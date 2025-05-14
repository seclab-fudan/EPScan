# __init__.py -- EP 分析模块
#
# Copyright (C) 2024 KAAAsS
from typing import Iterable, Optional

from analyse.security.base import Issue, Rule
from modules.perm_compare import permission
from modules.types import PodResult, EPScanPermission
from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

_CSV_HEADER = 'pod kind,pod name,perm resource,perm verb,perm scope,left pod,left perm,right pod,right perm'

RULE_EXCESSIVE_PERMISSIONS = Rule('excessive-permissions')


class PermComparer:
    """
    EP 分析模块的核心逻辑，主要用于比较两组 Pod 结果中的权限
    """

    def __init__(self, left: list[PodResult], right: list[PodResult]):
        self.left = left
        self.right = right

    def scan_ep(self) -> list[Issue]:
        """扫描过度的权限"""
        issues = []

        sensitive_perms = permission.get_sensitive_perm_lookup_map()

        for lf, rt in self._align():
            if lf is None:
                # 源码分析中得出多的 Pod，理论上不可能，因为都是匹配配置中的 Pod
                continue

            pod = lf.pod
            lf_set = _result_to_perm_keys(lf)
            if rt is None:
                warn('source pod calls no API, maybe not a golang container or analysis error', pod=pod)
            rt_set = _result_to_perm_keys(rt)

            eps = lf_set - rt_set
            exploitable_eps = set()
            for ep in eps:
                perm = _find_perm_by_key(lf.perms, ep)
                matched_sensitive = sensitive_perms.get(perm.get_deduplicate_key(), None)

                if not matched_sensitive:
                    continue
                if not perm.covers(matched_sensitive):
                    continue

                exploitable_eps.add(perm)

            if not exploitable_eps:
                continue

            issue = Issue(RULE_EXCESSIVE_PERMISSIONS) \
                .case_of(f'{pod.kind} have EP vulnerability') \
                .object(pod)
            for perm in exploitable_eps:
                issue.reason(f'Pod: {pod.kind} {pod.name}, PERM: {perm}')
            issues.append(issue)

        return issues

    def _align(self) -> Iterable[tuple[Optional[PodResult], Optional[PodResult]]]:
        """对齐两组 Pod 结果"""
        l_map = {rt.pod: rt for rt in self.left}
        r_map = {rt.pod: rt for rt in self.right}

        for pod in l_map.keys() | r_map.keys():
            yield l_map.get(pod), r_map.get(pod)


def _result_to_perm_keys(result: Optional[PodResult]) -> set[tuple[str, str]]:
    if result is None:
        return set()
    return {perm.get_deduplicate_key() for perm in result.perms}


def _find_perm_by_key(perms: list[EPScanPermission], key: tuple[str, str]) -> Optional[EPScanPermission]:
    for perm in perms:
        if perm.get_deduplicate_key() == key:
            return perm
    return None
