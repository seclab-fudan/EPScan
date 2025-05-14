from unittest import TestCase

from analyse.k8s import rbac
from analyse.k8s.rbac import permission, PermissionScope
from tests import load_single_objs


class TestRole(TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.store = load_single_objs()

    def test_list_rules(self):
        with self.subTest("Empty rules"):
            role = self.store.search_by_name('role_empty_rules')[0]
            self.assertEqual(role.list_rules(), [])

    def test_can_i(self):
        role = self.store.search_by_name('role-normal')[0]
        self.assertTrue(role.can_i(api_group='', resource='pods', verb='get'))
        self.assertTrue(role.can_i(api_group='', resource='pods', verb='list'))

    def test_can_i_wildcard(self):
        cases = [
            {
                'role': 'role-wildcard-verb',
                'perms': [('', 'pods', '*')],
            },
            {
                'role': 'role-wildcard-resource',
                'perms': [('', '*', 'get'), ('apps', '*', 'list')],
            },
            {
                'role': 'role-wildcard-api-group',
                'perms': [('*', '*', 'watch')],
            },
        ]
        role = self.store.search_by_name('role-wildcard-verb')[0]
        role.can_i(api_group='', resource='pods', verb='watch')

        for case in cases:
            with self.subTest(case['role']):
                role = self.store.search_by_name(case['role'])[0]

                permitted_perms = set()
                for r_api_group, r_resource, r_verb in case['perms']:
                    # 遍历全体权限
                    for perm in permission.get_all_perms():
                        # 检查这个权限是否匹配测试用例的规则
                        matched_api_group = r_api_group == '*' or r_api_group == perm.api_group
                        matched_resource = r_resource == '*' or r_resource == perm.resource
                        matched_verb = r_verb == '*' or r_verb == perm.verb
                        if matched_api_group and matched_resource and matched_verb:
                            self.assertTrue(role.can_i(api_group=perm.api_group,
                                                       resource=perm.resource,
                                                       verb=perm.verb),
                                            f"Role {case['role']} should have permission {perm}")
                            permitted_perms.add(perm)

                # 检查是否有未匹配的权限
                for perm in permission.get_all_perms():
                    if perm not in permitted_perms:
                        self.assertFalse(role.can_i(api_group=perm.api_group,
                                                    resource=perm.resource,
                                                    verb=perm.verb),
                                         f"Role {case['role']} should not have permission {perm}")

    def test_can_i_scoped(self):
        cases = [
            {
                'role': 'role-scope-namespace',
                'perms': {
                    PermissionScope.NAMESPACE: [('', 'pods', 'get')],
                    PermissionScope.CLUSTER: [],
                    PermissionScope.RESOURCE_SPECIFIC: [],
                },
            },
            {
                'role': 'role-scope-cluster',
                'perms': {
                    PermissionScope.NAMESPACE: [],
                    PermissionScope.CLUSTER: [('', 'pods', 'get')],
                    PermissionScope.RESOURCE_SPECIFIC: [],
                },
            },
            {
                'role': 'role-scope-resource-specific',
                'perms': {
                    PermissionScope.NAMESPACE: [],
                    PermissionScope.CLUSTER: [],
                    PermissionScope.RESOURCE_SPECIFIC: [('', 'pods', 'get')],
                },
            },
            {
                'role': 'role-scope-resource-specific-cluster',
                'perms': {
                    PermissionScope.NAMESPACE: [],
                    PermissionScope.CLUSTER: [('', 'pods', 'get')],
                    PermissionScope.RESOURCE_SPECIFIC: [('', 'pods', 'get')],
                },
            },
            {
                'role': 'role-scope-resource-specific-namespace',
                'perms': {
                    PermissionScope.NAMESPACE: [('', 'pods', 'get')],
                    PermissionScope.CLUSTER: [],
                    PermissionScope.RESOURCE_SPECIFIC: [('', 'pods', 'get')],
                },
            },
        ]
        # role = self.store.search_by_name('role-scope-namespace')[0]
        # role.can_i(api_group='', resource='pods', verb='get', strict_scope='cluster')

        for case in cases:
            with self.subTest(case['role']):
                role = self.store.search_by_name(case['role'])[0]

                for scope, perms in case['perms'].items():
                    # 检查是否有该有的权限
                    permitted_perms = set()
                    for perm in perms:
                        self.assertTrue(role.can_i(api_group=perm[0], resource=perm[1], verb=perm[2],
                                                   strict_scope=scope),
                                        f"Role {case['role']} should have permission {perm} in scope {scope}")

                        for r_perm in permission.get_all_perms():
                            if r_perm.api_group == perm[0] and r_perm.resource == perm[1] and r_perm.verb == perm[2]:
                                permitted_perms.add(r_perm)

                    # 检查是否有未匹配的权限
                    for perm in permission.get_all_perms():
                        if perm not in permitted_perms:
                            self.assertFalse(role.can_i(api_group=perm.api_group,
                                                        resource=perm.resource,
                                                        verb=perm.verb,
                                                        strict_scope=scope),
                                             f"Role {case['role']} should not have permission {perm} in scope {scope}")


class TestServiceAccount(TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.store = load_single_objs()

    def test_default_sa(self):
        sa = rbac.get_service_account_by_name(self.store, 'default')
        self.assertEqual(sa.name, 'default')

        roles = sa.find_roles()
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0].name, 'default_sa_role')

        self.assertTrue(sa.can_i(api_group='', resource='pods', verb='get'))
        self.assertTrue(sa.can_i(api_group='', resource='pods', verb='watch'))
