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

import testtools

from deckhand.db.sqlalchemy import api as db_api
from deckhand.tests.unit import base


class DocumentFixture(object):

    def get_minimal_fixture(self, **kwargs):
        fixture = {'data': 'fake document data',
                   'metadata': 'fake meta',
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

	def test_create_document(self):
		fixture = DocumentFixture().get_minimal_fixture()
		document = db_api.document_create(fixture)
		self._validate_document(fixture, document)
