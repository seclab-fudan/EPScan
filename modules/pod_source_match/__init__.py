# __init__.py -- Pod-源代码 关联模块的实现
#
# Copyright (C) 2024 KAAAsS
import collections
import json
from pathlib import Path
from typing import Optional, Generator, NamedTuple

from analyse.k8s.basic import ObjectStore
from modules import ignore
from modules.pod_source_match.info import extract_pod_info, extract_program_entrypoints, ProgramEntrypointInfo, PodInfo
from modules.pod_source_match.rules import MatchingRule, MatchingContext, MATCHING_RULES_EXECUTABLE, \
    check_extracted_exe_contain_source_code_path
from modules.storage import ProjectFolder
from modules.types import CallSite, PodResult, EPScanPermission
from utils import csv_utils
from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

MatchedMap = dict[PodInfo, list[tuple[ProgramEntrypointInfo, Optional[MatchingRule]]]]


class PodSourceMatcher:
    """
    Pod-源代码 关联模块的核心逻辑，主要用于将源代码中的 entrypoints 与配置中的 workload/pod 进行匹配

    ```python
    psm = PodSourceMatcher(proj, proj_name, store)
    psm.extract_info()
    psm.remove_exception()
    psm.match_by_rule()
    result = psm.match_callsites(callsites)
    ```
    """

    def __init__(self, proj: ProjectFolder, proj_name: str, store: ObjectStore):
        self.proj = proj
        self.proj_name = proj_name
        self.store = store

        self.pod_info: list[PodInfo] = []
        self.source_info: list[ProgramEntrypointInfo] = []

        self.matched_pod: MatchedMap = collections.defaultdict(list)

    def remove_exception(self):
        """删除需要排除的信息，包括 Pod 与入口"""
        self._remove_container_not_golang()
        self._remove_empty_pod()
        self._remove_exception_entrypoint()

    def extract_info(self):
        cache_dir = self.proj.cache(self.proj_name, None)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.pod_info = list(extract_pod_info(self.store, cache_dir))
        self.source_info = list(extract_program_entrypoints(self.proj, self.proj_name))

    def do_match(self):
        cache_path = self.proj.cache(self.proj_name, 'matched_pod.json')
        if cache_path.exists():
            info('loading matched pod from cache', cache=cache_path)
            self.matched_pod = _load_cache_matched_map(cache_path, self.pod_info, self.source_info)
            return

        self.match_by_extract_executable()
        # Uncomment the following line to use heuristic matching as a fallback, which only works in very few cases.
        # self.match_by_executable_heuristic()

        _save_cache_matched_map(cache_path, self.matched_pod)

    def match_by_extract_executable(self, disable_llm=False):
        ctx = MatchingContext(self.proj_name)

        for pod_info in self.get_unmatched_pod_info():
            info('extracting executables for pod', pod=pod_info.pod_name)
            pod_info.extract_all_executables()

            try:
                matched_source = check_extracted_exe_contain_source_code_path(pod_info, self.source_info,
                                                                              disable_llm_extraction=disable_llm)
                dummy_rule = MatchingRule('extracted_exe_contain_source_code_path', None)
                debug('matched source by extracted exe source code path', pod=pod_info.pod_name, source=matched_source)
                for source_info in matched_source:
                    self.matched_pod[pod_info].append((source_info, dummy_rule))
            except Exception as e:
                error('error in check_extracted_exe_contain_source_code_path', pod=pod_info.pod_name, exc_info=e)
                continue

    def match_by_executable_heuristic(self):
        ctx = MatchingContext(self.proj_name)

        for pod_info in self.get_unmatched_pod_info():
            for source_info in self.source_info:
                self.run_rules(ctx, MATCHING_RULES_EXECUTABLE, pod_info, source_info)

    def run_rules(self, ctx, rules: list[MatchingRule], pod_info: PodInfo, source_info: ProgramEntrypointInfo) -> bool:
        for rule in rules:
            try:
                if rule.rule_func(ctx, pod_info, source_info):
                    debug('matched pod-source', pod=pod_info, entrypoint=source_info, rule=rule)
                    self.matched_pod[pod_info].append((source_info, rule))
                    return True
            except Exception as e:
                error('error in rule', rule=rule, exc_info=e)
        return False

    def match_callsites(self, callsites: list[CallSite]) -> list[PodResult]:
        Entrypoint = tuple[str, str]
        entrypoint_to_cs: dict[Entrypoint, list[CallSite]] = collections.defaultdict(list)
        for cs in callsites:
            entrypoint_to_cs[(cs.source_name, cs.entrypoint)].append(cs)

        results = []
        for pod_info, source_info_list in self.matched_pod.items():
            perms: list[EPScanPermission] = []

            for source_info, rule in source_info_list:
                entrypoint = (source_info.source_name, str(source_info.main_file_path))
                for cs in entrypoint_to_cs.get(entrypoint, []):
                    perms.append(cs.to_permission())

            results.append(PodResult(pod_info.get_pod(), perms))

        return results

    def get_unmatched_pod_info(self) -> list[PodInfo]:
        return [pod_info for pod_info in self.pod_info if pod_info not in self.matched_pod]

    def get_unmatched_source_info(self) -> list[ProgramEntrypointInfo]:
        matched_source = {
            source_info for source_info_list in self.matched_pod.values() for source_info, _ in source_info_list
        }
        return [source_info for source_info in self.source_info if source_info not in matched_source]

    def save_csv(self, output: Path):
        matched_info = list(export_matched_map(self.matched_pod))
        unmatched = self.get_unmatched_pod_info()
        unmatched_info = [p.dict() for p in unmatched]
        csv_utils.export_dict_to_csv(matched_info + unmatched_info, output)

    _EXCEPTION_COMMAND = [
        'curl', 'wget', 'npm', 'python3', 'kubectl', 'busybox', 'node', 'python',
    ]

    _EXCEPTION_APP = [
        'mosquitto', 'redis', 'mariadb', 'mysql', 'gunicorn', 'nginx', 'pgsql-postgresql',
    ]

    def _remove_container_not_golang(self):
        def non_golang_container(p: PodInfo, c: PodInfo.ContainerInfo):
            if c.name in self._EXCEPTION_COMMAND or c.name in self._EXCEPTION_APP:
                return True
            if c.image_name in self._EXCEPTION_COMMAND or c.image_name in self._EXCEPTION_APP:
                return True
            if c.executable_name in self._EXCEPTION_COMMAND or c.executable_name in self._EXCEPTION_APP:
                return True
            if any(cmd in self._EXCEPTION_APP for cmd in c.command):
                return True

            ignored = ignore.load_ignored_containers()
            for ignored_c in ignored:
                if self.proj_name != ignored_c.project:
                    continue
                if p.pod_name != ignored_c.pod_name:
                    continue
                if c.name != ignored_c.container_name:
                    continue
                info('found ignored container', pod=p.pod_name, container=c.name, reason=ignored_c.reason)
                return True

            return False

        for pod_info in self.pod_info:
            pod_info.containers = list(filter(
                lambda c: not non_golang_container(pod_info, c),
                pod_info.containers
            ))

    def _remove_empty_pod(self):
        for pod_info in self.pod_info:
            if len(pod_info.containers) == 0:
                info('found empty pod, will be remove', pod=pod_info.pod_name)
        self.pod_info = list(filter(
            lambda p: len(p.containers) > 0,
            self.pod_info
        ))

    def _remove_exception_entrypoint(self):
        def is_exception_entrypoint(e: ProgramEntrypointInfo):
            path = str(e.main_file_path)
            return not path.startswith('test') and not path.startswith('demo')

        self.source_info = list(filter(is_exception_entrypoint, self.source_info))


def export_matched_map(matched_map: MatchedMap, proj_name: Optional[str] = None) -> Generator[
    dict[str, str], None, None]:
    for pod_info, source_info_list in matched_map.items():
        for source_info, rule in source_info_list:
            row = {}
            if proj_name:
                row['project'] = proj_name
            row.update(pod_info.dict())
            row.update(source_info.dict())
            row['rule'] = rule.name if rule else ''
            yield row


class CacheEntry(NamedTuple):
    pod_kind: str
    pod_name: str
    source_name: str
    source_main_file_path: str
    rule_name: Optional[str]


def _load_cache_matched_map(cache_path: Path, pod_infos: list[PodInfo],
                            source_infos: list[ProgramEntrypointInfo]) -> MatchedMap:
    with cache_path.open() as f:
        data = json.load(f)
    matched_pod = collections.defaultdict(list)
    for d in data:
        entry = CacheEntry(*d)

        pod_info = None
        for p in pod_infos:
            if p.get_pod().kind == entry.pod_kind and p.get_pod().name == entry.pod_name:
                pod_info = p
                break
        assert pod_info is not None, f'pod not found: {entry.pod_kind} {entry.pod_name}'

        source_info = None
        for s in source_infos:
            if s.source_name == entry.source_name and str(s.main_file_path) == entry.source_main_file_path:
                source_info = s
                break

        rule_name = entry.rule_name
        rule = MatchingRule(rule_name, None) if rule_name else None
        matched_pod[pod_info].append((source_info, rule))
    return matched_pod


def _save_cache_matched_map(cache_path: Path, matched_pod: MatchedMap):
    data = []
    for pod_info, source_info_list in matched_pod.items():
        for source_info, rule in source_info_list:
            data.append(CacheEntry(pod_info.get_pod().kind, pod_info.get_pod().name,
                                   source_info.source_name, str(source_info.main_file_path),
                                   rule.name if rule else None))
    with cache_path.open('w') as f:
        json.dump(data, f, indent=2)


def _test():
    from pprint import pprint

    proj_root = ProjectFolder(Path('/Users/kaaass/Project/research/k8s/scripts/tests/resources/e2e'))
    store = ObjectStore.from_config_dir(
        Path('/Users/kaaass/Project/research/k8s/scripts/tests/resources/e2e/chaos-mesh/conf'))

    psm = PodSourceMatcher(proj_root, 'chaos-mesh', store)
    psm.extract_info()
    pprint(psm.pod_info)
    pprint(psm.source_info)

    psm.match_by_extract_executable()
    pprint(psm.matched_pod)
    pprint(psm.get_unmatched_pod_info())


if __name__ == '__main__':
    _test()
