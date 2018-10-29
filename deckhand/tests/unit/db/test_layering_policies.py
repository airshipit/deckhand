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

from deckhand import errors
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit import base


class LayeringPoliciesBaseTest(base.DeckhandWithDBTestCase):

    def setUp(self):
        super(LayeringPoliciesBaseTest, self).setUp()
        # Will create 3 documents: layering policy, plus a global and site
        # document.
        self.documents_factory = factories.DocumentFactory(2, [1, 1])
        self.document_mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }
        self.bucket_name = test_utils.rand_name('bucket')

    def _create_layering_policy(self):
        payload = self.documents_factory.gen_test(self.document_mapping)
        self.create_documents(self.bucket_name, payload)
        return payload[0]


class TestLayeringPolicies(LayeringPoliciesBaseTest):

    def test_update_layering_policy(self):
        layering_policy = self._create_layering_policy()
        layering_policy['data'] = {'data': {'layerOrder': ['region', 'site']}}
        self.create_documents(self.bucket_name, [layering_policy])

    def test_create_new_layering_policy_after_first_deleted(self):
        self._create_layering_policy()
        self.create_documents(self.bucket_name, [])
        self._create_layering_policy()


class TestLayeringPoliciesNegative(LayeringPoliciesBaseTest):

    def test_create_conflicting_layering_policy_fails(self):
        layering_policy = self._create_layering_policy()
        layering_policy['metadata']['name'] = 'another-layering-policy'
        self.assertRaises(errors.SingletonDocumentConflict,
                          self._create_layering_policy)
