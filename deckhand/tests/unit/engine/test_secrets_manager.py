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
import yaml

import mock
from oslo_utils import uuidutils
import testtools

from deckhand.engine import secrets_manager
from deckhand import errors
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base as test_base


class TestSecretsManager(test_base.TestDbBase):

    def setUp(self):
        super(TestSecretsManager, self).setUp()
        self.mock_barbican_driver = self.patchobject(
            secrets_manager.SecretsManager, 'barbican_driver')
        self.secret_ref = "https://barbican_host/v1/secrets/{secret_uuid}"\
            .format(**{'secret_uuid': uuidutils.generate_uuid()})
        self.mock_barbican_driver.create_secret.return_value = (
            {'secret_ref': self.secret_ref})
        self.factory = factories.DocumentSecretFactory()

    def _test_create_secret(self, encryption_type, secret_type):
        secret_data = test_utils.rand_password()
        secret_doc = self.factory.gen_test(
            secret_type, encryption_type, secret_data)
        payload = secret_doc['data']
        self.mock_barbican_driver.get_secret.return_value = (
            mock.Mock(payload=payload))

        created_secret = secrets_manager.SecretsManager.create(secret_doc)

        if encryption_type == 'cleartext':
            self.assertEqual(secret_data, created_secret)
        elif encryption_type == 'encrypted':
            expected_kwargs = {
                'name': secret_doc['metadata']['name'],
                'secret_type': secrets_manager.SecretsManager._get_secret_type(
                    'deckhand/' + secret_type),
                'payload': payload
            }
            self.mock_barbican_driver.create_secret.assert_called_once_with(
                **expected_kwargs)
            self.assertEqual(self.secret_ref, created_secret)

        return created_secret, payload

    def test_create_cleartext_certificate(self):
        self._test_create_secret('cleartext', 'Certificate')

    def test_create_cleartext_certificate_authority(self):
        self._test_create_secret('cleartext', 'CertificateAuthority')

    def test_create_cleartext_certificate_authority_key(self):
        self._test_create_secret('cleartext', 'CertificateAuthorityKey')

    def test_create_cleartext_certificate_key(self):
        self._test_create_secret('cleartext', 'CertificateKey')

    def test_create_cleartext_passphrase(self):
        self._test_create_secret('cleartext', 'Passphrase')

    def test_create_cleartext_private_key(self):
        self._test_create_secret('cleartext', 'PrivateKey')

    def test_create_encrypted_certificate(self):
        self._test_create_secret('encrypted', 'Certificate')

    def test_create_encrypted_certificate_authority(self):
        self._test_create_secret('encrypted', 'CertificateAuthority')

    def test_create_encrypted_certificate_authority_key(self):
        self._test_create_secret('encrypted', 'CertificateAuthorityKey')

    def test_create_encrypted_certificate_key(self):
        self._test_create_secret('encrypted', 'CertificateKey')

    def test_create_encrypted_passphrase(self):
        self._test_create_secret('encrypted', 'Passphrase')

    def test_create_encrypted_private_key(self):
        self._test_create_secret('encrypted', 'PrivateKey')

    def test_retrieve_barbican_secret(self):
        secret_ref, expected_secret = self._test_create_secret(
            'encrypted', 'Certificate')
        secret_payload = secrets_manager.SecretsManager.get(secret_ref)

        self.assertEqual(expected_secret, secret_payload)
        self.mock_barbican_driver.get_secret.assert_called_once_with(
            secret_ref=secret_ref)


class TestSecretsSubstitution(test_base.TestDbBase):

    def setUp(self):
        super(TestSecretsSubstitution, self).setUp()
        self.document_factory = factories.DocumentFactory(1, [1])
        self.secrets_factory = factories.DocumentSecretFactory()

    def _test_doc_substitution(self, document_mapping, substitution_sources,
                               expected_data):
        payload = self.document_factory.gen_test(document_mapping,
                                                 global_abstract=False)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(
            bucket_name, substitution_sources + [payload[-1]])

        expected_document = copy.deepcopy(documents[-1])
        expected_document['data'] = expected_data

        secret_substitution = secrets_manager.SecretsSubstitution(
            substitution_sources)
        substituted_docs = list(secret_substitution.substitute_all(documents))
        self.assertIn(expected_document, substituted_docs)

    def test_doc_substitution_single_cleartext(self):
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
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)

    @mock.patch.object(secrets_manager, 'SecretsManager', autospec=True)
    def test_doc_substitution_single_encrypted(self, mock_secrets_manager):
        mock_secrets_manager.get.return_value = 'test-certificate'
        secret_ref = test_utils.rand_uuid_hex()

        secret_ref = ("http://127.0.0.1/key-manager/v1/secrets/%s"
                      % secret_ref)
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'encrypted', data=secret_ref)
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
                        'certificate': 'test-certificate'
                    }
                }
            }
        }
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)
        mock_secrets_manager.get.assert_called_once_with(secret_ref=secret_ref)

    def test_create_destination_path_with_array(self):
        # Validate that the destination data will be populated with an array
        # where the data will be contained in array[0].
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'

        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart[0].values.tls.certificate"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "example-cert",
                    "path": "."
                }

            }]
        }
        expected_data = {
            'chart': [{
                'values': {
                    'tls': {
                        'certificate': 'CERTIFICATE DATA'
                    }
                }
            }]
        }
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)

    def test_create_destination_path_with_array_sequential_indices(self):
        # Validate that the destination data will be populated with an array
        # with multiple sequential indices successfully populated.
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'

        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [
                {
                    "dest": {
                        "path": ".chart[0].values.tls.certificate"
                    },
                    "src": {
                        "schema": "deckhand/Certificate/v1",
                        "name": "example-cert",
                        "path": "."
                    }
                },
                {
                    "dest": {
                        "path": ".chart[1].values.tls.same_certificate"
                    },
                    "src": {
                        "schema": "deckhand/Certificate/v1",
                        "name": "example-cert",
                        "path": "."
                    }
                }
            ]
        }
        expected_data = {
            'chart': [
                {
                    'values': {
                        'tls': {
                            'certificate': 'CERTIFICATE DATA',
                        }
                    }
                },
                {
                    'values': {
                        'tls': {
                            'same_certificate': 'CERTIFICATE DATA',
                        }
                    }
                }
            ]
        }
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)

    def test_create_destination_path_with_array_multiple_subs(self):
        # Validate that the destination data will be populated with an array
        # with multiple successful substitutions.
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'

        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [
                {
                    "dest": {
                        "path": ".chart[0].values.tls.certificate"
                    },
                    "src": {
                        "schema": "deckhand/Certificate/v1",
                        "name": "example-cert",
                        "path": "."
                    }
                },
                {
                    "dest": {
                        "path": ".chart[0].values.tls.same_certificate"
                    },
                    "src": {
                        "schema": "deckhand/Certificate/v1",
                        "name": "example-cert",
                        "path": "."
                    }
                }
            ]
        }
        expected_data = {
            'chart': [{
                'values': {
                    'tls': {
                        'certificate': 'CERTIFICATE DATA',
                        'same_certificate': 'CERTIFICATE DATA',
                    }
                }
            }]
        }
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)

    def test_create_destination_path_with_nested_arrays(self):
        # Validate that the destination data will be populated with an array
        # that contains yet another array.
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data='CERTIFICATE DATA')
        certificate['metadata']['name'] = 'example-cert'
        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart[0].values[0].tls.certificate"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "example-cert",
                    "path": "."
                }

            }]
        }
        expected_data = {
            'chart': [
                {
                    'values': [
                        {
                            'tls': {
                                'certificate': 'CERTIFICATE DATA'
                            }
                        }
                    ]
                }
            ]
        }
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)

    def test_create_destination_with_stringified_subpath(self):
        """Validate that a subpath like 'filter:authtoken' in a JSON path like
        ".values.conf.paste.'filter:authtoken'.password" works correctly.
        """
        certificate = self.secrets_factory.gen_test(
            'Passphrase', 'cleartext', data='admin-passphrase')
        certificate['metadata']['name'] = 'example-passphrase'
        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    # NOTE(fmontei): Usage of special characters like this
                    # without quotes need not be handled because it is not
                    # valid YAML to include ":" without quotes.
                    "path": ".values.conf.paste.'filter:authtoken'.password"
                },
                "src": {
                    "schema": "deckhand/Passphrase/v1",
                    "name": "example-passphrase",
                    "path": "."
                }

            }]
        }
        expected_data = {
            'values': {
                'conf': {
                    'paste': {
                        'filter:authtoken': {
                            'password': 'admin-passphrase'
                        }
                    }
                }
            }
        }
        self._test_doc_substitution(
            document_mapping, [certificate], expected_data)

    def test_doc_substitution_single_cleartext_with_pattern(self):
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
        self._test_doc_substitution(
            document_mapping, [passphrase], expected_data)

    def test_doc_substitution_double_cleartext(self):
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
        self._test_doc_substitution(
            document_mapping, [certificate, certificate_key], expected_data)

    def test_doc_substitution_multiple_cleartext(self):
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
        self._test_doc_substitution(
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
        self._test_doc_substitution(
            document_mapping, dependent_documents, expected_data=src_data)

    def test_doc_substitution_multiple_pattern_non_string_values(self):
        for test_value in (123, 3.2, False, None):
            test_yaml = """
---
schema: deckhand/LayeringPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: layering-policy
data:
  layerOrder:
    - global
    - site
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: ucp-drydock
  layeringDefinition:
    abstract: false
    layer: global
  storagePolicy: cleartext
  substitutions:
    - src:
        schema: twigleg/CommonAddresses/v1
        name: common-addresses
        path: .node_ports.maas_api
      dest:
        path: .values.conf.drydock.maasdriver.maas_api_url
        pattern: 'MAAS_PORT'
data:
  values:
    conf:
      drydock:
        maasdriver:
          maas_api_url: http://10.24.31.31:MAAS_PORT/MAAS/api/2.0/
---
schema: twigleg/CommonAddresses/v1
metadata:
  schema: metadata/Document/v1
  name: common-addresses
  layeringDefinition:
    abstract: false
    layer: site
  storagePolicy: cleartext
data:
  node_ports:
    maas_api: {}
...
    """.format(test_value)

            documents = list(yaml.safe_load_all(test_yaml))
            expected = copy.deepcopy(documents[1])
            expected['data']['values']['conf']['drydock']['maasdriver'][
                'maas_api_url'] = 'http://10.24.31.31:{}/MAAS/api/2.0/'.format(
                    test_value)

            secret_substitution = secrets_manager.SecretsSubstitution(
                documents)
            substituted_docs = list(secret_substitution.substitute_all(
                documents))
            self.assertEqual(expected, substituted_docs[0])

    def test_doc_substitution_multiple_pattern_substitutions(self):
        test_yaml = """
---
schema: deckhand/LayeringPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: layering-policy
data:
  layerOrder:
    - global
    - site
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: ucp-drydock
  layeringDefinition:
    abstract: false
    layer: global
  storagePolicy: cleartext
  substitutions:
    - src:
        schema: twigleg/CommonAddresses/v1
        name: common-addresses
        path: .genesis.ip
      dest:
        path: .values.conf.drydock.maasdriver.maas_api_url
        pattern: 'MAAS_IP'
    - src:
        schema: twigleg/CommonAddresses/v1
        name: common-addresses
        path: .node_ports.maas_api
      dest:
        path: .values.conf.drydock.maasdriver.maas_api_url
        pattern: 'MAAS_PORT'
data:
  values:
    conf:
      drydock:
        maasdriver:
          maas_api_url: http://MAAS_IP:MAAS_PORT/MAAS/api/2.0/
---
schema: twigleg/CommonAddresses/v1
metadata:
  schema: metadata/Document/v1
  name: common-addresses
  layeringDefinition:
    abstract: false
    layer: site
  storagePolicy: cleartext
data:
  genesis:
    ip: 10.24.31.31
  node_ports:
    maas_api: 30001
...
"""
        documents = list(yaml.safe_load_all(test_yaml))
        expected = copy.deepcopy(documents[1])
        expected['data']['values']['conf']['drydock']['maasdriver'][
            'maas_api_url'] = 'http://10.24.31.31:30001/MAAS/api/2.0/'

        secret_substitution = secrets_manager.SecretsSubstitution(documents)
        substituted_docs = list(secret_substitution.substitute_all(documents))
        self.assertEqual(expected, substituted_docs[0])


class TestSecretsSubstitutionNegative(test_base.TestDbBase):

    def setUp(self):
        super(TestSecretsSubstitutionNegative, self).setUp()
        self.document_factory = factories.DocumentFactory(1, [1])
        self.secrets_factory = factories.DocumentSecretFactory()

    def _test_secrets_substitution(self, secret_type, expected_exception):
        secret_ref = ("http://127.0.0.1/key-manager/v1/secrets/%s"
                      % test_utils.rand_uuid_hex())
        certificate = self.secrets_factory.gen_test(
            'Certificate', secret_type, data=secret_ref)
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
        payload = self.document_factory.gen_test(document_mapping,
                                                 global_abstract=False)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(
            bucket_name, [certificate] + [payload[-1]])

        secrets_substitution = secrets_manager.SecretsSubstitution(documents)
        with testtools.ExpectedException(expected_exception):
            next(secrets_substitution.substitute_all(documents))

    @mock.patch.object(secrets_manager, 'SecretsManager', autospec=True)
    def test_barbican_exception_raises_unknown_error(
            self, mock_secrets_manager):
        mock_secrets_manager.get.side_effect = errors.BarbicanException
        self._test_secrets_substitution(
            'encrypted', errors.UnknownSubstitutionError)

    @mock.patch('deckhand.engine.secrets_manager.utils', autospec=True)
    def test_generic_exception_raises_unknown_error(
            self, mock_utils):
        mock_utils.jsonpath_replace.side_effect = Exception('test')
        self._test_secrets_substitution(
            'cleartext', errors.UnknownSubstitutionError)

    def test_secret_substititon_missing_src_path_in_src_doc_raises_exc(self):
        """Validates that if a secret can't be found in a substitution
        source document then an exception is raised.
        """
        certificate = self.secrets_factory.gen_test(
            'Certificate', 'cleartext', data={})
        certificate['metadata']['name'] = 'example-cert'

        document_mapping = {
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".chart.values.tls.certificate"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "example-cert",
                    "path": ".path-to-nowhere"
                }

            }]
        }
        payload = self.document_factory.gen_test(document_mapping,
                                                 global_abstract=False)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(
            bucket_name, [certificate] + [payload[-1]])

        secrets_substitution = secrets_manager.SecretsSubstitution(documents)
        with testtools.ExpectedException(
                errors.SubstitutionSourceDataNotFound):
            next(secrets_substitution.substitute_all(documents))
