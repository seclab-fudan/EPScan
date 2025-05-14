# rbac.py -- 实现 RBAC 子系统相关对象
#
# Copyright (C) 2024 KAAAsS
from enum import Enum
from typing import Optional

from tinydb import Query

from analyse.k8s.basic import Object, ObjectStore
from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)


class PermissionScope(Enum):
    """
    权限范围
    """
    CLUSTER = ('cluster', 3)
    NAMESPACE = ('namespace', 2)
    RESOURCE_SPECIFIC = ('resource-specific', 1)

    def __gt__(self, other):
        return self.value[1] > other.value[1]

    def __ge__(self, other):
        return self.value[1] >= other.value[1]

    def __repr__(self):
        return self.value[0]

    def __str__(self):
        return self.value[0]

    @staticmethod
    def from_str(s: str):
        if s is None or s == '?':
            return None
        for scope in PermissionScope:
            if s == scope.value[0]:
                return scope
        raise ValueError(f'Invalid PermissionScope: {s}')


CLUSTER = PermissionScope.CLUSTER
NAMESPACE = PermissionScope.NAMESPACE
RESOURCE_SPECIFIC = PermissionScope.RESOURCE_SPECIFIC


class ServiceAccount(Object):

    def __init__(self, data: dict, store=None):
        super().__init__(data, store)
        self._cached_role_bindings = None
        self._cached_roles = None

    def find_role_bindings(self):
        """查找关联的 RoleBinding"""
        if self._cached_role_bindings is not None:
            return self._cached_role_bindings

        self._cached_role_bindings = self.store.search(
            Query().subjects.any(
                (Query().kind == 'ServiceAccount') &
                (Query().name == self.name)
            )
        )
        return self._cached_role_bindings

    def find_roles(self):
        """查找关联的 Role"""
        if self._cached_roles is not None:
            return self._cached_roles

        binds = self.find_role_bindings()
        results = []
        for bind in binds:
            results += bind.find_role()
        self._cached_roles = results
        return results

    def can_i(self, *args, **kwargs):
        """判断是否有权限"""
        roles = self.find_roles()
        for role in roles:
            if role.can_i(*args, **kwargs):
                return True
        return False

    def __repr__(self):
        return f'ServiceAccount({self.data})'

    @staticmethod
    def from_dict(data: dict):
        if data['kind'] != 'ServiceAccount':
            return None
        return ServiceAccount(data)


class DefaultServiceAccount(ServiceAccount):
    def __init__(self, store=None):
        super().__init__({
            'apiVersion': 'v1',
            'kind': 'ServiceAccount',
            'metadata': {
                'name': 'default',
                'namespace': None,  # 实际上 default 应该属于某个命名空间
            }
        }, store)


def get_service_account_by_name(store: ObjectStore, sa_name: str) -> ServiceAccount:
    """根据名称查找 ServiceAccount"""
    # 默认 SA
    if sa_name == 'default' or sa_name == '':
        return DefaultServiceAccount(store)

    sas = store.search((Query().metadata.name == sa_name) & (Query().kind == 'ServiceAccount'))
    assert len(sas) == 1, f'Found {len(sas)} ServiceAccount with name {sa_name}'
    return sas[0]


class RoleBinding(Object):

    def find_role(self):
        """查找关联的 Role"""
        return self.store.search(
            (Query().kind.one_of(['Role', 'ClusterRole'])) &
            (Query().metadata.name == self.data['roleRef']['name'])
        )

    def __repr__(self):
        return f'RoleBinding({self.data})'

    @property
    def is_cluster(self):
        return self.data['kind'] == 'ClusterRoleBinding'

    @staticmethod
    def from_dict(data: dict):
        if data['kind'] not in ['RoleBinding', 'ClusterRoleBinding']:
            return None
        return RoleBinding(data)


class Role(Object):

    def list_rules(self, scope: Optional[PermissionScope] = None):
        """
        列出所有规则
        :param scope: 只返回指定 scope 的规则，不会考虑范围之间的偏序关系，为 None 则不限制
        """
        rules = []

        # cluster scope 规则不可能出现在 Role 中
        if scope == PermissionScope.CLUSTER and not self.is_cluster:
            return []
        # namespace scope 规则不可能出现在 ClusterRole 中
        if scope == PermissionScope.NAMESPACE and self.is_cluster:
            return []

        explicit_rules = self.data.get('rules', None)
        if explicit_rules:
            rules += explicit_rules

        if self.is_cluster:
            # 如果是集群角色，需要考虑合并规则
            agg_roles = self.find_matched_aggregation_roles()
            for role in agg_roles:
                rules += role.list_rules()

        # 过滤 resource-specific scope 的规则
        filtered_rules = []
        for rule in rules:
            norm_rule = _normalize_rule(rule)
            if norm_rule is None:
                continue
            is_resource_specific_rule = norm_rule['resourceNames'] is not None

            if scope == PermissionScope.RESOURCE_SPECIFIC and is_resource_specific_rule:
                filtered_rules.append(rule)
            elif scope != PermissionScope.RESOURCE_SPECIFIC and not is_resource_specific_rule:
                filtered_rules.append(rule)

        rules = filtered_rules

        return rules

    def can_i(self, api_group: str, verb: str, resource: str, resource_name: str = None,
              strict_scope: Optional[PermissionScope] = None):
        """
        判断是否有权限
        :param api_group: API 组。为 None 则不限制
        :param verb: 操作
        :param resource: 资源
        :param resource_name: 资源名称。为 None 则不限制
        :param strict_scope: 严格判定的权限范围，不会考虑范围之间的偏序关系，为 None 则不限制
        """
        if strict_scope is not None:
            assert isinstance(strict_scope, PermissionScope), 'strict_scope must be an instance of PermissionScope'

        rules = self.list_rules(scope=strict_scope)
        for rule in rules:
            norm_rule = _normalize_rule(rule)

            # 强制匹配的字段们
            if not _check_rule(norm_rule, 'apiGroups', api_group):
                continue
            if not _check_rule(norm_rule, 'resources', resource):
                continue
            if not _check_rule(norm_rule, 'verbs', verb):
                continue

            # 参数不指定就不限制的字段们
            if resource_name is not None and not _check_rule(norm_rule, 'resourceNames', resource_name):
                continue

            # 匹配一条规则
            return True
        return False

    def find_matched_aggregation_roles(self):
        """查找聚合条件匹配到的 ClusterRole 对象"""
        assert self.is_cluster, 'Aggregation rules only available for ClusterRole'

        result = []

        if 'aggregationRule' not in self.data:
            return result
        if 'clusterRoleSelectors' not in self.data['aggregationRule']:
            return result

        for match_rules in self.data['aggregationRule']['clusterRoleSelectors']:
            if 'matchLabels' in match_rules:
                match_labels = match_rules['matchLabels']

                cond = Query().kind == 'ClusterRole'
                for k, v in match_labels.items():
                    cond &= Query().metadata.labels[k] == v

                roles = self.store.search(cond)
                result += roles

            if 'matchExpressions' in match_rules:
                raise NotImplementedError('matchExpressions not supported yet')

        return result

    def __repr__(self):
        return f'Role({self.data})'

    @property
    def is_cluster(self):
        return self.data['kind'] == 'ClusterRole'

    @staticmethod
    def from_dict(data: dict):
        if data['kind'] not in ['Role', 'ClusterRole']:
            return None
        return Role(data)


def _normalize_rule(rule: dict) -> Optional[dict]:
    """
    规范化规则。完成规范化后，规则的如果是列表则说明是白名单，为 None 则说明可以是任意值
    :see: https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.25/#policyrule-v1-rbac-authorization-k8s-io
    """
    if 'nonResourceURLs' in rule:
        # 暂时不支持 nonResourceURLs，默认忽略规则
        return None

    norm_rule = rule.copy()

    assert 'apiGroups' in norm_rule, 'apiGroups must be in rule'
    if '*' in norm_rule['apiGroups']:
        norm_rule['apiGroups'] = None

    assert 'resources' in norm_rule, 'resources must be in rule'
    if '*' in norm_rule['resources']:
        norm_rule['resources'] = None

    assert 'verbs' in norm_rule, 'verbs must be in rule'
    if '*' in norm_rule['verbs']:
        norm_rule['verbs'] = None

    # resourceNames 空列表表示允许任何
    if 'resourceNames' not in norm_rule or len(norm_rule['resourceNames']) == 0:
        norm_rule['resourceNames'] = None

    return norm_rule


def _check_rule(norm_rule: dict, filed: str, value: str) -> bool:
    """检查规则"""
    if norm_rule[filed] is None:
        # 无限制
        return True
    return value in norm_rule[filed]


def _test():
    from analyse.k8s.basic import ObjectStore
    from pathlib import Path
    from pprint import pprint

    store = ObjectStore.from_config_dir(Path('/Users/kaaass/Project/research/k8s/data/small_dataset/cncf/crossplane'))

    sa: ServiceAccount = get_service_account_by_name(store, 'crossplane')
    pprint(sa)

    binds = sa.find_role_bindings()
    pprint(binds)

    roles = binds[0].find_role()
    pprint(roles)

    role = roles[0]
    pprint(role.list_rules())

    pprint(role.can_i('', 'list', 'secrets'))
    pprint(role.can_i('', 'non_exists_verb', 'secrets'))

    pprint(sa.can_i('', 'list', 'secrets'))
    pprint(sa.can_i('', 'non_exists_verb', 'secrets'))


if __name__ == '__main__':
    _test()
