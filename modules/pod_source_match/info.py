# info.py -- 收集 Pod 信息和源码信息
#
# Copyright (C) 2024 KAAAsS
import csv
from pathlib import Path
from typing import NamedTuple, Generator

from analyse.k8s.basic import ObjectStore
from analyse.k8s.workload import ContainerCarrier, Container
from modules.pod_source_match.executable_extractor import ExecutableExtractor
from modules.storage import ProjectFolder, FILENAME_CODEQL_ENTRYPOINTS
from utils import docker_image, binary_utils
from utils.log import log_funcs, log_ctx

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

_BAD_IMAGE_FILE = Path(__file__).parent.parent / 'special_rules' / 'bad_image.txt'
_BAD_IMAGES = set(_BAD_IMAGE_FILE.read_text().splitlines())


class PodInfo:
    """从配置中抽取的 Pod 信息"""

    class ContainerInfo:
        def __init__(self, container: Container, cache_dir=None):
            self._container = container
            self._cache_dir = cache_dir
            self.name = container.name
            self.image = container.image
            _, image_repo_name, _ = docker_image.parse_image_ref(self.image)
            self.image_name = image_repo_name.split('/')[-1]
            self.all_executables = None
            self.extracted_executables = None

            self._cached_commands = None
            self._cached_executable_name = None

        @property
        def command(self) -> list[str]:
            if self._cached_commands is None:
                self._cached_commands = self._container.resolve_full_command(inspect_image=True,
                                                                             cache_dir=self._cache_dir)
            return self._cached_commands

        @property
        def executable_name(self) -> str:
            if self._cached_executable_name is None and self.image not in _BAD_IMAGES:
                self._cached_executable_name = self._container.resolve_executable_name(inspect_image=True,
                                                                                       cache_dir=self._cache_dir)
            return self._cached_executable_name

        def extract_all_executables(self, cache_dir: Path, remove_image=False):
            """抽取容器可能调用的所有可执行文件"""
            all_executables = []
            extracted_executables = []

            if self.image in _BAD_IMAGES:
                info('bad image, skip extracting executables', image_ref=self.image)
                return []
            debug('extracting all executables', image_ref=self.image, command=self.command)
            all_envs = self._container.resolve_all_envs()
            extractor = ExecutableExtractor(self.image, self.command, all_envs, remove_image=remove_image)
            results = extractor.extract_to(to_dir=cache_dir, cache_dir=cache_dir)
            for result in results:
                if result.container_path:
                    all_executables.append(result.container_path)
                else:
                    all_executables.append(result.script_reference)
                if result.saved_path:
                    extracted_executables.append(result.saved_path)
                    binary_utils.upx_decompress(result.saved_path)

            self.all_executables = all_executables
            self.extracted_executables = extracted_executables
            debug('all executables extracted', executables=all_executables)
            return all_executables

        def __repr__(self):
            return f'ContainerInfo(name={self.name}, image={self.image_name}, command={self.command})'

    def __init__(self, pod: ContainerCarrier, cache_dir=None):
        self._pod = pod
        self.pod_name: str = pod.name
        self.containers = [self.ContainerInfo(c, cache_dir) for c in pod.containers()]
        self._cache_dir = cache_dir

    def get_pod(self):
        return self._pod

    def extract_all_executables(self, remove_image=False):
        cache_dir = self._cache_dir / 'executables' / self.pod_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        with log_ctx(pod=self.pod_name):
            for container in self.containers:
                with log_ctx(container=container.name):
                    container.extract_all_executables(cache_dir, remove_image=remove_image)

    def __repr__(self):
        return f'PodInfo(pod_name={self.pod_name}, containers={self.containers})'

    def __hash__(self):
        return hash(self._pod)

    def dict(self):
        return {
            'pod_name': self.pod_name,
            'container_name': [c.name for c in self.containers],
            'container_image': [c.image for c in self.containers],
            'container_command': [' '.join(c.command) for c in self.containers],
            'container_executable': [c.all_executables for c in self.containers],
        }


class ProgramEntrypointInfo(NamedTuple):
    """从源码中抽取的程序入口信息"""
    source_name: str
    main_file_path: Path
    package_path: str

    def dict(self):
        return {
            'source_name': self.source_name,
            'main_file_path': self.main_file_path,
            'package_path': self.package_path,
        }


def extract_program_entrypoints(proj: ProjectFolder, proj_name) -> Generator[ProgramEntrypointInfo, None, None]:
    """从程序分析的结果中抽取项目程序入口信息"""
    result_path = proj.cache(proj_name, FILENAME_CODEQL_ENTRYPOINTS)

    with result_path.open() as result_file:
        reader = csv.DictReader(result_file)
        for row in reader:
            yield ProgramEntrypointInfo(row['source_name'], Path(row['file']), row['package'])


def extract_pod_info(store: ObjectStore, cache_dir=None) -> Generator[PodInfo, None, None]:
    for pod in store:
        if not isinstance(pod, ContainerCarrier):
            continue
        yield PodInfo(pod, cache_dir)
