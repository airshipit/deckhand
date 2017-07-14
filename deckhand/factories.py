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

import abc
import copy

from oslo_log import log as logging

from deckhand.tests import test_utils
from deckhand import types

LOG = logging.getLogger(__name__)


class DeckhandFactory(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def gen(self, *args):
        pass

    @abc.abstractmethod
    def gen_test(self, *args, **kwargs):
        pass


class ValidationPolicyFactory(DeckhandFactory):
    """Class for auto-generating validation policy templates for testing."""

    VALIDATION_POLICY_TEMPLATE = {
        "data": {
            "validations": []
        },
        "metadata": {
            "schema": "metadata/Control/v1",
            "name": ""
        },
        "schema": types.VALIDATION_POLICY_SCHEMA
    }

    def __init__(self):
        """Constructor for ``ValidationPolicyFactory``.

        Returns a template whose YAML representation is of the form::

            ---
            schema: deckhand/ValidationPolicy/v1
            metadata:
              schema: metadata/Control/v1
              name: site-deploy-ready
            data:
              validations:
                - name: deckhand-schema-validation
                - name: drydock-site-validation
                  expiresAfter: P1W
                - name: promenade-site-validation
                  expiresAfter: P1W
                - name: armada-deployability-validation
            ...
        """
        pass

    def gen(self, validation_type, status):
        if validation_type not in types.DECKHAND_VALIDATION_TYPES:
            raise ValueError("The validation type must be in %s."
                             % types.DECKHAND_VALIDATION_TYPES)

        validation_policy_template = copy.deepcopy(
            self.VALIDATION_POLICY_TEMPLATE)

        validation_policy_template['metadata'][
            'name'] = validation_type
        validation_policy_template['data']['validations'] = [
            {'name': validation_type, 'status': status}
        ]

        return validation_policy_template

    def gen_test(self, name=None, num_validations=None):
        """Generate the test document template.

        Generate the document template based on the arguments passed to
        the constructor and to this function.
        """
        if not(num_validations and isinstance(num_validations, int)
               and num_validations > 0):
            raise ValueError('The "num_validations" attribute must be integer '
                             'value > 1.')

        if not name:
            name = test_utils.rand_name('validation-policy')
        if not num_validations:
            num_validations = 3

        validations = [
            test_utils.rand_name('validation-name')
            for _ in range(num_validations)]

        validation_policy_template = copy.deepcopy(
            self.VALIDATION_POLICY_TEMPLATE)
        validation_policy_template['metadata']['name'] = name
        validation_policy_template['data']['validations'] = validations

        return validation_policy_template
