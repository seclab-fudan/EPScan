import unittest
from pathlib import PurePath

from modules.pod_source_match.rules import *


class TestUtils(unittest.TestCase):
    def test_get_last_nontrivial_part(self):
        path = PurePath('cmd/chaos-daemon/main.go')
        self.assertEqual(get_last_nontrivial_part(path.parts), 'chaos-daemon')

        pkg = 'github.com/chaos-mesh/chaos-mesh/cmd/chaos-dashboard'.split('/')
        self.assertEqual(get_last_nontrivial_part(pkg), 'chaos-dashboard')
