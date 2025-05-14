import json
import tarfile
import tempfile
from pathlib import PurePath, Path
from typing import Optional, IO

import docker
import dxf

from utils.log import log_funcs

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

PAUSE_IMAGE = 'rancher/pause:3.2'
PAUSE_BIN = Path(__file__).parent / 'pause'
BUSYBOX_IMAGE = 'busybox:stable-uclibc'
BUSYBOX_BIN = Path(__file__).parent / 'busybox'


class DockerImageExtractor:
    """Docker 镜像文件抽取"""

    def __init__(self, image_ref: str, remove_image_at_close=False):
        self.image_ref = image_ref
        self.client = docker.from_env()
        self.image = None
        self.container = None
        self.remove_image_at_close = remove_image_at_close

    def open(self):
        if not PAUSE_BIN.exists():
            download_pause(PAUSE_BIN)
        if not BUSYBOX_BIN.exists():
            download_busybox(BUSYBOX_BIN)

        debug('start pulling image', image_ref=self.image_ref)
        self.image = self.client.images.pull(self.image_ref)
        args = {
            'detach': True,
            'entrypoint': '/pause',
            'mounts': [
                docker.types.Mount(target='/pause', source=str(PAUSE_BIN), type='bind', read_only=True),
                docker.types.Mount(target='/bin/busybox', source=str(BUSYBOX_BIN), type='bind', read_only=True),
            ]
        }
        for attempt in range(2):
            container = None
            try:
                container = self.client.containers.create(self.image, **args)
                container.start()
                break
            except docker.errors.APIError as e:
                # 如果报错就试试不替换 entrypoint
                del args['entrypoint']
                container.remove(force=True)
        else:
            error(f"failed to create container", image_ref=self.image_ref)
            raise e

        self.container = container
        debug('container created', container_id=self.container.id)

    def extract_file(self, src_path: PurePath) -> Optional[IO[bytes]]:
        assert self.container, "container not opened"
        debug('extracting file', src_path=src_path)
        return extract_file_from_container(self.container, src_path)

    def resolve_executable_path(self, path: PurePath) -> Optional[PurePath]:
        # 是否是纯命令名
        if len(path.parts) == 1 and not path.is_absolute():
            commands = [
                f'/bin/busybox which {path}',
            ]

            # 尝试用 working dir 作为寻找路径
            working_dir = self.container.attrs.get('Config', {}).get('WorkingDir', None)
            if working_dir:
                debug('working dir found', working_dir=working_dir)
                commands.append(f'/bin/busybox find {working_dir} -name {path}')

            # 只有命令，尝试通过 which 查找
            for cmd in commands:
                result = self.container.exec_run(cmd)
                if result.exit_code == 0:
                    resolved = result.output.decode().strip()
                    debug('executable resolved', path=path, resolved=resolved)
                    return PurePath(resolved)

        # 否则，暂时不做处理
        return path

    def close(self, remove_image=False):
        if self.container:
            self.container.remove(force=True)
            debug('container removed', container_id=self.container.id)
        if self.image and remove_image:
            self.client.images.remove(self.image.id)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(remove_image=self.remove_image_at_close)


def extract_file_from_container(container, src_path: PurePath) -> Optional[IO[bytes]]:
    for link_count in range(3):
        try:
            data, stat = container.get_archive(str(src_path))
            debug('file stat', stat=stat)
        except docker.errors.NotFound as e:
            error(f"file not found", src_path=src_path, exc_info=e)
            raise FileNotFoundError(src_path)
        if not stat['linkTarget']:
            break
        src_path = PurePath(stat['linkTarget'])
        debug('file is a link', src_path=src_path, link_count=link_count)
    else:
        error(f"too many links", src_path=src_path)
        raise FileNotFoundError(f"too many links {src_path}")

    with tempfile.NamedTemporaryFile() as file:
        for chunk in data:
            file.write(chunk)
        file.seek(0)
        # 解析 tar
        filename = stat['name']
        tar = tarfile.open(file.name)
        member = tar.getmember(filename)
        if member.isreg():
            return tar.extractfile(member)
    error(f"failed to extract file", src_path=src_path)
    raise FileNotFoundError(f"failed to extract file {src_path}")


def download_pause(dest_path: Path):
    """下载 pause 文件到本地"""
    debug('downloading pause file', dest_path=dest_path, image_ref=PAUSE_IMAGE)
    _download_binary_from_image(dest_path, PAUSE_IMAGE, PurePath('/pause'))


def download_busybox(dest_path: Path):
    """下载 busybox 文件到本地"""
    debug('downloading busybox file', dest_path=dest_path, image_ref=BUSYBOX_IMAGE)
    _download_binary_from_image(dest_path, BUSYBOX_IMAGE, PurePath('/bin/busybox'))


def _download_binary_from_image(dest_path: Path, image: str, container_path: PurePath):
    client = docker.from_env()
    image = client.images.pull(image)
    container = None
    try:
        container = client.containers.create(image, detach=True)
        with extract_file_from_container(container, container_path) as f:
            with dest_path.open('wb') as dest:
                dest.write(f.read())
    finally:
        if container:
            container.remove(force=True)

    # 设置 +x
    dest_path.chmod(0o755)


def parse_image_ref(image_ref: str) -> tuple[str, str, str]:
    """
    解析镜像引用
    :param image_ref: 镜像引用
    :return: (host, image_name, tag)
    """
    default_host = 'registry-1.docker.io'
    default_tag = 'latest'

    # 检查主机名
    if '/' in image_ref:
        parts = image_ref.split('/')
        if '.' in parts[0] or ':' in parts[0]:
            # 第一部分是 host
            host = parts.pop(0)
        else:
            host = default_host
        remaining_ref = '/'.join(parts)
    else:
        host = default_host
        remaining_ref = image_ref

    # 检查标签
    if ':' in remaining_ref:
        image_name, tag = remaining_ref.rsplit(':', 1)
    else:
        image_name = remaining_ref
        tag = default_tag

    # 特殊映射规则
    if host == 'docker.io':
        host = default_host

    return host, image_name, tag


def get_image_config(host, image_name, tag, cache_dir=None) -> Optional[dict]:
    # 检查 Cache
    cache_path = None
    if cache_dir:
        file_name = f'{host}_{image_name}_{tag}'.replace('/', '_')
        cache_path = cache_dir / 'images' / f'{file_name}.json'
        if cache_path.exists():
            with cache_path.open('r') as f:
                return json.load(f)

    # 获取镜像配置
    config = None
    try:
        config = _get_image_config_no_cache(host, image_name, tag)
    except Exception as e:
        warn(f"failed to get image config", host=host, image_name=image_name, tag=tag, exc_info=e)
    try:
        if not config:
            config = _get_image_config_by_pull_no_cache(host, image_name, tag)
    except Exception as e:
        warn(f"failed to get image config by pull", host=host, image_name=image_name, tag=tag, exc_info=e)
    if not config:
        return None

    # 写入 Cache
    if cache_dir:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open('w') as f:
            json.dump(config, f)

    return config


def _get_image_config_no_cache(host, image_name, tag):
    d = dxf.DXF(host, image_name, auth=_default_auth)
    config_id = d.get_digest(tag)
    if isinstance(config_id, dict):
        # 在 tag 有多个架构的情况下，返回的是一个字典
        # 此时随便取一个架构的 config_id
        config_id = list(config_id.values())[0]
    blob = d.pull_blob(config_id)
    ret = b''
    for chunk in blob:
        ret += chunk
    return json.loads(ret)


def _get_image_config_by_pull_no_cache(host, image_name, tag):
    client = docker.from_env()
    image = client.images.pull(f'{host}/{image_name}:{tag}')
    try:
        return {"config": image.attrs['Config']}
    finally:
        client.images.remove(image.id)


def _default_auth(dxf, response):
    dxf.authenticate(response=response)


def _test():
    from pprint import pprint
    host, image_name, tag = parse_image_ref('ghcr.io/chaos-mesh/chaos-daemon:v2.6.3')
    print(host, image_name, tag)
    config = get_image_config(host, image_name, tag)
    pprint(config)

    host, image_name, tag = parse_image_ref('quay.io/huawei-cni-genie/genie-admission-controller:latest')
    config = get_image_config(host, image_name, tag)
    pprint(config)

    with DockerImageExtractor('curlimages/curl:latest') as die:
        with die.extract_file(PurePath('/usr/bin/curl')) as f:
            print(f.read()[:50])

    with DockerImageExtractor('docker.io/emissaryingress/emissary:3.9.1') as die:
        print(path := die.resolve_executable_path(PurePath('diagd')))
        with die.extract_file(path) as f:
            print(f.read()[:50])

    with DockerImageExtractor('mcr.microsoft.com/oss/virtual-kubelet/virtual-kubelet:1.6.1') as die:
        print(path := die.resolve_executable_path(PurePath('virtual-kubelet')))
        with die.extract_file(path) as f:
            print(f.read()[:50])

    with DockerImageExtractor('layer5/meshery:stable-latest') as die:
        print(path := die.resolve_executable_path(PurePath('meshery')))
        with die.extract_file(path) as f:
            print(f.read()[:50])


if __name__ == '__main__':
    _test()
