# source_analyse.py -- 源码分析模块
#
# Copyright (C) 2024 KAAAsS
import csv
from pathlib import Path

from analyse.source import codeql
from modules.storage import ProjectFolder, FILENAME_CODEQL_ENTRYPOINTS
from modules.types import CallSite
from utils.log import log_ctx, log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)


def parse_query_result(result_path: Path) -> list['CallSite']:
    info("parse CodeQL query results")

    assert result_path.exists(), "CodeQL result not found"

    with result_path.open() as result_file:
        reader = csv.reader(result_file)
        next(reader)
        return [CallSite(*row) for row in reader]


class ApiCallScanner:
    """
    源码分析模块的核心逻辑，主要用于扫描源码中的 K8s API 调用点

    ```python
    acs = ApiCallScanner(proj_root)
    acs.build_db(proj_name)
    css = acs.scan(proj_name)
    ```
    """

    def __init__(self, proj: ProjectFolder):
        self.proj = proj

    def build_db(self, proj_name) -> None:
        info("check CodeQL environment")
        codeql.prepare_queries()
        with log_ctx(project=proj_name):
            info("build CodeQL database for project")

            for source in self.proj.sources(proj_name):
                with log_ctx(source=source):
                    source_path = source.local_path
                    dest_path = self.proj.db(proj_name, source.name)
                    log_path = self.proj.log(proj_name, f'codeql/build_db_{source.name}.log')

                    if dest_path.exists():
                        info("db already exists, skip building")
                        continue
                    try:
                        codeql.build_db(source_path, dest_path, log_path)
                    except AssertionError as e:
                        warn("failed to build CodeQL database for source", source=source, error=e)
                        continue

            info("done building CodeQL database")

    def scan(self, proj_name) -> list['CallSite']:
        with log_ctx(project=proj_name):
            info("scan project for API calls")

            for source in self.proj.sources(proj_name):
                with log_ctx(source=source):
                    self.run_query(proj_name, source.name, codeql.QUERY_REACHABLE_API_CALLS)
                    # 顺便查询所有 API 调用便于结果校验
                    self.run_query(proj_name, source.name, codeql.QUERY_API_CALLS)
                    # 查询所有入口点，作为后续 Pod-source 模块的输入
                    self.run_query(proj_name, source.name, codeql.QUERY_ENTRYPOINTS)

            # 合并分仓库的结果
            result_reachable_path = self.proj.cache(proj_name, 'codeql.csv')
            result_calls_path = self.proj.cache(proj_name, 'codeql_all_cs.csv')
            result_entrypoints_path = self.proj.cache(proj_name, FILENAME_CODEQL_ENTRYPOINTS)

            self.merge_query_result(proj_name, codeql.QUERY_REACHABLE_API_CALLS, result_reachable_path)
            self.merge_query_result(proj_name, codeql.QUERY_API_CALLS, result_calls_path)
            self.merge_query_result(proj_name, codeql.QUERY_ENTRYPOINTS, result_entrypoints_path)

            # 解析结果
            return parse_query_result(result_reachable_path)

    def run_query(self, proj_name, source_name, query: codeql.Query) -> None:
        info("run CodeQL query for source", query=query)

        db_path = self.proj.db(proj_name, source_name)
        assert db_path.exists(), f"Database not found for {source_name}"
        log_dir = self.proj.log(proj_name, 'codeql')
        log_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = self.proj.cache(proj_name, None)
        cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            result_dir = self.proj.cache_query_result(proj_name, query)
            result_file = result_dir / f"repo_{source_name}.csv"
            if result_file.exists():
                info("query result already exists, skip running", result_file=result_file)
                return
            query.run(
                db_path=db_path,
                log_dir=log_dir,
                cache_dir=cache_dir,
                result_path=result_file,
                query_name=f"{proj_name}_{source_name}",
                disable_cache=False,
            )
        except AssertionError as e:
            warn("failed to run CodeQL query for source", source=source_name, error=e)

    def merge_query_result(self, proj_name, query: codeql.Query, result_path: Path) -> None:
        info("merge CodeQL query results of all source repo for query", query=query)

        with result_path.open('w') as result_file:
            # 写入表头
            result_file.write(','.join(
                ['source_name'] + query.result_cols
            ) + '\n')
            # 合并结果
            for source in self.proj.sources(proj_name):
                result_dir = self.proj.cache_query_result(proj_name, query)
                source_result_path = result_dir / f"repo_{source.name}.csv"
                if not source_result_path.exists():
                    # 命令执行出错导致没有结果，之前已经报过错了
                    continue
                with source_result_path.open() as source_result_file:
                    next(source_result_file)
                    for line in source_result_file:
                        # 增加一列 source
                        line = f"{source.name},{line}"
                        result_file.write(line)


if __name__ == '__main__':
    from pprint import pprint

    proj_root = ProjectFolder(Path('/Users/kaaass/Project/research/k8s/projs'))
    acs = ApiCallScanner(proj_root)
    acs.build_db('chaos-mesh')
    css = acs.scan('chaos-mesh')
    pprint(css)

    perms = {cs.to_permission() for cs in css}
    pprint(perms)
