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
import uuid

import testtools
from testtools import matchers

from deckhand.db.sqlalchemy import api as db_api
from deckhand.tests import test_utils
from deckhand.tests.unit import base

BASE_EXPECTED_FIELDS = ("created_at", "updated_at", "deleted_at", "deleted")
DOCUMENT_EXPECTED_FIELDS = BASE_EXPECTED_FIELDS + (
    "id", "schema", "name", "metadata", "data", "revision_id")
REVISION_EXPECTED_FIELDS = BASE_EXPECTED_FIELDS + (
    "id", "child_id", "parent_id", "documents")


class DocumentFixture(object):

    @staticmethod
    def get_minimal_fixture(**kwargs):
        fixture = {'data': test_utils.rand_name('data'),
                   'metadata': {'name': test_utils.rand_name('name')},
                   'schema': test_utils.rand_name('schema', prefix='deckhand')}
        fixture.update(kwargs)
        return fixture

    @staticmethod
    def get_minimal_multi_fixture(count=2, **kwargs):
        return [DocumentFixture.get_minimal_fixture(**kwargs) 
                for _ in range(count)]


class TestDocumentsApi(base.DeckhandWithDBTestCase):

    def _create_documents(self, payload):
        if not isinstance(payload, list):
            payload = [payload]

        docs = db_api.documents_create(payload)
        for idx, doc in enumerate(docs):
            self._validate_document(expected=payload[idx], actual=doc)
        return docs

    def _get_document(self, **fields):
        doc = db_api.document_get(**fields)
        self._validate_document(actual=doc)
        return doc

    def _get_revision(self, revision_id):
        revision = db_api.revision_get(revision_id)
        self._validate_revision(revision)
        return revision

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

    def test_create_and_get_document(self):
        payload = DocumentFixture.get_minimal_fixture()
        documents = self._create_documents(payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(1, len(documents))

        for document in documents:
            retrieved_document = self._get_document(id=document['id'])
            self.assertEqual(document, retrieved_document)

    def test_create_document_again_with_no_changes(self):
        payload = DocumentFixture.get_minimal_fixture()
        self._create_documents(payload)
        documents = self._create_documents(payload)

        self.assertIsInstance(documents, list)
        self.assertEmpty(documents)

    def test_create_document_and_get_revision(self):
        payload = DocumentFixture.get_minimal_fixture()
        documents = self._create_documents(payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(1, len(documents))

        for document in documents:
            revision = self._get_revision(document['revision_id'])
            self._validate_revision(revision)
            self.assertEqual(document['revision_id'], revision['id'])

    def test_get_documents_by_revision_id(self):
        payload = DocumentFixture.get_minimal_fixture()
        documents = self._create_documents(payload)

        revision = self._get_revision(documents[0]['revision_id'])
        self.assertEqual(1, len(revision['documents']))
        self.assertEqual(documents[0], revision['documents'][0])

    def test_get_multiple_documents_by_revision_id(self):
        payload = DocumentFixture.get_minimal_multi_fixture(count=3)
        documents = self._create_documents(payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(3, len(documents))

        for document in documents:
            revision = self._get_revision(document['revision_id'])
            self._validate_revision(revision)
            self.assertEqual(document['revision_id'], revision['id'])
