# source_download.py -- 源码下载模块
#
# Copyright (C) 2024 KAAAsS
import shutil
import subprocess
from pathlib import Path

from modules.storage import ProjectFolder
from modules.types import RemoteRepository, SourceCode
from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

GIT_BINARY = 'git'


def download_repository(repo: RemoteRepository, dest: Path) -> None:
    """下载源代码仓库"""
    repo_url = repo.url
    tag = repo.tag
    commit_hash = repo.commit_hash
    assert tag or commit_hash, 'tag or commit_hash must be specified'

    info('download repository', repo_url=repo_url, tag=tag, commit_hash=commit_hash, dest=dest)

    # Clone 仓库
    repo_url = repo_url.rstrip('/')
    repo_url = f'{repo_url}.git' if not repo_url.endswith('.git') else repo_url
    cmd = [GIT_BINARY, 'clone']
    if tag:
        cmd.extend(['--branch', tag, '--depth', '1'])
    cmd.extend([repo_url, str(dest)])
    debug('run command', cmd=cmd)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Checkout 指定 commit
    if commit_hash:
        cmd = [GIT_BINARY, '-C', dest, 'reset', '--hard', commit_hash]
        debug('run command', cmd=cmd)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def download_project_source(proj: ProjectFolder, proj_name: str, repo: RemoteRepository) -> SourceCode:
    """下载源代码仓库到本地"""
    repo_name = Path(repo.url).stem
    source_path = proj.source(proj_name, repo_name, no_check=True)
    source = SourceCode(repo_name, repo, source_path)

    # 检查缓存
    should_download = True

    if source_path.exists():
        if check_source_version(source):
            info('source code already exists', source_path=source_path)
            should_download = False
        else:
            info('source code exists but version mismatch, re-download', source_path=source_path)
            shutil.rmtree(source_path)

            # 检查 DB
            db_path = proj.db(proj_name, repo_name)
            if db_path.exists():
                if input('DB cache exists, delete? [y/N] ').lower() == 'y':
                    shutil.rmtree(db_path)

    if should_download:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        download_repository(repo, source_path)

    return source


def check_source_version(source: SourceCode) -> bool:
    """检查源代码版本是否匹配"""
    if not source.remote_repo:
        return True

    expected_hash = None

    # 检查 Tag
    if source.remote_repo.tag:
        cmd = [GIT_BINARY, '-C', source.local_path, 'rev-parse', f'{source.remote_repo.tag}^{{}}']
        debug('run command', cmd=cmd)
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            warn('failed to get tag hash', tag=source.remote_repo.tag)
            return False
        expected_hash = result.stdout.strip().decode()
        debug('source tag commit hash', tag=source.remote_repo.tag, hash=expected_hash)

    # 检查 Commit
    if source.remote_repo.commit_hash:
        if expected_hash is not None and source.remote_repo.commit_hash != expected_hash:
            warn('tag hash and commit hash mismatch', tag=source.remote_repo.tag, commit_hash=source.remote_repo.commit_hash)
            return False
        expected_hash = source.remote_repo.commit_hash

    # 检查 HEAD
    cmd = [GIT_BINARY, '-C', source.local_path, 'rev-parse', 'HEAD']
    debug('run command', cmd=cmd)
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    actual_hash = result.stdout.strip().decode()

    debug('compare commit hash', expected_hash=expected_hash, actual_hash=actual_hash)
    return actual_hash == expected_hash


if __name__ == '__main__':
    repo = RemoteRepository('https://github.com/argoproj/argo-cd', 'v2.9.5', None)
    download_repository(repo, Path('test'))
