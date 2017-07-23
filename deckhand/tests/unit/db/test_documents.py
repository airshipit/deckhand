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

    def get_minimal_fixture(self, **kwargs):
        fixture = {'data': 'fake document data',
                   'metadata': 'fake metadata',
                   'kind': 'FakeConfigType',
                   'schemaVersion': 'deckhand/v1'}
        fixture.update(kwargs)
        return fixture


class TestDocumentsApi(base.DeckhandWithDBTestCase):

	def _validate_document(self, expected, actual):
		expected['doc_metadata'] = expected.pop('metadata')
		expected['schema_version'] = expected.pop('schemaVersion')

		# TODO: Validate "status" fields, like created_at.
		self.assertIsInstance(actual, dict)
		for key, val in expected.items():
			self.assertIn(key, actual)
			self.assertEqual(val, actual[key])

	def _validate_revision(self, revision):
		expected_attrs = ('id', 'document_id', 'child_id', 'parent_id')
		for attr in expected_attrs:
			self.assertIn(attr, revision)
			self.assertThat(revision[attr], matchers.MatchesAny(
				matchers.Is(None), matchers.IsInstance(unicode)))

	def test_create_document(self):
		fixture = DocumentFixture().get_minimal_fixture()
		document = db_api.document_create(fixture)
		self._validate_document(fixture, document)

		revision = db_api.revision_get(document['id'])
		self._validate_revision(revision)
		self.assertEqual(document['id'], revision['document_id'])

	def test_create_and_update_document(self):
		"""
		Check that the following relationship is true:

		    parent_document <-- parent_revision
                      ^         /          
                       \     (has child)
					    \	  /
						 \	 /
						  \ /
					      / \
				         /   \
                        /     \
                       /     (has parent)
                      v         \
		    child_document <-- child_revision
		"""
		fixture = DocumentFixture().get_minimal_fixture()
		child_document = db_api.document_create(fixture)

		fixture['metadata'] = 'modified fake metadata'
		parent_document = db_api.document_create(fixture)
		self._validate_document(fixture, parent_document)

		# Validate that the new document was created.
		self.assertEqual('modified fake metadata',
						 parent_document['doc_metadata'])
		self.assertNotEqual(child_document['id'], parent_document['id'])

		# Validate that the parent document has a different revision and
		# that the revisions and document links are correct.
		child_revision = db_api.revision_get(child_document['id'])
		parent_revision = db_api.revision_get(parent_document['id'])
		for revision in (child_revision, parent_revision):
			self._validate_revision(revision)

		self.assertNotEqual(child_revision['id'], parent_revision['id'])
		self.assertEqual(parent_document['id'],
						 parent_revision['document_id'])
		self.assertEqual(child_document['id'], parent_revision['child_id'])
		self.assertEqual(parent_document['id'], child_revision['parent_id'])
