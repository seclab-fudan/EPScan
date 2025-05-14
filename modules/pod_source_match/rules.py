# rules.py -- 若干匹配的启发式规则
#
# Copyright (C) 2024 KAAAsS
import platform
import re
import subprocess
from typing import NamedTuple, Callable, Reversible, Optional

from modules.pod_source_match.info import PodInfo, ProgramEntrypointInfo
from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)


class MatchingContext(NamedTuple):
    project: str


class MatchingRule(NamedTuple):
    """启发式匹配规则"""
    name: str
    rule_func: Optional[Callable[[MatchingContext, PodInfo, ProgramEntrypointInfo], bool]]


def rule_source_exe_is_pod_name(ctx: MatchingContext, pod_info: PodInfo, source_info: ProgramEntrypointInfo) -> bool:
    keywords = set()
    append_filename_keywords(keywords, ctx, source_info)
    append_package_keywords(keywords, ctx, source_info)
    return pod_info.pod_name in keywords


def rule_source_exe_is_container_name(ctx: MatchingContext, pod_info: PodInfo,
                                      source_info: ProgramEntrypointInfo) -> bool:
    keywords = set()
    append_filename_keywords(keywords, ctx, source_info)
    append_package_keywords(keywords, ctx, source_info)
    return any(c.name in keywords for c in pod_info.containers)


def rule_source_exe_match_extracted_exe_name(ctx: MatchingContext, pod_info: PodInfo,
                                             source_info: ProgramEntrypointInfo) -> bool:
    keywords = set()
    append_filename_keywords(keywords, ctx, source_info)
    append_package_keywords(keywords, ctx, source_info)

    for container in pod_info.containers:
        if container.all_executables:
            for exe in container.all_executables:
                exe_name = get_last_nontrivial_part(exe.parts)
                if exe_name in keywords:
                    return True

    return False


_IS_LINUX = platform.system() == 'Linux'

REG_EXECUTABLE = re.compile(r'(?:^|/)([^/\s]+)(?=\s|$)')


def check_extracted_exe_contain_source_code_path(pod_info: PodInfo,
                                                 source_info: list[ProgramEntrypointInfo],
                                                 disable_llm_extraction=False) -> list[ProgramEntrypointInfo]:
    # 要匹配的 Exe
    exes = []

    for c in pod_info.containers:
        for exe in c.extracted_executables:
            if disable_llm_extraction:
                # 如果要屏蔽 LLM 解析，则使用正则
                commands = c.command
                if not commands:
                    continue
                cmd = ' '.join(commands)
                m = REG_EXECUTABLE.search(cmd)
                if not m:
                    continue
                if exe.name != m.group(1):
                    continue
            exes.append(exe)
    if not exes:
        return exes

    # 拼接源代码正则
    min_len = min(map(lambda s: len(str(s.main_file_path)), source_info))
    reg_files = '|'.join(map(lambda s: re.escape(str(s.main_file_path)), source_info))
    reg_sources = f'({reg_files})'
    reg_sources = re.compile(reg_sources)

    # 使用 strings 检查
    cmds = [
        'strings',
        '-n', str(min_len),
    ]
    if _IS_LINUX:
        # 只考虑 data 中的元数据，macOS 默认的 strings 不支持这个选项
        cmds.append('-d')
    cmds.extend(exes)

    matched_paths = set()

    try:
        debug('start matching symbols', cmds=cmds, regex=reg_sources)
        proc = subprocess.Popen(cmds, stdout=subprocess.PIPE)
        for raw_line in proc.stdout:
            line = raw_line.decode('utf-8').strip()
            matched = reg_sources.search(line)
            if matched:
                matched_paths.add(matched.group(1))

        return [s for s in source_info if s.package_path in matched_paths or str(s.main_file_path) in matched_paths]
    except Exception as e:
        warn('failed to run strings for extracted executables', cmds=cmds, exc_info=e)
    return []


MATCHING_RULES_EXECUTABLE = [
    MatchingRule('source_exe_is_pod_name', rule_source_exe_is_pod_name),
    MatchingRule('source_exe_is_container_name', rule_source_exe_is_container_name),
    MatchingRule('source_exe_match_extracted_exe_name', rule_source_exe_match_extracted_exe_name),
]


def get_last_nontrivial_part(parts: Reversible[str]) -> Optional[str]:
    for stem in reversed(parts):
        if stem.endswith('.go'):
            continue
        if stem not in ('main', 'cmd', 'src', 'internal', 'pkg', 'api', 'apis', 'types', 'util', 'utils', 'common'):
            return stem
    return None


def append_filename_keywords(keywords: set[str], ctx: MatchingContext, source_info: ProgramEntrypointInfo):
    """从文件名猜测 Exe 名"""
    source_exe = get_last_nontrivial_part(source_info.main_file_path.parts)
    if source_exe is not None:
        keywords.add(source_exe)
        keywords.add(f'{ctx.project}-{source_exe}')
        keywords.add(f'{ctx.project}_{source_exe}')


def append_package_keywords(keywords: set[str], ctx: MatchingContext, source_info: ProgramEntrypointInfo):
    """从包名猜测 Exe 名"""
    source_exe = get_last_nontrivial_part(source_info.package_path.split('/'))
    if source_exe is not None:
        keywords.add(source_exe)
        keywords.add(f'{ctx.project}-{source_exe}')
        keywords.add(f'{ctx.project}_{source_exe}')
