from pathlib import Path
from unittest import TestCase

from analyse.k8s.basic import ObjectStore
from analyse.k8s.rbac import CLUSTER, NAMESPACE
from modules.config_analyse import *
from modules.types import EPScanPermission
from tests import load_single_objs

BASE_PATH = Path(__file__).parent / '..' / 'resources' / 'config_analyse'


class TestPodPermAnalyser(TestCase):
    def test_analyse(self):
        store = ObjectStore.from_config_dir(BASE_PATH / 'normal')

        ppa = PodPermAnalyser()
        results = ppa.analyse(store)
        self.assertEqual(len(results), 1)

        pod_result = results[0]
        self.assertEqual(pod_result.pod.name, 'nginx-deployment')

        perms = pod_result.perms
        self.assertEqual(len(perms), 7)
        self.assertIn(EPScanPermission('pods', 'get', NAMESPACE), perms)
        self.assertIn(EPScanPermission('pods', 'list', NAMESPACE), perms)
        self.assertIn(EPScanPermission('secrets', 'get', NAMESPACE), perms)
        self.assertIn(EPScanPermission('secrets', 'list', NAMESPACE), perms)
        self.assertIn(EPScanPermission('deployments', 'create', NAMESPACE), perms)
        self.assertIn(EPScanPermission('events', 'get', CLUSTER), perms)
        self.assertIn(EPScanPermission('events', 'list', CLUSTER), perms)

    def test_coredns(self):
        store = ObjectStore.from_config_dir(BASE_PATH / 'coredns')

        ppa = PodPermAnalyser()
        results = ppa.analyse(store)
        self.assertEqual(len(results), 1)

        pod_result = results[0]
        self.assertEqual(pod_result.pod.name, 'coredns')

        perms = pod_result.perms
        self.assertEqual(len(perms), 10)

        for resc in ('endpoints', 'services', 'pods', 'namespaces'):
            self.assertIn(EPScanPermission(resc, 'list', CLUSTER), perms)
            self.assertIn(EPScanPermission(resc, 'watch', CLUSTER), perms)

        self.assertIn(EPScanPermission('endpointslices', 'list', CLUSTER), perms)
        self.assertIn(EPScanPermission('endpointslices', 'watch', CLUSTER), perms)

    def test_any_match(self):
        store = ObjectStore.from_config_dir(BASE_PATH / 'any_match')

        ppa = PodPermAnalyser()
        results = ppa.analyse(store)
        self.assertEqual(len(results), 1)

        pod_result = results[0]
        self.assertEqual(pod_result.pod.name, 'nginx-deployment')

        perms = set(pod_result.perms)
        expected_perms = {EPScanPermission(p.resource, p.verb, NAMESPACE) for p in get_all_perms() if
                          p.api_group == '' and p.api_version == 'v1'}
        self.assertEqual(perms, expected_perms)

    def test_kubescape(self):
        store = ObjectStore.from_config_dir(BASE_PATH / 'kubescape')

        ppa = PodPermAnalyser()
        results = ppa.analyse(store)
        self.assertEqual(len(results), 1)

        pod_result = results[0]
        self.assertEqual(pod_result.pod.name, 'kubescape')

        perms = set(pod_result.perms)
        expected_perms = {EPScanPermission(p.resource, p.verb, CLUSTER) for p in get_all_perms() if
                          p.verb in ("get", "list")}
        self.assertEqual(expected_perms, perms)

    def test_dex(self):
        store = ObjectStore.from_config_dir(BASE_PATH / 'dex')

        ppa = PodPermAnalyser()
        results = ppa.analyse(store)
        self.assertEqual(len(results), 1)

        pod_result = results[0]
        self.assertEqual(pod_result.pod.name, 'dex')

        perms = set(pod_result.perms)
        expected_perms = {EPScanPermission('customresourcedefinitions', 'create', CLUSTER),
                          EPScanPermission('customresourcedefinitions', 'list', CLUSTER)}
        self.assertEqual(expected_perms, perms)


class TestUtils(TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.store = load_single_objs()

    def test_list_all_perms(self):
        sa = self.store.search_by_name('test_sa')[0]
        perms = list_all_perms(sa)

        self.assertEqual(len(perms), 7)
        self.assertIn(EPScanPermission('pods', 'get', PermissionScope.NAMESPACE), perms)
        self.assertIn(EPScanPermission('pods', 'list', PermissionScope.RESOURCE_SPECIFIC), perms)
        self.assertIn(EPScanPermission('pods', 'watch', PermissionScope.NAMESPACE), perms)
        self.assertIn(EPScanPermission('secrets', 'list', PermissionScope.CLUSTER), perms)
        self.assertIn(EPScanPermission('pods', 'patch', PermissionScope.CLUSTER), perms)
        self.assertIn(EPScanPermission('pods', 'update', PermissionScope.CLUSTER), perms)
        self.assertIn(EPScanPermission('deployments', 'get', PermissionScope.RESOURCE_SPECIFIC), perms)
