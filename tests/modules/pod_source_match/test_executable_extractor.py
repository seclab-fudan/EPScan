import unittest

from modules.pod_source_match.executable_extractor import *


class TestUtils(unittest.TestCase):

    def test_list_scripts_path_in_script(self):
        ret = list_scripts_path_in_script('tini -- /bin/entrypoint.sh fluentd')
        self.assertEqual(ret, [PurePath('/bin/entrypoint.sh')])

        ret = list_scripts_path_in_script(
            '/opt/bitnami/scripts/mongodb/entrypoint.sh /opt/bitnami/scripts/mongodb/run.sh')
        self.assertEqual(ret, [PurePath('/opt/bitnami/scripts/mongodb/entrypoint.sh'),
                               PurePath('/opt/bitnami/scripts/mongodb/run.sh')])

        ret = list_scripts_path_in_script(
            '/bin/sh -c echo name: $EG_NAME > /opt/eg-config/config.yaml &&\ncat /opt/eg-config/eg-primary.yaml >> '
            '/opt/eg-config/config.yaml &&\n/opt/easegress/bin/easegress-server \\\n  -f /opt/eg-config/config.yaml '
            '\\\n  --advertise-client-urls http://$(EG_NAME).easegress-hs.default:2379 \\\n  '
            '--initial-advertise-peer-urls http://$(EG_NAME).easegress-hs.default:2380')
        self.assertEqual(ret, [])

        ret = list_scripts_path_in_script('./gen-admission-secret.sh --service volcano-admission-service '
                                          '--namespace default --secret volcano-admission-secret')
        self.assertEqual(ret, [PurePath('gen-admission-secret.sh')])

        ret = list_scripts_path_in_script('/opt/keycloak/bin/kc.sh start --features=token-exchange --db=$(KC_DB) '
                                          '--db-url-host=$(KC_DB_URL_HOST) --db-username=$(KC_DB_USER) '
                                          '--db-password=$(KC_DB_PASSWORD) '
                                          '--hostname=keycloak-microcks.192.168.99.100.nip.io --health-enabled=true '
                                          '--import-realm')
        self.assertEqual(ret, [PurePath('/opt/keycloak/bin/kc.sh')])
