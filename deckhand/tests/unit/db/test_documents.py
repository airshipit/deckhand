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
from deckhand.tests.unit import base


class DocumentFixture(object):

    EXPECTED_FIELDS = ("created_at", "updated_at", "deleted_at", "deleted",
                       "id", "schema", "name", "_metadata", "data",
                       "revision_id")

    @staticmethod
    def get_minimal_fixture(**kwargs):
        fixture = {'data': 'fake document data',
                   'metadata': {'name': 'fake metadata'},
                   'schema': 'deckhand/v1'}
        fixture.update(kwargs)
        return fixture


class TestDocumentsApi(base.DeckhandWithDBTestCase):

    def _create_document(self, payload):
        doc = db_api.document_create(payload)
        self._validate_document(expected=payload, actual=doc)
        return doc

    def _get_document(self, **fields):
        doc = db_api.document_get(**fields)
        self._validate_document(actual=doc)
        return doc

    def _get_revision(self, revision_id):
        revision = db_api.revision_get(revision_id)
        self._validate_revision(revision)
        return revision

    def _validate_document(self, actual, expected=None, is_deleted=False):
        # Validate that the document has all expected fields and is a dict.
        expected_fields = list(DocumentFixture.EXPECTED_FIELDS)
        if not is_deleted:
            expected_fields.remove('deleted_at')

        self.assertIsInstance(actual, dict)
        for field in expected_fields:
            self.assertIn(field, actual)

        # ``_metadata`` is used in the DB schema as ``metadata`` is reserved.
        actual['metadata'] = actual.pop('_metadata')

        if expected:
            # Validate that the expected values are equivalent to actual
            # values.
            for key, val in expected.items():
                self.assertEqual(val, actual[key])

    def _validate_revision(self, revision):
        expected_attrs = ('id', 'child_id', 'parent_id')
        for attr in expected_attrs:
            self.assertIn(attr, revision)
            self.assertThat(revision[attr], matchers.MatchesAny(
                matchers.Is(None), matchers.IsInstance(unicode)))

    def _validate_revision_connections(self, parent_document, parent_revision,
                                       child_document, child_revision,
                                       parent_child_connected=True):
        self.assertNotEqual(child_revision['id'], parent_revision['id'])
        self.assertEqual(parent_document['revision_id'], parent_revision['id'])
        self.assertEqual(child_document['revision_id'], child_revision['id'])

        # Validate that the revisions are distinct and connected together.
        if parent_child_connected:
            self.assertEqual(parent_revision['child_id'], child_revision['id'])
            self.assertEqual(
                child_revision['parent_id'], parent_revision['id'])
        # Validate that the revisions are distinct but unconnected.
        else:
            self.assertIsNone(parent_revision['child_id'])
            self.assertIsNone(child_revision['parent_id'])

    def test_create_and_get_document(self):
        payload = DocumentFixture.get_minimal_fixture()
        document = self._create_document(payload)
        retrieved_document = self._get_document(id=document['id'])
        self.assertEqual(document, retrieved_document)

    def test_create_document_and_get_revision(self):
        payload = DocumentFixture.get_minimal_fixture()
        document = self._create_document(payload)

        revision = self._get_revision(document['revision_id'])
        self._validate_revision(revision)
        self.assertEqual(document['revision_id'], revision['id'])

    def test_create_and_update_document(self):
        """
        Check that the following relationship is true:

            parent_document --> parent_revision
                                 |         ^
                             (has child) (has parent)
                                 v         |
            child_document --> child_revision
        """
        child_payload = DocumentFixture.get_minimal_fixture()
        child_document = self._create_document(child_payload)

        parent_payload = DocumentFixture.get_minimal_fixture()
        parent_payload['data'] = 'fake updated document data'
        parent_document = self._create_document(parent_payload)

        # Validate that the new document was created.
        self.assertEqual('fake updated document data', parent_document['data'])
        self.assertNotEqual(child_document['id'], parent_document['id'])

        # Validate that the parent document has a different revision and
        # that the revisions and document links are correct.
        child_revision = self._get_revision(child_document['revision_id'])
        parent_revision = self._get_revision(parent_document['revision_id'])

        self._validate_revision_connections(
            parent_document, parent_revision, child_document, child_revision)

    def test_create_and_update_document_schema(self):
        """
        Check that the following relationship is true:

            parent_document --> parent_revision
            child_document --> child_revision

        "schema" is unique so changing it results in a new document being
        created.
        """
        child_payload = DocumentFixture.get_minimal_fixture()
        child_document = self._create_document(child_payload)

        parent_payload = DocumentFixture.get_minimal_fixture()
        parent_payload['schema'] = 'deckhand/v2'
        parent_document = self._create_document(parent_payload)

        # Validate that the new document was created.
        self.assertEqual('deckhand/v2', parent_document['schema'])
        self.assertNotEqual(child_document['id'], parent_document['id'])

        # Validate that the parent document has a different revision and
        # that the revisions and document links are correct.
        child_revision = self._get_revision(child_document['revision_id'])
        parent_revision = self._get_revision(parent_document['revision_id'])

        self._validate_revision_connections(
            parent_document, parent_revision, child_document, child_revision,
            False)

    def test_create_and_update_document_metadata_name(self):
        """
        Check that the following relationship is true:

            parent_document --> parent_revision
            child_document --> child_revision

        "metadata.name" is unique so changing it results in a new document
        being created.
        """
        child_payload = DocumentFixture.get_minimal_fixture()
        child_document = self._create_document(child_payload)

        parent_payload = DocumentFixture.get_minimal_fixture()
        parent_payload['metadata'] = {'name': 'fake updated metadata'}
        parent_document = self._create_document(parent_payload)

        # Validate that the new document was created.
        self.assertEqual({'name': 'fake updated metadata'},
                         parent_document['metadata'])
        self.assertNotEqual(child_document['id'], parent_document['id'])

        # Validate that the parent document has a different revision and
        # that the revisions and document links are correct.
        child_revision = self._get_revision(child_document['revision_id'])
        parent_revision = self._get_revision(parent_document['revision_id'])

        self._validate_revision_connections(
            parent_document, parent_revision, child_document, child_revision,
            False)
