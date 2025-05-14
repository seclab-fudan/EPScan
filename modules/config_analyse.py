# config_analyse.py -- 配置分析模块
#
# Copyright (C) 2024 KAAAsS

from analyse.k8s.rbac import ServiceAccount, PermissionScope
from analyse.k8s.rbac.permission import get_all_perms
from analyse.k8s.workload import ContainerCarrier
from modules.types import EPScanPermission, PodResult


class PodPermAnalyser:
    """
    配置分析模块的核心逻辑，主要用于分析配置中的所有 Pod 与 Workload，并分析其具有的权限

    ```python
    ppa = PodPermAnalyser()
    results = ppa.analyse(store)
    ```
    """

    def analyse(self, store) -> list[PodResult]:
        """分析配置中的所有 Pod 及其具有的权限"""
        results = []

        for pod in store:
            if not isinstance(pod, ContainerCarrier):
                continue
            sa = pod.get_sa()
            perms = list_all_perms(sa)
            results.append(PodResult(pod, perms))

        return results


def list_all_perms(sa: ServiceAccount) -> list[EPScanPermission]:
    """
    列出 ServiceAccount 具有的所有权限。如果多个权限除 scope 之外都相同，则按偏序只列出一个 scope 最大的一个。
    :param sa: ServiceAccount 对象
    :return:
    """
    perms = {}

    for perm in get_all_perms():
        for scope in PermissionScope:
            if perm.is_permitted_to(sa, strict_scope=scope):
                ep_perm = EPScanPermission(perm.resource, perm.verb, scope)
                key = ep_perm.get_deduplicate_key()
                if key not in perms:
                    perms[key] = ep_perm
                else:
                    perms[key] = max(perms[key], ep_perm, key=lambda x: x.scope)

    return list(perms.values())
