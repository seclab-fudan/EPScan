# workload.py -- 实现工作负载对象
#
# Copyright (C) 2024 KAAAsS
import typing
from pathlib import PurePosixPath

from tinydb.queries import Query

from analyse.k8s.basic import Object
from analyse.k8s.rbac import ServiceAccount, get_service_account_by_name
from utils import docker_image
from utils.log import log_funcs

ContainerType = typing.Literal['InitContainer', 'Container', 'EphemeralContainer']
INIT_CONTAINER: ContainerType = 'InitContainer'
CONTAINER: ContainerType = 'Container'
EPHEMERAL_CONTAINER: ContainerType = 'EphemeralContainer'

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

WORKLOAD_KINDS = 'Pod', 'Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob', 'ReplicaSet'
WORKLOAD_RESOURCES = 'pods', 'deployments', 'statefulsets', 'daemonsets', 'jobs', 'cronjobs', 'replicasets'


class Container:
    def __init__(self, typ: ContainerType, data: dict):
        self.type = typ
        self.data = data

    def __repr__(self):
        return f'{self.type}({self.data})'

    @property
    def name(self) -> str:
        return self.data['name']

    @property
    def image(self) -> str:
        return self.data['image']

    @property
    def command(self) -> typing.Optional[list[str]]:
        return self.data.get('command', None)

    @property
    def args(self) -> typing.Optional[list[str]]:
        return self.data.get('args', None)

    def resolve_full_command(self, inspect_image=False, cache_dir=None) -> list[str]:
        """
        解析容器运行的完整命令行
        :param inspect_image: 是否需要检查镜像以解析命令
        :param cache_dir: 缓存目录
        """
        command = self.command
        if command is None:
            if not inspect_image:
                raise ValueError('Command not explicitly defined, need inspect_image=True to resolve')
            # 从 Image 中解析命令
            command = self._resolve_command_from_image(cache_dir=cache_dir)
            if not command:
                warn('no command found in image', container=self)
            info('resolved command from image', container=self, command=command)
        return command + (self.args or [])

    def resolve_executable_name(self, inspect_image=False, cache_dir=None) -> typing.Optional[str]:
        """
        解析容器运行的可执行文件名
        :param inspect_image: 是否需要检查镜像以解析命令
        """
        commands = self.resolve_full_command(inspect_image, cache_dir=cache_dir)
        if not commands:
            warn('no command found', container=self)
            return None

        # tini 特殊处理
        if commands[0].endswith('/tini'):
            # 寻找第一个 '--'
            real_cmd_idx = 1
            for i, cmd in enumerate(commands[1:], 1):
                if cmd == '--':
                    real_cmd_idx = i + 1
                    break
            debug('meet tini command', commands=commands, real_cmd_idx=real_cmd_idx)
            commands = commands[real_cmd_idx:]

        executable_path = PurePosixPath(commands[0])

        if executable_path.name.endswith('.sh'):
            debug(f'Executable name ends with .sh, need llm to resolve', exe_name=executable_path.name)

        return executable_path.name

    def resolve_all_envs(self, cache_dir=None) -> dict[str, str]:
        """解析运行时使用的环境变量"""
        envs = {}

        # 先从镜像配置获得环境变量
        config = self._get_image_config(cache_dir=cache_dir)
        if config is not None:
            conf_envs = config.get('config', {}).get('Env', [])
            for env in conf_envs:
                key, value = env.split('=', 1)
                envs[key] = value

        # 然后从配置中读取覆盖的环境变量
        for env in self.data.get('env', []):
            if 'value' not in env:
                continue
            envs[env['name']] = env['value']

        return envs

    def _resolve_command_from_image(self, cache_dir=None) -> list[str]:
        # 获得镜像配置
        debug('start resolving command from image', image=self.image)
        config = self._get_image_config(cache_dir=cache_dir)
        if config is None:
            return []
        debug('got image config', image=self.image)

        # 解析命令
        entrypoint = config.get('config', {}).get('Entrypoint', [])
        if entrypoint is None:
            entrypoint = []
        cmd = config.get('config', {}).get('Cmd', [])
        if cmd is None:
            cmd = []

        return entrypoint + cmd

    def _get_image_config(self, cache_dir=None):
        image_ref = docker_image.parse_image_ref(self.image)
        debug('resolving image config', image_ref=image_ref)
        return docker_image.get_image_config(*image_ref, cache_dir=cache_dir)


class ContainerCarrier(Object):

    def containers(self) -> typing.Iterable[Container]:
        raise NotImplementedError

    @property
    def sa_name(self) -> str:
        raise NotImplementedError

    def get_sa(self) -> ServiceAccount:
        return get_service_account_by_name(self.store, self.sa_name)


class Pod(ContainerCarrier):
    @staticmethod
    def from_dict(data: dict):
        if data['kind'] != 'Pod':
            return None
        return Pod(data)

    def containers(self):
        for container in self.data['spec']['containers']:
            yield Container(CONTAINER, container)
        for container in self.data['spec'].get('initContainers', None) or []:
            yield Container(INIT_CONTAINER, container)
        for container in self.data['spec'].get('ephemeralContainers', None) or []:
            yield Container(EPHEMERAL_CONTAINER, container)

    @property
    def sa_name(self) -> str:
        return _get_sa_from_pod_spec(self.data['spec'])


class Workload(ContainerCarrier):
    """所有工作负载对象的公共基类"""

    @staticmethod
    def from_dict(data: dict):
        if data['kind'] not in ('Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob', 'ReplicaSet'):
            if 'template' in data.get('spec', {}):
                warn(f'Unknown workload kind: {data["kind"]}')
            return None
        return Workload(data)

    def get_pod_template(self):
        if self.kind == 'CronJob':
            return self.data['spec']['jobTemplate']['spec']['template']
        else:
            return self.data['spec']['template']

    def containers(self):
        templateSpec = self.get_pod_template()['spec']
        for container in templateSpec['containers']:
            yield Container(CONTAINER, container)
        for container in templateSpec.get('initContainers', None) or []:
            yield Container(INIT_CONTAINER, container)
        for container in templateSpec.get('ephemeralContainers', None) or []:
            yield Container(EPHEMERAL_CONTAINER, container)

    @property
    def sa_name(self) -> str:
        return _get_sa_from_pod_spec(self.get_pod_template()['spec'])


def _get_sa_from_pod_spec(spec: dict) -> str:
    sa_name = spec.get('serviceAccountName', None)
    if sa_name is None:
        sa_name = spec.get('serviceAccount', None)
    if not sa_name:
        sa_name = 'default'
    return sa_name


def find_pods_by_service_account(store, service_account_name) -> list[Pod]:
    """根据 ServiceAccount 查找关联的 Pod"""
    return store.search(
        Query().spec.serviceAccountName == service_account_name
    )


def find_workloads_by_service_account(store, service_account_name) -> list[Workload]:
    """根据 ServiceAccount 查找关联的 Workload"""
    return store.search(
        Query().spec.template.spec.serviceAccountName == service_account_name
    )


def _test():
    from analyse.k8s.basic import ObjectStore
    from pathlib import Path
    store = ObjectStore.from_config_dir(Path('/Users/kaaass/Project/research/k8s/data/small_dataset/cncf/crossplane'))
    sa = 'crossplane'

    print(ret := find_pods_by_service_account(store, sa))
    assert len(ret) == 0

    print(ret := find_workloads_by_service_account(store, sa))
    assert len(ret) == 1

    for workload in ret:
        print('Workload:', workload)
        for container in workload.containers():
            print('  ', container)
            print('     Image:', container.image)
            print('     Command:', container.command)
            print('     Args:', container.args)


if __name__ == '__main__':
    _test()
