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

from oslo_policy import policy

from deckhand.policies import base


validation_policies = [
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'create_validation',
        base.RULE_ADMIN_API,
        "Add the results of a validation for a particular revision.",
        [
            {
                'method': 'POST',
                'path': '/api/v1.0/revisions/{revision_id}/validations'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'list_validations',
        base.RULE_ADMIN_API,
        """"List all validations that have been reported for a revision. Also
lists the validation entries for a particular validation.""",
        [
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions/{revision_id}/validations'
            },
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions/{revision_id}/validations/'
                        '{validation_name}'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'show_validation',
        base.RULE_ADMIN_API,
        """Gets the full details of a particular validation entry, including
all posted error details.""",
        [
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions/{revision_id}/validations/'
                        '{validation_name}/entries/{entry_id}'
            }
        ]),
]


def list_rules():
    return validation_policies
