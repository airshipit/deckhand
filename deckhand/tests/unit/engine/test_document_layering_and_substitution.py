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

import mock

from deckhand.engine import secrets_manager
from deckhand import factories
from deckhand.tests.unit.engine import test_document_layering


class TestDocumentLayeringWithSubstitution(
        test_document_layering.TestDocumentLayering):

    def test_layering_and_substitution_default_scenario(self):
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

        with mock.patch.object(
                secrets_manager.db_api, 'document_get',
                return_value=certificate, autospec=True) as mock_document_get:
            self._test_layering(documents, site_expected=site_expected,
                                global_expected=global_expected)
        mock_document_get.assert_called_once_with(
            schema=certificate['schema'], name=certificate['metadata']['name'],
            **{'metadata.layeringDefinition.abstract': False})

    def test_layering_and_substitution_no_children(self):
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

        documents[1]['metadata']['labels'] = {}
        secrets_factory = factories.DocumentSecretFactory()
        certificate = secrets_factory.gen_test(
            'Certificate', 'cleartext', data='global-secret',
            name='global-cert')

        global_expected = {'a': {'x': 1, 'y': 2}, 'c': 'global-secret'}
        site_expected = {'b': 4}

        with mock.patch.object(
                secrets_manager.db_api, 'document_get',
                return_value=certificate, autospec=True) as mock_document_get:
            self._test_layering(documents, site_expected=site_expected,
                                global_expected=global_expected)
        mock_document_get.assert_called_once_with(
            schema=certificate['schema'], name=certificate['metadata']['name'],
            **{'metadata.layeringDefinition.abstract': False})

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

        def _get_secret_document(*args, **kwargs):
            name = kwargs['name']
            prefix = name.split('-')[0]
            return secrets_factory.gen_test(
                'Certificate', 'cleartext', data='%s-secret' % prefix,
                name='%s' % name)

        with mock.patch.object(
                secrets_manager.db_api, 'document_get',
                autospec=True) as mock_document_get:
            mock_document_get.side_effect = _get_secret_document
            self._test_layering(documents, site_expected=site_expected,
                                global_expected=global_expected)
        mock_document_get.assert_has_calls([
            mock.call(
                schema="deckhand/Certificate/v1", name='global-cert',
                **{'metadata.layeringDefinition.abstract': False}),
            mock.call(
                schema="deckhand/CertificateKey/v1", name='site-cert',
                **{'metadata.layeringDefinition.abstract': False})
        ])
