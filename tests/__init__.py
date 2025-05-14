import os
from pathlib import Path

from analyse.k8s.basic import ObjectStore

HEAVY_TEST = os.environ.get('HEAVY_TEST', False)
E2E_TEST = os.environ.get('E2E_TEST', False)


def load_single_objs() -> ObjectStore:
    return ObjectStore.from_config_dir(Path(__file__).parent / 'resources' / 'single_objs')
