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

import itertools

import mock

from deckhand import factories
from deckhand.tests.unit.engine import test_document_layering


class TestDocumentLayeringWithSubstitution(
        test_document_layering.TestDocumentLayering):

    def test_layering_and_substitution_default_scenario(self):
        # Validate that layering and substitution work together.
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": {"b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)

        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        documents.append(certificate)

        global_expected = {'a': {'x': 1, 'y': 2}, 'c': 'global-secret'}
        site_expected = {'a': {'x': 1, 'y': 2}, 'b': 4, 'c': 'global-secret'}

        self._test_layering(documents, site_expected=site_expected,
                            global_expected=global_expected)

    def test_layering_and_substitution_no_children(self):
        """Validate that a document with no children undergoes substitution.

        global -> (no children) requires substitution
        site -> (no parent) do nothing
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": {"b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)

        # Remove the labels from the global document so that the site document
        # (the child) has no parent.
        documents[1]['metadata']['labels'] = {}

        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        documents.append(certificate)

        global_expected = {'a': {'x': 1, 'y': 2}, 'c': 'global-secret'}
        site_expected = {'b': 4}

        self._test_layering(documents, site_expected=site_expected,
                            global_expected=global_expected)

    def test_substitution_without_parent_document(self):
        """Validate that a document with no parent undergoes substitution.

        global -> do nothing
        site -> (no parent & no children) requires substitution
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_SITE_DATA_1_": {"data": {"b": 4}},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "site-cert",
                    "path": "."
                }
            }],
            # No layering should be applied as the document has no parent.
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)

        # Remove the labels from the global document so that the site document
        # (the child) has no parent.
        documents[1]['metadata']['labels'] = {}

        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='site-secret',
            name='site-cert')
        documents.append(certificate)

        global_expected = {'a': {'x': 1, 'y': 2}}
        site_expected = {'b': 4, 'c': 'site-secret'}

        self._test_layering(documents, site_expected=site_expected,
                            global_expected=global_expected)

    def test_parent_and_child_layering_and_substitution_different_paths(self):
        """Validate that parent and child documents both undergo layering and
        substitution where the substitution occurs at different paths.

        global -> requires substitution
          |
          v
        site -> requires substitution
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": {"c": "need-site-secret"}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-cert",
                    "path": "."
                }
            }],
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret',
                         'c': 'site-secret'}

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_key = secrets_factory.gen_test(
            'CertificateKey', 'cleartext', data='site-secret',
            name='site-cert')
        documents.extend([certificate, certificate_key])

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected)

    def test_parent_and_child_layering_and_substitution_same_paths(self):
        """Validate that parent and child documents both undergo layering and
        substitution where the substitution occurs at the same path.

        global -> requires substitution
          |
          v
        site -> requires substitution
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": "placeholder"},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-cert",
                    "path": "."
                }
            }],
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = {'a': {'x': 1, 'y': 2}, 'b': 'site-secret'}

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_key = secrets_factory.gen_test(
            'CertificateKey', 'cleartext', data='site-secret',
            name='site-cert')
        documents.extend([certificate, certificate_key])

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected)

    def test_parent_with_multi_child_layering_and_sub_different_paths(self):
        """Validate that parent and children documents both undergo layering
        and substitution where the substitution occurs at different paths.

        global -> requires substitution
          |
          v
        site1 -> requires substitution
        site2 -> requires substitution
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": "placeholder"},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-1-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_2_": {"data": "placeholder"},
            "_SITE_ACTIONS_2_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_2_": [{
                "dest": {
                    "path": ".d"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-2-cert",
                    "path": "."
                }
            }],
        }
        doc_factory = factories.DocumentFactory(2, [1, 2])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = [
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret', 'c': 'site-1-sec'},
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret', 'd': 'site-2-sec'}]

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_keys = [
            secrets_factory.gen_test(
                'CertificateKey', 'cleartext', data='site-%d-sec' % idx,
                name='site-%d-cert' % idx)
            for idx in range(1, 3)
        ]
        documents.extend([certificate] + certificate_keys)

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected)

    def test_parent_with_multi_child_layering_and_sub_same_path(self):
        """Validate that parent and children documents both undergo layering
        and substitution where the substitution occurs at the same path.

        global -> requires substitution
          |
          v
        site1 -> requires substitution
        site2 -> requires substitution
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": "placeholder"},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-1-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_2_": {"data": "placeholder"},
            "_SITE_ACTIONS_2_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_2_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-2-cert",
                    "path": "."
                }
            }],
        }
        doc_factory = factories.DocumentFactory(2, [1, 2])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = [
            {'a': {'x': 1, 'y': 2}, 'b': 'site-1-sec'},
            {'a': {'x': 1, 'y': 2}, 'b': 'site-2-sec'}]

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_keys = [
            secrets_factory.gen_test(
                'CertificateKey', 'cleartext', data='site-%d-sec' % idx,
                name='site-%d-cert' % idx)
            for idx in range(1, 3)
        ]
        documents.extend([certificate] + certificate_keys)

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected)

    def test_parent_with_multi_child_layering_and_multi_substitutions(self):
        """Validate that parent and children documents both undergo layering
        and multiple substitutions.

        global -> requires substitution
          |
          v
        site1 -> requires multiple substitutions
        site2 -> requires multiple substitutions
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": "placeholder"},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [
                {
                    "dest": {
                        "path": ".c"
                    },
                    "src": {
                        "schema": "deckhand/CertificateKey/v1",
                        "name": "site-1-cert-key",
                        "path": "."
                    },
                },
                {
                    "dest": {
                        "path": ".d"
                    },
                    "src": {
                        "schema": "deckhand/Certificate/v1",
                        "name": "site-1-cert",
                        "path": "."
                    }
                }
            ],
            "_SITE_DATA_2_": {"data": "placeholder"},
            "_SITE_ACTIONS_2_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_2_": [
                {
                    "dest": {
                        "path": ".e"
                    },
                    "src": {
                        "schema": "deckhand/CertificateKey/v1",
                        "name": "site-2-cert-key",
                        "path": "."
                    },
                },
                {
                    "dest": {
                        "path": ".f"
                    },
                    "src": {
                        "schema": "deckhand/Certificate/v1",
                        "name": "site-2-cert",
                        "path": "."
                    }
                }
            ]
        }
        doc_factory = factories.DocumentFactory(2, [1, 2])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = [
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret',
             'c': 'site-1-sec-key', 'd': 'site-1-sec'},
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret',
             'e': 'site-2-sec-key', 'f': 'site-2-sec'}]

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_keys = [
            secrets_factory.gen_test(
                'CertificateKey', 'cleartext', data='site-%d-sec-key' % idx,
                name='site-%d-cert-key' % idx)
            for idx in range(1, 3)
        ]
        certificates = [
            secrets_factory.gen_test(
                'Certificate', 'cleartext', data='site-%d-sec' % idx,
                name='site-%d-cert' % idx)
            for idx in range(1, 3)
        ]
        documents.extend([certificate] + certificate_keys + certificates)

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected)

    @mock.patch('deckhand.engine.layering.LOG', autospec=True)
    def test_parent_and_child_undergo_layering_and_substitution_empty_layers(
            self, mock_log):
        """Validate that parent and child documents both undergo substitution
        and layering.

        empty layer -> discard
          |
          v
        empty layer -> discard
          |
          v
        global -> requires substitution
          |
          v
        empty layer -> discard
          |
          V
        site -> requires substitution (layered with global)

        Where the site's parent is actually the global document.
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": {"c": "need-site-secret"}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-cert",
                    "path": "."
                }
            }],
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        documents[0]['data']['layerOrder'] = [
            'empty_1', 'empty_2', 'global', 'empty_3', 'site']
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret',
                         'c': 'site-secret'}

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_key = secrets_factory.gen_test(
            'CertificateKey', 'cleartext', data='site-secret',
            name='site-cert')
        documents.extend([certificate] + [certificate_key])

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected)

        expected_message = (
            '%s is an empty layer with no documents. It will be discarded '
            'from the layerOrder during the layering process.')
        expected_log_calls = [mock.call(expected_message, layer)
                              for layer in ('empty_1', 'empty_2', 'empty_3')]
        mock_log.info.assert_has_calls(expected_log_calls)

    def test_layering_with_substitution_dependency_chain(self):
        """Validate that parent with multiple children that substitute from
        each other works no matter the order of the documents.
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".b"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }],
            "_SITE_NAME_1_": "site-1",
            "_SITE_DATA_1_": {"data": {"c": "placeholder"}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-cert",
                    "path": "."
                }
            }],
            "_SITE_NAME_2_": "site-2",
            "_SITE_DATA_2_": {"data": {"d": "placeholder"}},
            "_SITE_ACTIONS_2_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_2_": [{
                "dest": {
                    "path": ".d"
                },
                "src": {
                    "schema": "example/Kind/v1",
                    "name": "site-1",
                    "path": ".c"
                }
            }],
            "_SITE_NAME_3_": "site-3",
            "_SITE_DATA_3_": {"data": {"e": "placeholder"}},
            "_SITE_ACTIONS_3_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_3_": [{
                "dest": {
                    "path": ".e"
                },
                "src": {
                    "schema": "example/Kind/v1",
                    "name": "site-2",
                    "path": ".d"
                }
            }]
        }
        doc_factory = factories.DocumentFactory(2, [1, 3])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=False)
        secrets_factory = factories.DocumentSecretFactory()

        global_expected = {'a': {'x': 1, 'y': 2}, 'b': 'global-secret'}
        site_expected = [
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret', 'c': 'site-secret'},
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret', 'd': 'site-secret'},
            {'a': {'x': 1, 'y': 2}, 'b': 'global-secret', 'e': 'site-secret'}
        ]

        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')
        certificate_key = secrets_factory.gen_test(
            'CertificateKey', 'cleartext', data='site-secret',
            name='site-cert')
        documents.extend([certificate] + [certificate_key])

        # Pass in the documents in reverse order to ensure that the dependency
        # chain by default is not linear and thus requires sorting.
        self._test_layering(
            list(reversed(documents)), site_expected=site_expected,
            global_expected=global_expected)

        # Try different permutations of document orders for good measure.
        for document_order in list(itertools.permutations(documents))[:10]:
            self._test_layering(
                document_order, site_expected=site_expected,
                global_expected=global_expected)

    def test_layering_and_substitution_site_abstract_and_global_concrete(self):
        """Verifies that if a global document is abstract, yet has
        substitutions, those substitutions are performed and carry down to
        concrete children that inherit from the abstract parent.
        """
        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')

        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"global": "random"}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".cert"
                },
                "src": {
                    "schema": certificate['schema'],
                    "name": certificate['metadata']['name'],
                    "path": "."
                }
            }],
            "_SITE_DATA_1_": {"data": {"site": "stuff"}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False,
                                         global_abstract=True)
        documents.append(certificate)

        site_expected = {"global": "random", "cert": "global-secret",
                         "site": "stuff"}
        global_expected = None
        self._test_layering(documents, site_expected,
                            global_expected=global_expected)
