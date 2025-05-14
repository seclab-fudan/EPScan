# types.py -- EP-Scan 各个模块的公共类型定义
#
# Copyright (C) 2024 KAAAsS
from pathlib import Path
from typing import NamedTuple, Optional

from analyse.k8s.rbac import PermissionScope
from analyse.k8s.workload import ContainerCarrier

PermissionKey = tuple[str, str]


class EPScanPermission(NamedTuple):
    """
    权限
    """
    resource: str
    verb: str
    scope: Optional[PermissionScope]

    def get_deduplicate_key(self):
        return self.resource, self.verb

    def covers(self, other: 'EPScanPermission'):
        """检查当前权限是否覆盖了另一个权限"""
        if self.get_deduplicate_key() != other.get_deduplicate_key():
            return False
        if self.scope is None or other.scope is None:
            return True
        return self.scope >= other.scope


class RemoteRepository(NamedTuple):
    """
    远程仓库
    """
    url: str
    tag: Optional[str] = None
    commit_hash: Optional[str] = None


class SourceCode(NamedTuple):
    """
    源代码仓库
    """
    name: str
    remote_repo: Optional[RemoteRepository]
    local_path: Optional[Path]

    def __hash__(self):
        return hash(self.name)

    @staticmethod
    def empty(name: str):
        return SourceCode(name, None, None)

    @staticmethod
    def from_remote(name: str, remote: RemoteRepository):
        return SourceCode(name, remote, None)

    @staticmethod
    def from_local(name: str, local_path: Path | str):
        return SourceCode(name, None, Path(local_path))


class CallSite(NamedTuple):
    source_name: str
    entrypoint: str
    parent: str
    resource_type: str
    verb: str
    location: str

    def to_permission(self):
        # 从 CallSite 中无法获取权限范围，因此 scope 为 None
        return EPScanPermission(self.resource_type, self.verb, scope=None)


class PodResult(NamedTuple):
    """单个 Pod 的分析结果，包含了 Pod 及其具有的所有权限"""
    pod: ContainerCarrier
    perms: list[EPScanPermission]
