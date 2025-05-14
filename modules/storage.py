from pathlib import Path
from typing import Iterable

from analyse.source import codeql
from modules.types import SourceCode

FILENAME_CODEQL_ENTRYPOINTS = "codeql_entrypoints.csv"


class ProjectFolder:
    """
    Project 文件夹的常用函数

    proj_root 文件夹的格式：
    - {project name}/        项目文件夹
      - conf/                K8s 配置文件目录
      - source/              项目源码
        - {repo name}/
      - db/                  CodeQL DB，运行 `ApiCallScanner.build_db` 后创建
        - {repo name}/
      - cache/               缓存，运行分析后创建
        - codeql.csv         源代码分析中 CodeQL 查询的 CSV 结果，运行 `ApiCallScanner.scan` 后创建
      - logs/                日志
      - result/              运行结果，运行分析后创建
        - issues.json        安全问题，运行 ep-scan 工具后创建
    """

    def __init__(self, proj_root: Path):
        self.root = proj_root

    def db(self, proj_name, source_name) -> Path:
        db_base = self.project(proj_name) / "db"
        db_base.mkdir(parents=True, exist_ok=True)
        return db_base / source_name

    def log(self, proj_name, log_file) -> Path:
        log_path = self.project(proj_name) / "logs"
        if log_file is not None:
            log_path /= log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path

    def cache(self, proj_name, cache_file) -> Path:
        cache_path = self.project(proj_name) / "cache"
        if cache_file is not None:
            cache_path /= cache_file
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def cache_query_result(self, proj_name, query: codeql.Query) -> Path:
        """CodeQL 查询的结果目录"""
        result_path = self.cache(proj_name, f"codeql_queries/{query.identifier}/")
        result_path.mkdir(parents=True, exist_ok=True)
        return result_path

    def project(self, proj_name, no_check=False) -> Path:
        project_path = self.root / proj_name
        if not no_check:
            assert project_path.exists(), f"Project {proj_name} not found"
        return project_path

    def projects(self) -> Iterable[str]:
        for proj in self.root.iterdir():
            if proj.is_dir():
                yield proj.name

    def source(self, proj_name, source_name, no_check=False) -> Path:
        source_dir = self.project(proj_name, no_check) / "source"
        if not no_check:
            assert source_dir.exists(), f"Source code not found in {source_dir}"
        if source_name is None:
            return source_dir
        return source_dir / source_name

    def sources(self, proj_name) -> Iterable[SourceCode]:
        source_dir = self.source(proj_name, None)
        for source in source_dir.iterdir():
            if source.is_dir():
                yield SourceCode.from_local(source.name, source)

    def conf(self, proj_name) -> Path:
        return self.project(proj_name) / "conf"

    def result(self, proj_name, result_file):
        result_path = self.project(proj_name) / "result"
        if result_file is not None:
            result_path /= result_file
        result_path.parent.mkdir(parents=True, exist_ok=True)
        return result_path
