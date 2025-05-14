# executable_extractor.py -- 提取镜像运行的可执行文件
#
# Copyright (C) 2024 KAAAsS
import hashlib
import json
import re
import tempfile
from pathlib import PurePath, Path
from typing import NamedTuple, Optional

import yaml

from utils import openai_helper
from utils.docker_image import DockerImageExtractor
from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

Script = tuple[PurePath, str]


class ExecutableResult(NamedTuple):
    script_reference: PurePath
    container_path: Optional[PurePath]
    saved_path: Optional[Path]

    def to_dict(self, base_dir: Path):
        return {
            "script_reference": str(self.script_reference),
            "container_path": str(self.container_path) if self.container_path else None,
            "saved_path": str(self.saved_path.relative_to(base_dir)) if self.saved_path else None
        }

    @staticmethod
    def from_dict(data: dict, base_dir: Path):
        return ExecutableResult(
            PurePath(data["script_reference"]),
            PurePath(data["container_path"]) if data["container_path"] else None,
            base_dir / data["saved_path"] if data["saved_path"] else None
        )


class ExecutableExtractor:
    """从镜像中提取运行的可执行文件"""

    def __init__(self, image_ref: str, commands: list[str], all_envs: dict[str, str], remove_image=False):
        """
        :param image_ref:
        :param commands:
        :param all_envs: 全部环境变量，包括镜像指定的
        :param remove_image:
        """
        self.image_ref = image_ref
        self.commands = commands
        self.all_envs = all_envs
        self.remove_image = remove_image

    def extract_to(self, to_dir: Path, cache_dir=None) -> list[ExecutableResult]:
        cache_file = None

        if cache_dir:
            identifier = self.image_ref + ':' + ' '.join(self.commands)
            identifier = hashlib.sha1(identifier.encode()).hexdigest()
            cache_file = cache_dir / f"exe_extract_{identifier}.json"
            if cache_file.exists():
                debug("loading cache", cache_file=cache_file)
                return self._load_cache(cache_file)

        try:
            results = self._extract_no_cache(to_dir)
        except Exception as e:
            error("failed to extract executables", exc_info=e, image_ref=self.image_ref, commands=self.commands)
            return []

        if cache_dir:
            self._save_cache(cache_file, results)

        return results

    def _extract_no_cache(self, to_dir: Path) -> list[ExecutableResult]:
        results = []

        with DockerImageExtractor(self.image_ref, remove_image_at_close=self.remove_image) as die:
            # 提取脚本并渲染为 Prompt
            try:
                image_info = ImageRunInfo(die, self.commands, self.all_envs, script_save_dir=to_dir)
                image_info.extract_scripts()
            except Exception as e:
                error("failed to extract image info", exc_info=e, image_ref=self.image_ref, commands=self.commands)
                return results

            paths = []
            paths.extend(self._list_paths_by_llm(image_info))
            paths.extend(self._list_paths_by_rules(image_info))
            paths = list(set(paths))
            debug("got all executable paths", paths=paths)

            # 从镜像中提取所有可执行文件
            for exe_path in paths:
                result = ExecutableResult(exe_path, None, None)

                try:
                    # 解析镜像内的绝对路径
                    resolved_path = die.resolve_executable_path(exe_path)
                    result = result._replace(container_path=resolved_path)

                    # 提取文件
                    with die.extract_file(resolved_path) as f:
                        dest_path = to_dir / exe_path.name
                        with dest_path.open('wb') as dest:
                            dest.write(f.read())
                    result = result._replace(saved_path=dest_path)
                    debug("extracted executable", exe_path=exe_path, resolved_path=resolved_path, dest_path=dest_path)
                except Exception as e:
                    error("failed to extract executable", exc_info=e, exe_path=exe_path)

                results.append(result)

        return results

    def _list_paths_by_llm(self, image_info: 'ImageRunInfo') -> list[PurePath]:
        prompt = render_resolve_prompt(image_info)
        paths = openai_helper.completion_with_type(prompt, resp_type=list, temperature=0.6)
        debug("got executables paths from llm", paths=paths)
        return [PurePath(p) for p in paths]

    def _list_paths_by_rules(self, image_info: 'ImageRunInfo') -> list[PurePath]:
        paths = []

        # 入口命令
        commands = image_info.commands
        if not commands[0].endswith('sh'):
            paths.append(commands[0])

        return [PurePath(p) for p in paths]

    def _load_cache(self, cache_file: Path) -> list[ExecutableResult]:
        with cache_file.open('r') as f:
            data = json.load(f)
        return [ExecutableResult.from_dict(r, cache_file.parent) for r in data["results"]]

    def _save_cache(self, cache_file, results: list[ExecutableResult]):
        data = {
            "image_ref": self.image_ref,
            "commands": self.commands,
            "results": [r.to_dict(cache_file.parent) for r in results]
        }
        with cache_file.open('w') as f:
            json.dump(data, f)


class ImageRunInfo:
    """镜像运行信息"""

    def __init__(self, extractor: DockerImageExtractor, commands: list[str], all_envs: dict[str, str],
                 script_save_dir: Optional[Path] = None):
        self.extractor = extractor
        self.commands = commands
        self._all_envs = all_envs
        self._script_save_dir = script_save_dir
        self._cached_scripts: list[Script] = None

    @property
    def entrypoint(self) -> str:
        """获取镜像的入口命令"""
        return ' '.join(self.commands)

    @property
    def scripts(self) -> list[Script]:
        """获取镜像运行的脚本"""
        if not self._cached_scripts:
            self.extract_scripts()
        return self._cached_scripts

    @property
    def all_envs(self) -> dict[str, str]:
        """获取镜像配置的所有环境变量"""
        return self._all_envs

    def extract_scripts(self):
        paths = list_scripts_path_in_script(self.entrypoint)
        scripts = []

        if len(paths) > 0:
            for path in paths:
                path = self.extractor.resolve_executable_path(path)
                with self.extractor.extract_file(path) as f:
                    scripts_content = f.read().decode()
                    scripts.append((path, scripts_content))
                    if self._script_save_dir:
                        with (self._script_save_dir / path.name).open('w') as dest:
                            dest.write(scripts_content)

        self._cached_scripts = scripts


_PROMPT_TEMPLATE_FILE = Path(__file__).parent / 'prompt_template.yaml'
_PROMPT_TEMPLATE: dict = {}


def render_resolve_prompt(info: ImageRunInfo) -> list[dict]:
    """将镜像运行信息渲染为 LLM 解析的提示词"""
    history = []

    def write_query(entrypoint, scripts, all_envs) -> dict:
        query = f"Start up scripts: \n```shell\n{entrypoint}\n```\n\n"
        for script in scripts:
            query += f"Script file \"{script[0]}\": \n```shell\n{script[1]}\n```\n\n"

        # 寻找使用的环境变量
        envs = filter_envs(entrypoint, all_envs)
        if envs:
            query += "Environment variables: \n"
            for k, v in envs.items():
                query += f"- {k}: {v}\n"
            query += "\n"
        return {
            "role": "user",
            "content": query,
        }

    def write_answer(paths) -> dict:
        return {
            "role": "assistant",
            "content": json.dumps(paths),
        }

    # 载入 prompt 模板
    if not _PROMPT_TEMPLATE:
        with _PROMPT_TEMPLATE_FILE.open('r') as f:
            _PROMPT_TEMPLATE.update(yaml.safe_load(f))

    # System 部分
    history.append({
        "role": "system",
        "content": _PROMPT_TEMPLATE["system"]
    })

    # Few-shot 示例
    for example in _PROMPT_TEMPLATE["examples"]:
        query = example["query"]
        answer = example["answer"]
        history.append(write_query(query["entrypoint"], query["scripts"], query["all_envs"]))
        history.append(write_answer(answer))

    # 实际查询
    history.append(write_query(info.entrypoint, info.scripts, info.all_envs))

    return history


def list_scripts_path_in_script(script: str) -> list[PurePath]:
    """列出脚本中提及的脚本路径"""
    REG_SCRIPT_PATH = r'([^ ]+\.sh)'
    return [PurePath(match.group(1)) for match in re.finditer(REG_SCRIPT_PATH, script)]


def filter_envs(scripts: str, envs: dict[str, str]):
    """从脚本中提取使用的环境变量"""
    used_envs = {}
    if envs:
        for k, v in envs.items():
            if k in scripts:
                used_envs[k] = v
    return used_envs


def _test():
    # image = 'docker.io/emissaryingress/emissary:3.9.1'
    # commands = ['bash', '/buildroot/ambassador/python/entrypoint.sh']
    #
    # # with DockerImageExtractor(image) as extractor:
    # #     info = ImageRunInfo(extractor, commands)
    # #     print(info.entrypoint)
    # #     print(info.scripts)
    #
    # result_dir = Path(tempfile.gettempdir()) / 'exe_extract'
    # result_dir.mkdir(exist_ok=True)
    # result = ExecutableExtractor(image, commands, {}).extract_to(result_dir, cache_dir=result_dir)
    # print(result)
    # print(list(result_dir.glob('*')))

    image = 'docker.io/networkservicemesh/nsmdp:master'
    commands = ['/bin/sh', '-c', '/bin/${ENTRY}']
    all_envs = {
        'ENTRY': 'nsmdp',
    }

    with tempfile.TemporaryDirectory() as td:
        result_dir = Path(td) / 'exe_extract'
        result_dir.mkdir(exist_ok=True)
        result = ExecutableExtractor(image, commands, all_envs).extract_to(result_dir, cache_dir=result_dir)
        print(result)
        print(list(result_dir.glob('*')))


if __name__ == '__main__':
    _test()
