from pathlib import Path
from unittest import TestCase

from tinydb.queries import Query

from analyse.k8s.basic import Object
from analyse.k8s.workload import Container, ContainerCarrier
from tests import load_single_objs


class TestContainer(TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        store = load_single_objs()
        self.pod = store.search(Query().metadata.name == 'test_container')[0]
        self.deployment = store.search(Query().metadata.name == 'test_container_deployment')[0]
        self.cronjob = store.search(Query().metadata.name == 'test_container_cronjob')[0]
        assert self.pod

    def get_container(self, name) -> Container:
        for container in self.pod.containers():
            if container.name == name:
                return container
        self.fail(f'Container {name} not found')

    def test_resolve_full_command(self):
        container = self.get_container('container-has-cmd')
        self.assertEqual(container.resolve_full_command(inspect_image=False), ['nginx', '-g', 'daemon off;'])

        container = self.get_container('container-has-cmd-args')
        self.assertEqual(container.resolve_full_command(inspect_image=False), ['nginx', '-g', 'daemon off;'])

        container = self.get_container('container-no-cmd')
        with self.assertRaises(ValueError, msg='No explicit command needs image inspection'):
            container.resolve_full_command(inspect_image=False)

    def test_resolve_full_command_from_image(self):
        CACHE_DIR = Path(__file__).parent / '../../resources'
        container = self.get_container('container-no-cmd')
        self.assertEqual(container.resolve_full_command(inspect_image=True, cache_dir=CACHE_DIR),
                         ['/docker-entrypoint.sh', 'nginx', '-g', 'daemon off;'])

    def test_resolve_executable_name(self):
        container = self.get_container('container-has-cmd')
        self.assertEqual(container.resolve_executable_name(inspect_image=False), 'nginx')

        container = self.get_container('container-cmd-use-absolute')
        self.assertEqual(container.resolve_executable_name(inspect_image=False), 'nginx')

        with self.subTest('container-use-tini'):
            container = self.get_container('container-use-tini')
            self.assertEqual(container.resolve_executable_name(inspect_image=True), 'kustomize-controller')

    def test_containers(self):
        with self.subTest('Pod'):
            for container in self.pod.containers():
                self.assertIsInstance(container, Container)

        with self.subTest('Deployment'):
            for container in self.deployment.containers():
                self.assertIsInstance(container, Container)

        with self.subTest('CronJob'):
            for container in self.cronjob.containers():
                self.assertIsInstance(container, Container)


class TestContainerCarrier(TestCase):
    def test_sa_name(self):
        cases = [
            {
                "name": "Normal",
                "pod": {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "spec": {
                        "serviceAccountName": "test-sa"
                    }
                },
                "expected_sa": "test-sa"
            },
            {
                "name": "Default SA",
                "pod": {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "spec": {}
                },
                "expected_sa": "default"
            },
            {
                "name": "Empty SA",
                "pod": {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "spec": {
                        "serviceAccountName": ""
                    }
                },
                "expected_sa": "default"
            },
            {
                "name": "Deprecated serviceAccount",
                "pod": {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "spec": {
                        "serviceAccount": "test-sa"
                    }
                },
                "expected_sa": "test-sa"
            },
            {
                "name": "Deployment",
                "pod": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "spec": {
                        "template": {
                            "spec": {
                                "serviceAccountName": "test-sa"
                            }
                        }
                    }
                },
                "expected_sa": "test-sa"
            },
            {
                "name": "CronJob",
                "pod": {
                    "apiVersion": "batch/v1beta1",
                    "kind": "CronJob",
                    "spec": {
                        "jobTemplate": {
                            "spec": {
                                "template": {
                                    "spec": {
                                        "serviceAccountName": "test-sa"
                                    }
                                }
                            }
                        }
                    }
                },
                "expected_sa": "test-sa"
            },
        ]

        for case in cases:
            with self.subTest(case['name']):
                pod = Object.from_dict(case['pod'])
                self.assertIsInstance(pod, ContainerCarrier)
                self.assertEqual(case['expected_sa'], pod.sa_name)
