# ignore.py -- 处理需要忽略部分项目的逻辑
#
# Copyright (C) 2024 KAAAsS
from pathlib import Path
from typing import NamedTuple

from utils import csv_utils

_FILE_IGNORE_CONTAINERS = Path(__file__).parent / 'special_rules' / 'ignore_containers.csv'

_CACHE_IGNORE_CONTAINERS = []


class IgnoredContainer(NamedTuple):
    project: str
    pod_name: str
    container_name: str
    reason: str


def load_ignored_containers():
    # TODO: 更改为每个项目可以单独设置要忽略的容器
    global _CACHE_IGNORE_CONTAINERS
    if not _CACHE_IGNORE_CONTAINERS:
        data = csv_utils.load_csv_to_dict(_FILE_IGNORE_CONTAINERS)
        _CACHE_IGNORE_CONTAINERS = [IgnoredContainer(*x.values()) for x in data]
    return _CACHE_IGNORE_CONTAINERS
