# basic.py -- K8s 对象的基础定义与配置解析
#
# Copyright (C) 2024 KAAAsS
from pathlib import Path
from pprint import pprint
from typing import Optional

import yaml
from tinydb import TinyDB, where
from tinydb.queries import QueryLike, Query
from tinydb.storages import MemoryStorage

from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)


class Object:
    """K8s 对象"""

    def __init__(self, data: dict, store=None, source_path: Optional[Path] = None):
        self.data = data
        self.store = store
        self.source_path = source_path

    def _repr_data(self):
        result = self.data.copy()
        if 'spec' in result:
            del result['spec']
        return result

    def __repr__(self):
        if self.__class__ != Object:
            result = f'{self.kind}'
        else:
            result = f'Object'
        result += '('
        result += f'name={self.name}, '
        result += f'source_path={self.source_path}, '
        result += f'data={self._repr_data()})'
        return result

    def bind_store(self, store):
        self.store = store

    def simple_check(self) -> bool:
        """简单检查是否是 k8s 对象"""
        return 'apiVersion' in self.data and 'kind' in self.data and 'metadata' in self.data

    def __eq__(self, other):
        return self.data == other.data

    def __hash__(self):
        return hash(repr(self.data))

    @property
    def kind(self):
        return self.data['kind']

    @property
    def name(self):
        return self.data['metadata']['name']

    @staticmethod
    def from_dict(data: dict):
        if data is None:
            return None

        from analyse.k8s.rbac import ServiceAccount, RoleBinding, Role
        from analyse.k8s.workload import Pod, Workload
        specialize_objs = [ServiceAccount, RoleBinding, Role, Pod, Workload]
        for cls in specialize_objs:
            try:
                obj = cls.from_dict(data)
                if obj is not None:
                    return obj
            except KeyError:
                continue
        return Object(data, source_path=None)


class ObjectStore:
    """一系列 K8s 对象"""

    def __init__(self, objects: list[Object]):
        self.objects = objects
        self._db_obj_map = {}
        self._db = self._make_db()

    def search(self, cond: QueryLike):
        docs = self._db.search(cond)
        results = []
        for doc in docs:
            results.append(self._db_obj_map[doc.doc_id])
        return results

    def search_by_kind(self, kind: str):
        """根据 kind 搜索对象"""
        return self.search(where('kind') == kind)

    def search_by_name(self, name: str):
        """根据 name 搜索对象"""
        return self.search(Query().metadata.name == name)

    def search_by_kind_and_name(self, kind: str, name: str):
        """根据 kind 和 name 搜索对象"""
        results = self.search(Query().kind == kind and Query().metadata.name == name)
        assert len(results) <= 1
        return results[0] if results else None

    def contains(self, cond: QueryLike):
        return self._db.contains(cond)

    def _make_db(self):
        """生成 tinydb 数据库"""
        db = TinyDB(storage=MemoryStorage)
        for obj in self.objects:
            doc_id = db.insert(obj.data)
            self._db_obj_map[doc_id] = obj
        return db

    def __getstate__(self):
        state = self.__dict__.copy()
        # 不序列化 DB
        state['_db'] = None
        state['_db_obj_map'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # FIXME: 不知道为什么，有时候 objects 会是一个全空的对象
        self.objects = [
            obj
            for obj in self.objects
            if hasattr(obj, 'data')
        ]
        # 重建 DB
        self._db_obj_map = {}
        self._db = self._make_db()

    def __iter__(self):
        return iter(self.objects)

    @staticmethod
    def from_config_dir(dir: Path):
        """从配置目录加载对象"""
        objects = []

        # 遍历所有 yaml 文件
        for path in dir.rglob('*.yaml'):
            with path.open() as f:
                # 解析文件（多文档）
                data = yaml.full_load_all(f)
                if data is None:
                    continue
                for item in data:
                    obj = Object.from_dict(item)
                    if obj is None:
                        continue
                    if not obj.simple_check():
                        debug(f'Invalid object in {path}, obj = {obj}')
                    obj.source_path = path.absolute()
                    objects.append(obj)

        store = ObjectStore(objects)
        for obj in store.objects:
            obj.bind_store(store)
        return store


if __name__ == '__main__':
    os = ObjectStore.from_config_dir(Path('/Users/kaaass/Project/research/k8s/data/small_dataset/cncf/crossplane'))
    pprint(os.objects)
    pprint(os.search_by_kind('ServiceAccount'))
