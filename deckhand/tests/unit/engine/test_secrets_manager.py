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

import copy

from deckhand.engine import secrets_manager
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base as test_base


class TestSecretsManager(test_base.TestDbBase):

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
            self.assertEqual(secret_data, created_secret)
        elif encryption_type == 'encrypted':
            expected_kwargs = {
                'name': secret_doc['metadata']['name'],
                'secret_type': ('private' if secret_type == 'CertificateKey'
                                else secret_type.lower()),
                'payload': secret_doc['data']
            }
            self.mock_barbican_driver.create_secret.assert_called_once_with(
                **expected_kwargs)
            self.assertEqual(self.secret_ref, created_secret)

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


class TestSecretsSubstitution(test_base.TestDbBase):

    def setUp(self):
        super(TestSecretsSubstitution, self).setUp()
        self.document_factory = factories.DocumentFactory(1, [1])
        self.secrets_factory = factories.DocumentSecretFactory()

    def _test_secret_substitution(self, document_mapping, secret_documents,
                                  expected_data):
        payload = self.document_factory.gen_test(document_mapping,
                                                 global_abstract=False)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(
            bucket_name, secret_documents + [payload[-1]])

        expected_document = copy.deepcopy(documents[-1])
        expected_document['data'] = expected_data

        secret_substitution = secrets_manager.SecretsSubstitution(documents)
        substituted_docs = secret_substitution.substitute_all()

        self.assertIn(expected_document, substituted_docs)

    def test_secret_substitution_single_cleartext(self):
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'

        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart.values.tls.certificate"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "example-cert",
                    "path": "."
                }

            }]
        }
        expected_data = {
            'chart': {
                'values': {
                    'tls': {
                        'certificate': 'CERTIFICATE DATA'
                    }
                }
            }
        }
        self._test_secret_substitution(
            document_mapping, [certificate], expected_data)

    def test_secret_substitution_single_cleartext_with_pattern(self):
        passphrase = self.secrets_factory.gen_test(
            'Passphrase', 'cleartext', data='my-secret-password')
        passphrase['metadata']['name'] = 'example-password'

        document_mapping = {
            "_GLOBAL_DATA_1_": {
                'data': {
                    'chart': {
                        'values': {
                            'some_url': (
                                'http://admin:INSERT_PASSWORD_HERE'
                                '@service-name:8080/v1')
                        }
                    }
                }
            },
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart.values.some_url",
                    "pattern": "INSERT_[A-Z]+_HERE"
                },
                "src": {
                    "schema": "deckhand/Passphrase/v1",
                    "name": "example-password",
                    "path": "."
                }
            }]
        }
        expected_data = {
            'chart': {
                'values': {
                    'some_url': (
                        'http://admin:my-secret-password@service-name:8080/v1')
                }
            }
        }
        self._test_secret_substitution(
            document_mapping, [passphrase], expected_data)

    def test_secret_substitution_double_cleartext(self):
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'

        certificate_key = self.secrets_factory.gen_test(
            'CertificateKey', 'cleartext', data='KEY DATA')
        certificate_key['metadata']['name'] = 'example-key'

        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart.values.tls.certificate"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "example-cert",
                    "path": "."
                }

            }, {
                "dest": {
                    "path": ".chart.values.tls.key"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "example-key",
                    "path": "."
                }

            }]
        }
        expected_data = {
            'chart': {
                'values': {
                    'tls': {
                        'certificate': 'CERTIFICATE DATA',
                        'key': 'KEY DATA'
                    }
                }
            }
        }
        self._test_secret_substitution(
            document_mapping, [certificate, certificate_key], expected_data)

    def test_secret_substitution_multiple_cleartext(self):
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'

        certificate_key = self.secrets_factory.gen_test(
            'CertificateKey', 'cleartext', data='KEY DATA')
        certificate_key['metadata']['name'] = 'example-key'

        passphrase = self.secrets_factory.gen_test(
            'Passphrase', 'cleartext', data='my-secret-password')
        passphrase['metadata']['name'] = 'example-password'

        document_mapping = {
            "_GLOBAL_DATA_1_": {
                'data': {
                    'chart': {
                        'values': {
                            'some_url': (
                                'http://admin:INSERT_PASSWORD_HERE'
                                '@service-name:8080/v1')
                        }
                    }
                }
            },
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart.values.tls.certificate"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "example-cert",
                    "path": "."
                }

            }, {
                "dest": {
                    "path": ".chart.values.tls.key"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "example-key",
                    "path": "."
                }

            }, {
                "dest": {
                    "path": ".chart.values.some_url",
                    "pattern": "INSERT_[A-Z]+_HERE"
                },
                "src": {
                    "schema": "deckhand/Passphrase/v1",
                    "name": "example-password",
                    "path": "."
                }
            }]
        }
        expected_data = {
            'chart': {
                'values': {
                    'tls': {
                        'certificate': 'CERTIFICATE DATA',
                        'key': 'KEY DATA'
                    },
                    'some_url': (
                        'http://admin:my-secret-password@service-name:8080/v1')
                }
            }
        }
        self._test_secret_substitution(
            document_mapping, [certificate, certificate_key, passphrase],
            expected_data)

    def test_substitution_with_generic_document_as_source(self):
        src_data = 'data-from-generic-document'

        # Create DataSchema document to register generic source document.
        dataschema_factory = factories.DataSchemaFactory()
        dataschema = dataschema_factory.gen_test(
            'unusual/DictWithSecret/v1', {})
        # Create the generic source document from which data will be extracted.
        generic_document_mapping = {
            "_GLOBAL_DATA_1_": {
                'data': {'public': 'random', 'money': src_data}
            }
        }
        payload = self.document_factory.gen_test(generic_document_mapping,
                                                 global_abstract=False)
        payload[-1]['schema'] = "unusual/DictWithSecret/v1"
        payload[-1]['metadata']['name'] = 'dict-with-secret'

        # Store both documents to be created by helper.
        dependent_documents = [payload[-1], dataschema]

        # Mapping for destination document.
        document_mapping = {
            "_GLOBAL_DATA_1_": {
                'data': {}
            },
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": "."
                },
                "src": {
                    "schema": "unusual/DictWithSecret/v1",
                    "name": "dict-with-secret",
                    "path": ".money"
                }

            }]
        }
        self._test_secret_substitution(
            document_mapping, dependent_documents, expected_data=src_data)
