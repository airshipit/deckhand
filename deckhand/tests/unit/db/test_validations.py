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

import yaml

from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base
from deckhand import types

ARMADA_VALIDATION_POLICY = """
---
status: success
validator:
  name: armada
  version: 1.1.3
"""

PROMENADE_VALIDATION_POLICY = """
---
status: failure
errors:
  - documents:
      - schema: promenade/Node/v1
        name: node-document-name
      - schema: promenade/Masters/v1
        name: kubernetes-masters
    message: Node has master role, but not included in cluster masters list.
validator:
  name: promenade
  version: 1.1.2
"""


class TestValidations(base.TestDbBase):

    def _create_revision_with_validation_policy(self):
        vp_factory = factories.ValidationPolicyFactory()
        validation_policy = vp_factory.gen(types.DECKHAND_SCHEMA_VALIDATION,
                                           'success')
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, [validation_policy])
        revision_id = documents[0]['revision_id']
        return revision_id

    def test_create_validation(self):
        revision_id = self._create_revision_with_validation_policy()
        validation_name = test_utils.rand_name('validation')

        payload = yaml.safe_load(PROMENADE_VALIDATION_POLICY)
        created_validation = self.create_validation(
            revision_id, validation_name, payload)

        self.assertIsInstance(created_validation, dict)
        self.assertEqual(validation_name, created_validation['name'])
        self.assertEqual(payload['status'], created_validation['status'])
        self.assertEqual(payload['validator'], created_validation['validator'])

    def test_create_multiple_validations(self):
        revision_id = self._create_revision_with_validation_policy()

        for val_policy in (ARMADA_VALIDATION_POLICY,
                           PROMENADE_VALIDATION_POLICY):
            validation_name = test_utils.rand_name('validation')

            payload = yaml.safe_load(val_policy)
            created_validation = self.create_validation(
                revision_id, validation_name, payload)

            payload.update({'name': validation_name})
            self.assertIsInstance(created_validation, dict)
            self.assertEqual(validation_name, created_validation['name'])
            self.assertEqual(payload['status'], created_validation['status'])
            self.assertEqual(payload['validator'],
                             created_validation['validator'])
