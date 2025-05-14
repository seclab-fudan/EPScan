from pathlib import Path
from pprint import pprint
from unittest import TestCase

from analyse.k8s.rbac import NAMESPACE, RESOURCE_SPECIFIC
from analyse.k8s.workload import ContainerCarrier
from modules.perm_compare import PermComparer
from modules.types import EPScanPermission, PodResult

BASE_PATH = Path(__file__).parent / '..' / 'resources'


def mk_pod(name):
    return ContainerCarrier({
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            'name': name
        }
    })


def perm(resource, verb, scope):
    return EPScanPermission(resource, verb, scope)


def pret(pod, perms):
    return PodResult(pod, perms)


class TestPermComparer(TestCase):
    def test_scan_ep(self):
        with self.subTest('lf more perm'):
            p = mk_pod('pod')
            lf = [pret(p, [perm('pods', 'update', NAMESPACE), ret := perm('pods', 'patch', NAMESPACE)])]
            rt = [pret(p, [perm('pods', 'update', None)])]

            pc = PermComparer(lf, rt)
            issues = pc.scan_ep()
            self.assertEqual(1, len(issues))
            issue = issues[0]
            self.assertEqual('Pod have EP vulnerability', issue.case)
            self.assertEqual(p, issue.objects[0])
            self.assertIn(repr(ret), issue.reasons[0])

        with self.subTest('lf more perm + not exploitable ep (perm)'):
            p = mk_pod('pod')
            lf = [pret(p, [perm('pods', 'update', NAMESPACE),
                           ret := perm('pods', 'patch', NAMESPACE),
                           perm('pods', 'get', NAMESPACE)])]
            rt = [pret(p, [perm('pods', 'update', None)])]

            pc = PermComparer(lf, rt)
            issues = pc.scan_ep()
            self.assertEqual(1, len(issues))
            issue = issues[0]
            self.assertEqual('Pod have EP vulnerability', issue.case)
            self.assertEqual(p, issue.objects[0])
            self.assertIn(repr(ret), issue.reasons[0])

        with self.subTest('lf more perm + not exploitable ep (scope)'):
            p = mk_pod('pod')
            lf = [pret(p, [perm('pods', 'update', NAMESPACE),
                           ret := perm('pods', 'patch', NAMESPACE),
                           perm('secrets', 'get', RESOURCE_SPECIFIC)])]
            rt = [pret(p, [perm('pods', 'update', None)])]

            pc = PermComparer(lf, rt)
            issues = pc.scan_ep()
            self.assertEqual(1, len(issues))
            issue = issues[0]
            self.assertEqual('Pod have EP vulnerability', issue.case)
            self.assertEqual(p, issue.objects[0])
            self.assertIn(repr(ret), issue.reasons[0])

        with self.subTest('lf + rt more perm'):
            p = mk_pod('pod')
            lf = [pret(p, [perm('pods', 'update', NAMESPACE), perm('pods', 'patch', NAMESPACE)])]
            rt = [pret(p, [perm('pods', 'update', None), perm('pods', 'create', None)])]

            pc = PermComparer(lf, rt)  # 应该打印日志
            issues = pc.scan_ep()
            self.assertEqual(1, len(issues))

        with self.subTest('lf + rt more pod'):
            p = mk_pod('pod1')
            p2 = mk_pod('pod2')
            p3 = mk_pod('pod3')
            lf = [pret(p, [perm('pods', 'patch', NAMESPACE)]),
                  pret(p2, [perm('pods', 'patch', NAMESPACE)])]
            rt = [pret(p, [perm('pods', 'patch', None)]),
                  pret(p3, [perm('pods', 'patch', None)])]

            pc = PermComparer(lf, rt)
            issues = pc.scan_ep()
            pprint(issues)
            self.assertEqual(2, len(issues))
            self.assertIn(p2, issues[0].objects + issues[1].objects)
