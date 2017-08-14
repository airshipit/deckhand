# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from deckhand.engine import secrets_manager
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestSecretsManager(base.TestDbBase):

    def setUp(self):
        super(TestSecretsManager, self).setUp()
        self.mock_barbican_driver = self.patchobject(
            secrets_manager.SecretsManager, 'barbican_driver')
        self.secret_ref = 'https://path/to/fake_secret'
        self.mock_barbican_driver.create_secret.return_value = (
            {'secret_href': self.secret_ref})

        self.secrets_manager = secrets_manager.SecretsManager()
        self.factory = factories.DocumentSecretFactory()

    def _test_create_secret(self, encryption_type, secret_type):
        secret_data = test_utils.rand_password()
        secret_doc = self.factory.gen_test(
            secret_type, encryption_type, secret_data)

        created_secret = self.secrets_manager.create(secret_doc)

        if encryption_type == 'cleartext':
            self.assertIn('secret', created_secret)
            self.assertEqual(secret_data, created_secret['secret'])
        elif encryption_type == 'encrypted':
            expected_kwargs = {
                'name': secret_doc['metadata']['name'],
                'secret_type': ('private' if secret_type == 'CertificateKey'
                                else secret_type.lower()),
                'payload': secret_doc['data']
            }
            self.mock_barbican_driver.create_secret.assert_called_once_with(
                **expected_kwargs)

            self.assertIn('secret', created_secret)
            self.assertEqual(self.secret_ref, created_secret['secret'])

    def test_create_cleartext_certificate(self):
        self._test_create_secret('cleartext', 'Certificate')

    def test_create_cleartext_certificate_key(self):
        self._test_create_secret('cleartext', 'CertificateKey')

    def test_create_cleartext_passphrase(self):
        self._test_create_secret('cleartext', 'Passphrase')

    def test_create_encrypted_certificate(self):
        self._test_create_secret('encrypted', 'Certificate')

    def test_create_encrypted_certificate_key(self):
        self._test_create_secret('encrypted', 'CertificateKey')

    def test_create_encrypted_passphrase(self):
        self._test_create_secret('encrypted', 'Passphrase')
