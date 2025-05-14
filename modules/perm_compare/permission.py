# permission.py -- 权限相关逻辑
#
# Copyright (C) 2024 KAAAsS
import collections
from pathlib import Path
from typing import NamedTuple

from analyse.k8s import workload
from analyse.k8s.rbac import PermissionScope, CLUSTER, NAMESPACE, RESOURCE_SPECIFIC
from modules.types import EPScanPermission, PermissionKey
from utils import csv_utils

_CSV_SENSITIVE_PERM = Path(__file__).parent / "sensitive_perm_rules.csv"

_cache_sensitive_perms = None
_cache_sensitive_perm_lookup_map = None


class SensitivePermission(NamedTuple):
    perm: EPScanPermission
    risk: str


def get_sensitive_perms() -> list[SensitivePermission]:
    """获取敏感权限列表"""
    global _cache_sensitive_perms
    if _cache_sensitive_perms is not None:
        return _cache_sensitive_perms

    rows = csv_utils.load_csv_to_dict(_CSV_SENSITIVE_PERM)
    perms = []
    for row in rows:
        if row["resource"] == "workload":
            resources = workload.WORKLOAD_RESOURCES
        else:
            resources = [row["resource"]]
        verbs = row["verb"].split("/")
        scope = PermissionScope.from_str(row["scope"])

        for resource in resources:
            for verb in verbs:
                perms.append(SensitivePermission(EPScanPermission(resource, verb, scope), row["risk"]))

    _cache_sensitive_perms = perms
    return perms


def get_sensitive_perm_lookup_map() -> dict[PermissionKey, EPScanPermission]:
    """获取敏感权限列表"""
    global _cache_sensitive_perm_lookup_map
    if _cache_sensitive_perm_lookup_map is not None:
        return _cache_sensitive_perm_lookup_map

    perms = get_sensitive_perms()
    perm_map = {}

    for perm in perms:
        key = perm.perm.get_deduplicate_key()
        # 保留 scope 最低的，确保匹配的更多
        if key not in perm_map or perm_map[key].scope > perm.perm.scope:
            perm_map[key] = perm.perm

    _cache_sensitive_perm_lookup_map = perm_map
    return perm_map


def get_risk_lookup_map() -> dict[tuple[str, str, str], str]:
    """获取敏感权限风险等级"""
    perms = get_sensitive_perms()
    dedup_perms = collections.defaultdict(list)

    for perm in perms:
        key = perm.perm.get_deduplicate_key()
        dedup_perms[key].append(perm)

    risk_map = {}

    for key, perms in dedup_perms.items():
        perms = sorted(perms, key=lambda x: x.perm.scope, reverse=True)
        for scope in (CLUSTER, NAMESPACE, RESOURCE_SPECIFIC):
            for perm in perms:
                if scope >= perm.perm.scope:
                    risk_map[key + (str(scope),)] = perm.risk
                    break

    return risk_map


def _test():
    risk = get_risk_lookup_map()
    print(risk)
    assert risk[('secrets', 'get', 'cluster')] == 'control-cluster'
    assert risk[('secrets', 'get', 'namespace')] == 'info-leak'


if __name__ == '__main__':
    _test()
