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

from __future__ import absolute_import

import os

import fixtures
import mock
from oslo_config import cfg
from oslo_log import log as logging
import testtools

from deckhand.conf import config  # noqa: Calls register_opts(CONF)
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import cache
from deckhand.tests import test_utils
from deckhand.tests.unit import fixtures as dh_fixtures

CONF = cfg.CONF
logging.register_options(CONF)
logging.setup(CONF, 'deckhand')

BASE_EXPECTED_FIELDS = ("created_at", "updated_at", "deleted_at", "deleted")
DOCUMENT_EXPECTED_FIELDS = BASE_EXPECTED_FIELDS + (
    "id", "schema", "name", "layer", "metadata", "data", "data_hash",
    "metadata_hash", "revision_id", "bucket_id")
REVISION_EXPECTED_FIELDS = ("id", "documents", "tags")


class DeckhandTestCase(testtools.TestCase):

    def setUp(self):
        super(DeckhandTestCase, self).setUp()
        self.useFixture(fixtures.FakeLogger('deckhand'))
        self.useFixture(dh_fixtures.ConfPatcher(
            api_endpoint='http://127.0.0.1/key-manager', group='barbican'))
        self.useFixture(dh_fixtures.ConfPatcher(
            development_mode=True, group=None))

    def tearDown(self):
        # Clear the cache between tests.
        cache.invalidate()
        super(DeckhandTestCase, self).tearDown()

    def override_config(self, name, override, group=None):
        CONF.set_override(name, override, group)
        self.addCleanup(CONF.clear_override, name, group)

    def assertEmpty(self, collection):
        if isinstance(collection, list):
            self.assertEqual(0, len(collection))
        elif isinstance(collection, dict):
            self.assertEqual(0, len(collection.keys()))

    def assertDictItemsAlmostEqual(self, first, second, ignore):
        """Assert that the items in a dictionary or list of dictionaries
        are equal, except for the keys specified in ``ignore``.

        Both first and second must contain the keys specified in ``ignore``.

        :param first: First dictionary or list of dictionaries to compare.
        :type first: dict or list[dict]
        :param second: Second dictionary or list of dictionaries to compare.
        :type second: dict or list[dict]
        :param ignore: List of keys to ignore in both dictionaries or list
            of dictionaries.
        :type ignore: list or tuple
        """
        if not isinstance(first, list):
            first = [first]
        if not isinstance(second, list):
            second = [second]
        for key in ignore:
            for item in first:
                item.pop(key)
            for item in second:
                item.pop(key)
        self.assertEqual(first, second)

    def patch(self, target, autospec=True, **kwargs):
        """Returns a started `mock.patch` object for the supplied target.

        The caller may then call the returned patcher to create a mock object.

        The caller does not need to call stop() on the returned
        patcher object, as this method automatically adds a cleanup
        to the test class to stop the patcher.

        :param target: String module.class or module.object expression to patch
        :param **kwargs: Passed as-is to `mock.patch`. See mock documentation
                         for details.
        """
        p = mock.patch(target, autospec=autospec, **kwargs)
        m = p.start()
        self.addCleanup(p.stop)
        return m

    def patchobject(self, target, attribute, new=mock.DEFAULT, **kwargs):
        """Convenient wrapper around `mock.patch.object`

        Returns a started mock that will be automatically stopped after the
        test ran.
        """

        p = mock.patch.object(target, attribute, new, **kwargs)
        m = p.start()
        self.addCleanup(p.stop)
        return m


class DeckhandWithDBTestCase(DeckhandTestCase):

    def setUp(self):
        super(DeckhandWithDBTestCase, self).setUp()
        self.override_config(
            'connection', os.environ.get('PIFPAF_URL', 'sqlite://'),
            group='database')
        db_api.setup_db(CONF.database.connection, create_tables=True)
        self.addCleanup(db_api.drop_db)

    def create_documents(self, bucket_name, documents,
                         validation_policies=None):
        if not validation_policies:
            validation_policies = []

        if not isinstance(documents, list):
            documents = [documents]
        if not isinstance(validation_policies, list):
            validation_policies = [validation_policies]

        docs = db_api.documents_create(
            bucket_name, documents, validation_policies)

        return docs

    def show_document(self, **fields):
        doc = db_api.document_get(**fields)

        self.validate_document(actual=doc)

        return doc

    def create_revision(self):
        # Implicitly creates a revision and returns it.
        documents = [DocumentFixture.get_minimal_fixture()]
        bucket_name = test_utils.rand_name('bucket')
        revision_id = self.create_documents(bucket_name, documents)[0][
            'revision_id']
        return revision_id

    def show_revision(self, revision_id):
        revision = db_api.revision_get(revision_id)
        self.validate_revision(revision)
        return revision

    def delete_revisions(self):
        return db_api.revision_delete_all()

    def list_revision_documents(self, revision_id, **filters):
        documents = db_api.revision_documents_get(revision_id, **filters)
        for document in documents:
            self.validate_document(document)
        return documents

    def list_revisions(self):
        return db_api.revision_get_all()

    def rollback_revision(self, revision_id):
        latest_revision = db_api.revision_get_latest()
        return db_api.revision_rollback(revision_id, latest_revision)

    def create_validation(self, revision_id, val_name, val_data):
        return db_api.validation_create(revision_id, val_name, val_data)

    def _validate_object(self, obj):
        for attr in BASE_EXPECTED_FIELDS:
            if attr.endswith('_at'):
                self.assertThat(obj[attr], testtools.matchers.MatchesAny(
                    testtools.matchers.Is(None),
                    testtools.matchers.IsInstance(str)))
            else:
                self.assertIsInstance(obj[attr], bool)

    def validate_document(self, actual, expected=None, is_deleted=False):
        self._validate_object(actual)

        # Validate that the document has all expected fields and is a dict.
        expected_fields = list(DOCUMENT_EXPECTED_FIELDS)
        if not is_deleted:
            expected_fields.remove('deleted_at')

        self.assertIsInstance(actual, dict)
        for field in expected_fields:
            self.assertIn(field, actual)

    def validate_revision(self, revision):
        self._validate_object(revision)

        for attr in REVISION_EXPECTED_FIELDS:
            self.assertIn(attr, revision)


# TODO(felipemonteiro): Move this into a separate module called `fixtures`.
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
                },
                'storagePolicy': test_utils.rand_name('storage_policy')
            },
            'schema': test_utils.rand_name('schema')}
        fixture.update(kwargs)
        return fixture

    @staticmethod
    def get_minimal_multi_fixture(count=2, **kwargs):
        return [DocumentFixture.get_minimal_fixture(**kwargs)
                for _ in range(count)]
