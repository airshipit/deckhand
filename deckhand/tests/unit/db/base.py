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

import testtools
from testtools import matchers

from deckhand.db.sqlalchemy import api as db_api
from deckhand.tests import test_utils
from deckhand.tests.unit import base

BASE_EXPECTED_FIELDS = ("created_at", "updated_at", "deleted_at", "deleted")
DOCUMENT_EXPECTED_FIELDS = BASE_EXPECTED_FIELDS + (
    "id", "schema", "name", "metadata", "data", "revision_id")
REVISION_EXPECTED_FIELDS = BASE_EXPECTED_FIELDS + (
    "id", "documents", "validation_policies")


class DocumentFixture(object):

    @staticmethod
    def get_minimal_fixture(**kwargs):
        fixture = {
            'data': {
                test_utils.rand_name('key'): test_utils.rand_name('value')
            },
            'metadata': {
                'name': test_utils.rand_name('metadata_data'),
                'label': test_utils.rand_name('metadata_label'),
                'layeringDefinition': {
                    'abstract': test_utils.rand_bool(),
                    'layer': test_utils.rand_name('layer')
                }
            },
            'schema': test_utils.rand_name('schema')}
        fixture.update(kwargs)
        return fixture

    @staticmethod
    def get_minimal_multi_fixture(count=2, **kwargs):
        return [DocumentFixture.get_minimal_fixture(**kwargs)
                for _ in range(count)]


class TestDbBase(base.DeckhandWithDBTestCase):

    def _create_documents(self, documents, validation_policies=None):
        if not validation_policies:
            validation_policies = []

        if not isinstance(documents, list):
            documents = [documents]
        if not isinstance(validation_policies, list):
            validation_policies = [validation_policies]

        docs = db_api.documents_create(documents, validation_policies)
        for idx, doc in enumerate(docs):
            self._validate_document(expected=documents[idx], actual=doc)
        return docs

    def _get_document(self, **fields):
        doc = db_api.document_get(**fields)
        self._validate_document(actual=doc)
        return doc

    def _get_revision(self, revision_id):
        revision = db_api.revision_get(revision_id)
        self._validate_revision(revision)
        return revision

    def _get_revision_documents(self, revision_id, **filters):
        documents = db_api.revision_get_documents(revision_id, **filters)
        for document in documents:
            self._validate_document(document)
        return documents

    def _list_revisions(self):
        return db_api.revision_get_all()

    def _validate_object(self, obj):
        for attr in BASE_EXPECTED_FIELDS:
            if attr.endswith('_at'):
                self.assertThat(obj[attr], matchers.MatchesAny(
                        matchers.Is(None), matchers.IsInstance(str)))
            else:
                self.assertIsInstance(obj[attr], bool)

    def _validate_document(self, actual, expected=None, is_deleted=False):
        self._validate_object(actual)

        # Validate that the document has all expected fields and is a dict.
        expected_fields = list(DOCUMENT_EXPECTED_FIELDS)
        if not is_deleted:
            expected_fields.remove('deleted_at')

        self.assertIsInstance(actual, dict)
        for field in expected_fields:
            self.assertIn(field, actual)

        if expected:
            # Validate that the expected values are equivalent to actual
            # values.
            for key, val in expected.items():
                self.assertEqual(val, actual[key])

    def _validate_revision(self, revision):
        self._validate_object(revision)

        for attr in REVISION_EXPECTED_FIELDS:
            self.assertIn(attr, revision)
