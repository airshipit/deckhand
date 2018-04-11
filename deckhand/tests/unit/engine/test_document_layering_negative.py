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

import mock

from deckhand.engine import layering
from deckhand import errors
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.engine import test_document_layering


class TestDocumentLayeringNegative(
        test_document_layering.TestDocumentLayering):

    def test_layering_method_merge_key_not_in_child(self):
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}, "c": 9}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": ".c"}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        self.assertRaises(errors.MissingDocumentKey, self._test_layering,
                          documents)

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_method_delete_key_not_in_child(self, mock_log):
        # The key will not be in the site after the global data is copied into
        # the site data implicitly.
        action = {'method': 'delete', 'path': '.b'}
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}, "c": 9}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {"actions": [action]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        self.assertRaises(errors.MissingDocumentKey, self._test_layering,
                          documents)
        # Verifies that document data is recursively scrubbed prior to logging
        # it.
        mock_log.debug.assert_called_with(
            'An exception occurred while attempting to layer child document '
            '[%s] %s with parent document [%s] %s using layering action: %s.\n'
            'Scrubbed child document data: %s.\nScrubbed parent document data:'
            ' %s.', documents[2]['schema'], documents[2]['metadata']['name'],
            documents[1]['schema'], documents[1]['metadata']['name'],
            action, {'b': 'Scrubbed', 'a': {'z': 'Scrubbed', 'x': 'Scrubbed'}},
            {'c': 'Scrubbed', 'a': {'x': 'Scrubbed', 'y': 'Scrubbed'}})

    def test_layering_method_replace_key_not_in_child(self):
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}, "c": 9}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "replace", "path": ".c"}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        self.assertRaises(errors.MissingDocumentKey, self._test_layering,
                          documents)

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_with_empty_layer(self, mock_log):
        doc_factory = factories.DocumentFactory(1, [1])
        documents = doc_factory.gen_test({}, global_abstract=False)
        del documents[0]['metadata']['layeringDefinition']

        # Only pass in the LayeringPolicy.
        self._test_layering([documents[0]], global_expected=None)
        mock_log.info.assert_has_calls([
            mock.call(
                '%s is an empty layer with no documents. It will be discarded '
                'from the layerOrder during the layering process.', 'global'),
            mock.call('Either the layerOrder in the LayeringPolicy was empty '
                      'to begin with or no document layers were found in the '
                      'layerOrder, causing it to become empty. No layering '
                      'will be performed.')
        ])

    def test_layering_document_with_invalid_layer_raises_exc(self):
        doc_factory = factories.DocumentFactory(1, [1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        documents[1]['metadata']['layeringDefinition']['layer'] = 'invalid'

        self.assertRaises(errors.InvalidDocumentLayer, self._test_layering,
                          documents)

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_child_with_invalid_parent_selector(self, mock_log):
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)

        for parent_selector in ({'key2': 'value2'}, {'key1': 'value2'}):
            documents[-1]['metadata']['layeringDefinition'][
                'parentSelector'] = parent_selector

            layering.DocumentLayering(documents, validate=False)
            self.assertTrue(any('Could not find parent for document' in
                mock_log.debug.mock_calls[x][1][0])
                    for x in range(len(mock_log.debug.mock_calls)))
            mock_log.debug.reset_mock()

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_unreferenced_parent_label(self, mock_log):
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)

        for parent_label in ({'key2': 'value2'}, {'key1': 'value2'}):
            # Second doc is the global doc, or parent.
            documents[1]['metadata']['labels'] = parent_label

            layering.DocumentLayering(documents, validate=False)
            self.assertTrue(any('Could not find parent for document' in
                mock_log.debug.mock_calls[x][1][0])
                    for x in range(len(mock_log.debug.mock_calls)))
            mock_log.debug.reset_mock()

    def test_layering_duplicate_parent_selector_2_layer(self):
        # Validate that documents belonging to the same layer cannot have the
        # same unique parent identifier referenced by `parentSelector`.
        doc_factory = factories.DocumentFactory(2, [2, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        # Make both global documents have the same exact labels.
        documents[2]['metadata']['labels'] = documents[1]['metadata']['labels']

        self.assertRaises(errors.IndeterminateDocumentParent,
                          layering.DocumentLayering, documents, validate=False)

    def test_layering_duplicate_parent_selector_3_layer(self):
        # Validate that documents belonging to the same layer cannot have the
        # same unique parent identifier referenced by `parentSelector`.
        doc_factory = factories.DocumentFactory(3, [1, 2, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        # Make both region documents have the same exact labels.
        documents[3]['metadata']['labels'] = documents[2]['metadata']['labels']

        self.assertRaises(errors.IndeterminateDocumentParent,
                          layering.DocumentLayering, documents, validate=False)

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_document_references_itself(self, mock_log):
        # Test that a parentSelector cannot reference the document itself
        # without an error being raised.
        doc_factory = factories.DocumentFactory(3, [1, 1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        self_ref = {"self": "self"}
        documents[2]['metadata']['labels'] = self_ref
        documents[2]['metadata']['layeringDefinition'][
            'parentSelector'] = self_ref

        layering.DocumentLayering(documents, validate=False)
        self.assertTrue(any('Could not find parent for document' in
            mock_log.debug.mock_calls[x][1][0])
                for x in range(len(mock_log.debug.mock_calls)))

    def test_layering_without_layering_policy_raises_exc(self):
        doc_factory = factories.DocumentFactory(1, [1])
        documents = doc_factory.gen_test({}, site_abstract=False)[1:]
        self.assertRaises(errors.LayeringPolicyNotFound,
                          layering.DocumentLayering, documents)

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_multiple_layering_policy_logs_warning(self, mock_log):
        doc_factory = factories.DocumentFactory(1, [1])
        documents = doc_factory.gen_test({}, global_abstract=False)
        # Copy the same layering policy so that 2 are passed in, causing a
        # warning to be raised.
        documents.append(documents[0])
        self._test_layering(documents, global_expected={})
        mock_log.warning.assert_called_with(
            'More than one layering policy document was passed in. Using the '
            'first one found: [%s] %s.', documents[0]['schema'],
            documents[0]['metadata']['name'])

    def test_layering_documents_with_different_schemas_raises_exc(self):
        """Validate that attempting to layer documents with different `schema`s
        results in errors.
        """
        doc_factory = factories.DocumentFactory(3, [1, 1, 1])
        documents = doc_factory.gen_test({})

        # Region and site documents should result in no parent being found
        # since their `schema`s will not match that of their parent's.
        for idx in range(1, 3):  # Only region/site have parent.
            documents[idx]['schema'] = test_utils.rand_name('schema')
            self.assertRaises(
                errors.InvalidDocumentParent, self._test_layering, documents)

    def test_layering_parent_and_child_with_same_layer_raises_exc(self):
        """Validate that attempting to layer documents with the same layer
        results in an exception.
        """
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({})

        for x in range(1, 3):
            documents[x]['metadata']['layeringDefinition']['layer'] = 'global'

        self.assertRaises(
            errors.InvalidDocumentParent, self._test_layering, documents)


class TestDocumentLayeringValidationNegative(
        test_document_layering.TestDocumentLayering):

    def test_layering_invalid_substitution_format_raises_exc(self):
        doc_factory = factories.DocumentFactory(1, [1])
        layering_policy, document_template = doc_factory.gen_test({
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
        }, global_abstract=False)

        for key in ('src', 'dest'):
            document = copy.deepcopy(document_template)
            del document['metadata']['substitutions'][0][key]
            self.assertRaises(errors.InvalidDocumentFormat,
                              self._test_layering, [layering_policy, document],
                              validate=True)

        for key in ('schema', 'name', 'path'):
            document = copy.deepcopy(document_template)
            del document['metadata']['substitutions'][0]['src'][key]
            self.assertRaises(errors.InvalidDocumentFormat,
                              self._test_layering, [layering_policy, document],
                              validate=True)

        for key in ('path',):
            document = copy.deepcopy(document_template)
            del document['metadata']['substitutions'][0]['dest'][key]
            self.assertRaises(errors.InvalidDocumentFormat,
                              self._test_layering, [layering_policy, document],
                              validate=True)

    def test_layering_invalid_document_format_generates_error_messages(self):
        doc_factory = factories.DocumentFactory(1, [1])
        lp_template, document = doc_factory.gen_test({
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
        }, global_abstract=False)

        layering_policy = copy.deepcopy(lp_template)
        del layering_policy['data']['layerOrder']
        error_re = r"^'layerOrder' is a required property$"
        e = self.assertRaises(
            errors.InvalidDocumentFormat, self._test_layering,
            [layering_policy, document], validate=True)
        self.assertRegex(e.error_list[0]['message'], error_re)
        self.assertEqual(layering_policy['schema'],
                         e.error_list[0]['documents'][0]['schema'])
        self.assertEqual(layering_policy['metadata']['name'],
                         e.error_list[0]['documents'][0]['name'])
        self.assertEqual(layering_policy['metadata']['layeringDefinition'][
                         'layer'],
                         e.error_list[0]['documents'][0]['layer'])
