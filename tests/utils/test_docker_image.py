from unittest import TestCase

import pytest

from tests import HEAVY_TEST
from utils.docker_image import get_image_config


class TestDockerImage(TestCase):
    @pytest.mark.skipif(not HEAVY_TEST, reason="HEAVY_TEST is not set")
    def test_get_image_config(self):
        with self.subTest("Normal"):
            config = get_image_config('registry-1.docker.io', 'library/nginx', 'latest')
            self.assertIsNotNone(config)

        with self.subTest("Image not exist"):
            config = get_image_config('registry-1.docker.io', 'library/not_exist', 'latest')
            self.assertIsNone(config)
            self.assertLogs('failed to get image configfailed to get image config', 'ERROR')

        with self.subTest("Tag not exist"):
            config = get_image_config('registry-1.docker.io', 'library/nginx', 'not_exist')
            self.assertIsNone(config)
            self.assertLogs('failed to get image configfailed to get image config', 'ERROR')
