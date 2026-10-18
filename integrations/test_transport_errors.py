import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from integrations.client import Client, CRMError

class TransportErrorsTests(SimpleTestCase):
    @patch('integrations.client.subprocess.run')
    def test_receive_failure_has_no_fake_http_status(self, run):
        run.return_value = SimpleNamespace(returncode=22, stdout=json.dumps({'transport_error': 0, 'transport_kind': 'ReceiveFailure'}))
        with self.assertRaises(CRMError) as caught:
            Client({'base_url': 'https://crm.baridsoft.ir', 'organization': 'Main', 'api_version': 'v8.2'}).get('WhoAmI')
        self.assertNotIn('HTTP 0', str(caught.exception))
        self.assertIn('محیط اجرای', str(caught.exception))

    @patch('integrations.client.subprocess.run')
    def test_real_http_status_preserved(self, run):
        run.return_value = SimpleNamespace(returncode=22, stdout=json.dumps({'transport_error': 403}))
        with self.assertRaisesMessage(CRMError, 'HTTP 403'):
            Client({'base_url': 'https://crm.baridsoft.ir', 'organization': 'Main', 'api_version': 'v8.2'}).get('WhoAmI')
