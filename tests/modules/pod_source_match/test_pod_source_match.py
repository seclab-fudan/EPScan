from unittest import TestCase

from modules.pod_source_match import *
from modules.pod_source_match.rules import get_last_nontrivial_part
from modules.storage import ProjectFolder

BASE_PATH = Path(__file__).parent / '..' / '..' / 'resources' / 'pod_source_match'


def get_pod_info_by_name(matched_pod: MatchedMap, name: str) -> tuple[
    PodInfo, list[tuple[ProgramEntrypointInfo, Optional[MatchingRule]]]]:
    for pod, source_info in matched_pod.items():
        if pod.pod_name == name:
            return pod, source_info


def rule_exe_name_from_file(_: MatchingContext, pod_info: PodInfo, source_info: ProgramEntrypointInfo) -> bool:
    source_exe = get_last_nontrivial_part(source_info.main_file_path.parts)
    return any(source_exe == c.executable_name for c in pod_info.containers)


SIMPLE_MATCH_RULES = [MatchingRule('exe_name_from_file', rule_exe_name_from_file)]


def simple_match(psm: PodSourceMatcher):
    ctx = MatchingContext(psm.proj_name)

    for pod_info in psm.get_unmatched_pod_info():
        for source_info in psm.source_info:
            psm.run_rules(ctx, SIMPLE_MATCH_RULES, pod_info, source_info)


class TestPodSourceMatcher(TestCase):

    def test_match(self):
        proj = ProjectFolder(BASE_PATH)
        proj_name = 'test_proj'
        store = ObjectStore.from_config_dir(proj.conf(proj_name))

        psm = PodSourceMatcher(proj, proj_name, store)
        psm.extract_info()
        psm.remove_exception()
        simple_match(psm)

        with self.subTest('normal'):
            pod_info, source_infos = get_pod_info_by_name(psm.matched_pod, 'test_container')
            self.assertEqual(len(source_infos), 1)

            source_info, rule = source_infos[0]
            self.assertEqual(source_info.package_path, 'github.com/test_proj/test_source/cmd/test_exe')

        with self.subTest('exe name is pod name postfix'):
            pod_info, source_infos = get_pod_info_by_name(psm.matched_pod, 'test_proj-operator')
            self.assertEqual(len(source_infos), 1)

            source_info, rule = source_infos[0]
            self.assertEqual(source_info.package_path, 'github.com/test_proj/test_source/cmd/operator')

    def test_match_callsites(self):
        proj = ProjectFolder(BASE_PATH)
        proj_name = 'test_proj'
        store = ObjectStore.from_config_dir(proj.conf(proj_name))

        psm = PodSourceMatcher(proj, proj_name, store)
        psm.extract_info()
        psm.remove_exception()
        simple_match(psm)

        # 构建 CallSite 对象
        css = [
            CallSite(
                source_name='test_source',
                entrypoint='cmd/test_exe/main.go',
                parent='github.com/pkg/pkg.caller',
                resource_type='pods',
                verb='get',
                location='/file.go@1:2:3:4',
            ),
        ]

        # 匹配
        result = psm.match_callsites(css)
        self.assertEqual(len(result), 2)

        pod_result = None
        for r in result:
            if r.pod.name == 'test_container':
                pod_result = r
                break
        self.assertIsNotNone(pod_result)

        perms = pod_result.perms
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0], EPScanPermission('pods', 'get', None))
