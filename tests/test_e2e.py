from pathlib import Path
from unittest import TestCase

import pytest

import ep_scan
from modules import source_download
from modules.storage import ProjectFolder
from modules.types import RemoteRepository
from tests import E2E_TEST

BASE_PATH = Path(__file__).parent / 'resources' / 'e2e'


@pytest.mark.skipif(not E2E_TEST, reason="E2E_TEST is not set")
class TestE2e(TestCase):

    def test_chaos_mesh(self):
        proj = ProjectFolder(BASE_PATH)
        proj_name = 'chaos-mesh'
        repo = RemoteRepository(
            url='https://github.com/chaos-mesh/chaos-mesh',
            tag='v2.6.3',
        )

        source_download.download_project_source(proj, proj_name, repo)

        ep_scan.run_single(proj, proj_name)

        # TODO: assertion

    def test_submariner(self):
        proj = ProjectFolder(BASE_PATH)
        proj_name = 'submariner'

        repos = [
            RemoteRepository(
                url='https://github.com/submariner-io/submariner-operator',
                tag='v0.14.0',
            ),
            RemoteRepository(
                url='https://github.com/submariner-io/submariner',
                tag='v0.17.1',
            ),
        ]
        for repo in repos:
            source_download.download_project_source(proj, proj_name, repo)

        ep_scan.run_single(proj, proj_name)

        # TODO: assertion
