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
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')

        global_expected = {'a': {'x': 1, 'y': 2}, 'c': 'global-secret'}
        site_expected = {'a': {'x': 1, 'y': 2}, 'b': 4, 'c': 'global-secret'}

        self._test_layering(documents, site_expected=site_expected,
                            global_expected=global_expected,
                            substitution_sources=[certificate])

    def test_layering_and_substitution_no_children(self):
        # Validate that a document with no children still undergoes
        # substitution.
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
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        # Remove the labels from the global document so that the site document
        # (the child) has no parent.
        documents[1]['metadata']['labels'] = {}
        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')

        global_expected = {'a': {'x': 1, 'y': 2}, 'c': 'global-secret'}
        site_expected = {'b': 4}

        self._test_layering(documents, site_expected=site_expected,
                            global_expected=global_expected,
                            substitution_sources=[certificate])

    def test_layering_and_substitution_no_parent(self):
        # Validate that a document with no parent undergoes substitution.
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
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        # Remove the labels from the global document so that the site document
        # (the child) has no parent.
        documents[1]['metadata']['labels'] = {}
        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='site-secret',
            name='site-cert')

        global_expected = {'a': {'x': 1, 'y': 2}}
        site_expected = {'b': 4, 'c': 'site-secret'}

        self._test_layering(documents, site_expected=site_expected,
                            global_expected=global_expected,
                            substitution_sources=[certificate])

    def test_layering_parent_and_child_undergo_substitution(self):
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
        documents = doc_factory.gen_test(mapping, site_abstract=False)
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

        self._test_layering(
            documents, site_expected=site_expected,
            global_expected=global_expected,
            substitution_sources=[certificate, certificate_key])
