# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from deckhand import errors
from deckhand import factories
from deckhand.tests.unit.engine import test_document_layering


class TestDocumentLayeringReplacementNegative(
        test_document_layering.TestDocumentLayering):

    def test_replacement_with_incompatible_name_or_schema_raises_exc(self):
        """Validate that attempting to replace a child with its parent when
        they don't have the same ``metadata.name`` and ``schema`` results in
        exception.

        global
          |
        site (replacement: true, incompatible with parent)
        """
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({})

        # Validate case where names mismatch.
        documents[1]['metadata']['name'] = 'foo'
        documents[2]['metadata']['replacement'] = True
        documents[2]['metadata']['name'] = 'bar'

        error_re = (r'.*Document replacement requires that both documents '
                    'have the same `schema` and `metadata.name`.')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)

        # Validate case where schemas mismatch.
        documents[1]['metadata']['schema'] = 'example/Kind/v1'
        documents[2]['metadata']['replacement'] = True
        documents[2]['metadata']['schema'] = 'example/Other/v1'

        error_re = (r'Document replacement requires that both documents '
                    'have the same `schema` and `metadata.name`.')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)

    def test_non_replacement_same_name_and_schema_as_parent_raises_exc(self):
        """Validate that a non-replacement document (i.e. regular document
        without `replacement: true`) cannot have the same schema/name as
        another document.

        global (replacement: false)
          |
        site (replacement: false)
        """
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({})

        documents[1]['metadata']['name'] = 'foo'
        documents[2]['metadata']['replacement'] = False
        documents[2]['metadata']['name'] = 'foo'

        error_re = (r'.*Non-replacement documents cannot have the same '
                    '`schema` and `metadata.name`.*')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)

    def test_replacement_without_parent_raises_exc(self):
        """Validate that attempting to do replacement without a parent document
        raises an exception.

        None
          |
        site (replacement: true)
        """
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({})

        documents[2]['metadata']['replacement'] = True
        documents[2]['metadata']['layeringDefinition'].pop('parentSelector')

        error_re = (r'Document replacement requires that the document with '
                    '`replacement: true` have a parent.')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)

    def test_replacement_with_parent_replace_true_raises_exc(self):
        """Validate that a parent document with replacement: true necessarily
        fails if it itself doesn't have a parent.

        None
          |
        global (replacement: true)
          |
        site
        """
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({})

        documents[1]['metadata']['replacement'] = True

        error_re = (r'Document replacement requires that the document with '
                    '`replacement: true` have a parent.')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)

    def test_replacement_that_is_replaced_raises_exc(self):
        """Validate that attempting to replace a replacement document raises an
        exception.

        global
          |
        region (replacement: true)
          |
        site (replacement: true)
        """
        doc_factory = factories.DocumentFactory(3, [1, 1, 1])
        documents = doc_factory.gen_test({}, region_abstract=False,
                                         site_abstract=False)

        for document in documents[1:]:
            document['metadata']['name'] = 'foo'
            document['schema'] = 'example/Kind/v1'

        documents[2]['metadata']['replacement'] = True
        documents[3]['metadata']['replacement'] = True

        error_re = (r'A replacement document cannot itself be replaced by '
                    'another document.')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)

    def test_replacement_true_with_parent_replacement_true_raises_exc(self):
        """Validate that when documents have the same ``metadata.name`` and
        ``schema`` existing in different layers without any of them
        having ``replacement = true`` raises an exception
        """
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test({})

        for document in documents[1:]:
            document['metadata']['name'] = 'foo'
            document['schema'] = 'example/Kind/v1'
            document['metadata']['replacement'] = False
            if 'parentSelector' in document['metadata']['layeringDefinition']:
                document['metadata']['layeringDefinition'].pop(
                    'parentSelector')

        error_re = (
            r'More than one document with the same name and schema was found, '
            'but none has `replacement: true`.*')
        self.assertRaisesRegexp(errors.InvalidDocumentReplacement, error_re,
                                self._test_layering, documents)
