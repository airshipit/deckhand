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

import falcon
from falcon import testing as falcon_testing

from deckhand.control import api
from deckhand import factories
from deckhand.tests.unit import base as test_base


class TestFunctionalBase(test_base.DeckhandWithDBTestCase,
                         falcon_testing.TestCase):
    """Base class for functional testing."""

    def setUp(self):
        super(TestFunctionalBase, self).setUp()
        self.app = falcon_testing.TestClient(api.start_api())
        self.validation_policy_factory = factories.ValidationPolicyFactory()

    @classmethod
    def setUpClass(cls):
        super(TestFunctionalBase, cls).setUpClass()
        mock.patch.object(api, '__setup_logging').start()
