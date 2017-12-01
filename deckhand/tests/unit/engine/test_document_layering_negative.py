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

        self._test_layering(
            documents, exception_expected=errors.MissingDocumentKey)

    def test_layering_method_delete_key_not_in_child(self):
        # The key will not be in the site after the global data is copied into
        # the site data implicitly.
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}, "c": 9}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "delete", "path": ".b"}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        self._test_layering(
            documents, exception_expected=errors.MissingDocumentKey)

    def test_layering_method_replace_key_not_in_child(self):
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}, "c": 9}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "replace", "path": ".c"}]}
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        self._test_layering(
            documents, exception_expected=errors.MissingDocumentKey)

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_with_broken_layer_order(self, mock_log):
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        layering_policy = self._extract_layering_policy(documents)
        broken_layer_orders = [
            ['site', 'region', 'global'], ['broken', 'global'], ['broken'],
            ['site', 'broken']]

        for broken_layer_order in broken_layer_orders:
            layering_policy['data']['layerOrder'] = broken_layer_order
            # The site will not be able to find a correct parent.
            layering.DocumentLayering(layering_policy, documents)
            self.assertRegexpMatches(mock_log.info.mock_calls[0][1][0],
                                     'Could not find parent for document .*')
            mock_log.info.reset_mock()

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_child_with_invalid_parent_selector(self, mock_log):
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        layering_policy = self._extract_layering_policy(documents)

        for parent_selector in ({'key2': 'value2'}, {'key1': 'value2'}):
            documents[-1]['metadata']['layeringDefinition'][
                'parentSelector'] = parent_selector

            layering.DocumentLayering(layering_policy, documents)
            self.assertRegexpMatches(mock_log.info.mock_calls[0][1][0],
                                     'Could not find parent for document .*')
            mock_log.info.reset_mock()

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_unreferenced_parent_label(self, mock_log):
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        layering_policy = self._extract_layering_policy(documents)

        for parent_label in ({'key2': 'value2'}, {'key1': 'value2'}):
            # Second doc is the global doc, or parent.
            documents[0]['metadata']['labels'] = [parent_label]

            layering.DocumentLayering(layering_policy, documents)
            self.assertRegexpMatches(mock_log.info.mock_calls[0][1][0],
                                     'Could not find parent for document .*')
            mock_log.info.reset_mock()

    def test_layering_duplicate_parent_selector_2_layer(self):
        # Validate that documents belonging to the same layer cannot have the
        # same unique parent identifier referenced by `parentSelector`.
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        layering_policy = self._extract_layering_policy(documents)
        documents.append(documents[0])  # Copy global layer.

        self.assertRaises(errors.IndeterminateDocumentParent,
                          layering.DocumentLayering, layering_policy,
                          documents)

    def test_layering_duplicate_parent_selector_3_layer(self):
        # Validate that documents belonging to the same layer cannot have the
        # same unique parent identifier referenced by `parentSelector`.
        doc_factory = factories.DocumentFactory(3, [1, 1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        layering_policy = self._extract_layering_policy(documents)

        # 0 is global layer, 1 is region layer.
        for idx in (0, 1):
            documents.append(documents[idx])
            self.assertRaises(errors.IndeterminateDocumentParent,
                              layering.DocumentLayering, layering_policy,
                              documents)
            documents.pop(-1)  # Remove the just-appended duplicate.

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_document_references_itself(self, mock_log):
        # Test that a parentSelector cannot reference the document itself
        # without an error being raised.
        doc_factory = factories.DocumentFactory(3, [1, 1, 1])
        documents = doc_factory.gen_test({}, site_abstract=False)
        layering_policy = self._extract_layering_policy(documents)
        self_ref = {"self": "self"}
        documents[2]['metadata']['labels'] = self_ref
        documents[2]['metadata']['layeringDefinition'][
            'parentSelector'] = self_ref

        layering.DocumentLayering(layering_policy, documents)
        self.assertRegexpMatches(mock_log.info.mock_calls[0][1][0],
                                 'Could not find parent for document .*')

    @mock.patch.object(layering, 'LOG', autospec=True)
    def test_layering_documents_with_different_schemas(self, mock_log):
        """Validate that attempting to layer documents with different schemas
        results in errors.
        """
        doc_factory = factories.DocumentFactory(3, [1, 1, 1])
        documents = doc_factory.gen_test({})
        layering_policy = self._extract_layering_policy(documents)

        # Region and site documents should result in no parent being found
        # since their schemas will not match that of their parent's.
        for idx in range(1, 3):  # Only region/site have parent.
            prev_schema = documents[idx]['schema']
            documents[idx]['schema'] = test_utils.rand_name('schema')

            layering.DocumentLayering(layering_policy, documents)
            self.assertRegexpMatches(mock_log.info.mock_calls[0][1][0],
                                     'Could not find parent for document .*')
            mock_log.info.reset_mock()

            # Restore schema for next test run.
            documents[idx]['schema'] = prev_schema
