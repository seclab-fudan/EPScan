# codeql.py -- 执行 CodeQL 查询
#
# Copyright (C) 2024 Tanxin
# Copyright (C) 2024 KAAAsS

import os
import subprocess
import time
from pathlib import Path
from typing import NamedTuple

from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

QUERIES_DIR = Path(__file__).parent / "queries"

# CodeQL configs
CODEQL_THREAD_NUM = 0  # Core 数
CODEQL_RAM = 102400
CODEQL_BINARY = "codeql"


class Query(NamedTuple):
    name: str
    version: int
    path: Path
    result_cols: list[str]

    @property
    def identifier(self):
        return f"{self.name}_v{self.version}"

    def run(self, *args, **kwargs):
        run_query(self, *args, **kwargs)

    def __repr__(self):
        return f'<Query name={self.name} version={self.version} path={self.path}>'


# 内置的查询
QUERY_REACHABLE_API_CALLS = Query(
    name="reachable_api_calls",
    version=130,
    path=QUERIES_DIR / "reachable_api_calls.ql",
    result_cols=['entrypoint', 'parent', 'resource_type', 'verb', 'location']
)
QUERY_API_CALLS = Query(
    name="api_calls",
    version=130,
    path=QUERIES_DIR / "api_calls.ql",
    result_cols=['name', 'api_type', 'parent', 'resource_type', 'verb', 'location']
)
QUERY_ENTRYPOINTS = Query(
    name="entrypoints",
    version=100,
    path=QUERIES_DIR / "entrypoints.ql",
    result_cols=['file', 'line_no', 'package']
)
QUERY_CANDIDATE_API_CALLS = Query(
    name="candidate_api_calls",
    version=130,
    path=QUERIES_DIR / "candidate_api_calls.ql",
    result_cols=['name', 'api_type', 'parent', 'type_hint', 'verb', 'location']
)
QUERY_ALL_SDK_CALLS = Query(
    name="all_sdk_calls",
    version=100,
    path=QUERIES_DIR / "all_sdk_calls.ql",
    result_cols=['full_name', 'package', 'name']
)


def run_query(
        query: Query,
        db_path: Path,
        log_dir: Path,
        cache_dir: Path,
        result_path: Path,
        disable_cache: bool = False,
        query_name: str = '',
):
    """执行 CodeQL 查询"""
    log_codeql = log_dir / f"run_{query.identifier}_{query_name}.log"
    log_decode = log_dir / f"decode_{query.identifier}_{query_name}.log"
    bqrs = cache_dir / f"result_{query.identifier}_{query_name}.bqrs"
    start = time.time()

    # 检查 DB 是否存在
    go_db = db_path / "db-go"
    assert go_db.exists(), f"CodeQL DB {go_db} not found"

    if not bqrs.exists() or disable_cache:
        cmd = [
            CODEQL_BINARY,
            "query",
            "run",
            f"--database={db_path}",
            f"--output={bqrs}",
            f"--threads={CODEQL_THREAD_NUM}",
            f"--ram={CODEQL_RAM}",
            "--",
            str(query.path),
            f"> {log_codeql}",
            "2>&1",
        ]
        cmd = " ".join(cmd)
        debug("exec cmd", cmd=cmd)
        assert os.system(cmd) == 0
    else:
        info("Query result already exists, use cache", bqrs=bqrs)

    cmd = [
        CODEQL_BINARY,
        "bqrs",
        "decode",
        str(bqrs),
        "--format=csv",
        f"--output={result_path}",
        f"> {log_decode}",
        "2>&1",
    ]
    cmd = " ".join(cmd)
    debug("exec cmd", cmd=cmd)
    assert os.system(cmd) == 0

    end = time.time()
    info("query end",
         query=query,
         db_path=db_path,
         result_path=result_path,
         elapsed=end - start
         )

    # 去除结果中的源码路径前缀
    source_prefix = get_db_source_prefix(db_path)
    with open(result_path) as f:
        lines = f.readlines()
    with open(result_path, "w") as f:
        for line in lines:
            f.write(line.replace(f'{source_prefix}/', ""))
    debug("remove source prefix in db", source_prefix=source_prefix)


def get_db_source_prefix(db_path: Path) -> Path:
    """获取 CodeQL DB 的源码前缀"""
    assert db_path.is_dir(), f"{db_path} is not a directory"
    with open(db_path / "codeql-database.yml") as f:
        for line in f:
            if line.startswith("sourceLocationPrefix:"):
                return Path(line.split(":")[1].strip())
    raise ValueError(f"sourceLocationPrefix not found in {db_path}")


def build_db(source_path: Path, dest_path: Path, log_path: Path):
    """构建 CodeQL 数据库"""
    assert source_path.is_dir(), f"{source_path} is not a directory"
    assert not dest_path.exists(), f"{dest_path} already exists"
    start = time.time()
    cmd = [
        CODEQL_BINARY,
        "database",
        "create",
        str(dest_path),
        "--language=go",
        f"--source-root={source_path}",
        f"--threads={CODEQL_THREAD_NUM}",
        f"> {log_path}",
        "2>&1",
    ]
    cmd = " ".join(cmd)
    debug("exec cmd", cmd=cmd)
    assert os.system(cmd) == 0
    end = time.time()
    info("build CodeQL DB finished", source_path=source_path, dest_path=dest_path, elapsed=end - start)


_MARK_FILE = '.codeql_prepared'


def prepare_queries():
    """准备 CodeQL 查询"""

    mark_file = QUERIES_DIR / _MARK_FILE
    if mark_file.exists():
        info("CodeQL env already prepared")
        return
    cmd = [
        CODEQL_BINARY,
        "pack",
        "install",
    ]
    ret = subprocess.check_call(cmd, cwd=QUERIES_DIR)
    assert ret == 0
    mark_file.touch()
