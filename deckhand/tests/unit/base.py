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

from deckhand.db.sqlalchemy import api as db_api

CONF = cfg.CONF
logging.register_options(CONF)
logging.setup(CONF, 'deckhand')


class DeckhandTestCase(testtools.TestCase):

    def setUp(self):
        super(DeckhandTestCase, self).setUp()
        self.useFixture(fixtures.FakeLogger('deckhand'))

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

    def patchobject(self, target, attribute, new=mock.DEFAULT, autospec=True):
        """Convenient wrapper around `mock.patch.object`

        Returns a started mock that will be automatically stopped after the
        test ran.
        """

        p = mock.patch.object(target, attribute, new, autospec=autospec)
        m = p.start()
        self.addCleanup(p.stop)
        return m


class DeckhandWithDBTestCase(DeckhandTestCase):

    def setUp(self):
        super(DeckhandWithDBTestCase, self).setUp()
        self.override_config(
            'connection', os.environ.get('DATABASE_URL', 'sqlite://'),
            group='database')
        db_api.setup_db()
        self.addCleanup(db_api.drop_db)
