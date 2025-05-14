# permission.py -- RBAC 权限对象
#
# Copyright (C) 2024 KAAAsS
import csv
from pathlib import Path
from typing import NamedTuple

_CSV_ALL_PERM = Path(__file__).parent / "data" / "all_perm.csv"


class Permission(NamedTuple):
    resource: str
    verb: str
    api_group: str = None
    api_version: str = None

    def is_permitted_to(self, can_i_able, strict_scope) -> bool:
        return can_i_able.can_i(api_group=self.api_group, resource=self.resource, verb=self.verb,
                                strict_scope=strict_scope)


_cache_all_perms = None


def get_all_perms() -> set[Permission]:
    """获取所有权限列表"""
    global _cache_all_perms
    if _cache_all_perms is not None:
        return _cache_all_perms

    perms = _load_perm_csv(_CSV_ALL_PERM)
    _cache_all_perms = perms
    return perms


def _load_perm_csv(csv_path: Path) -> set[Permission]:
    perms = set()
    with csv_path.open() as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for data in reader:
            api_gv = data[2]
            api_group, api_version = api_gv.split('/') if '/' in api_gv else ('', api_gv)
            resource = data[0]
            verbs = data[5:]
            for verb in verbs:
                if verb:
                    perms.add(Permission(resource, verb, api_version=api_version, api_group=api_group))
    return perms
