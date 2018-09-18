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


revision_policies = [
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'show_revision',
        base.RULE_ADMIN_API,
        "Show details for a revision.",
        [
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions/{revision_id}'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'list_revisions',
        base.RULE_ADMIN_API,
        "List all revisions.",
        [
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'delete_revisions',
        base.RULE_ADMIN_API,
        """Delete all revisions. Warning: this is equivalent to purging the
database.""",
        [
            {
                'method': 'DELETE',
                'path': '/api/v1.0/revisions'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'show_revision_deepdiff',
        base.RULE_ADMIN_API,
        "Show revision deep diff between two revisions.",
        [
            {
                'method': 'GET',
                'path': ('/api/v1.0/revisions/{revision_id}/deepdiff/'
                         '{comparison_revision_id}')
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'show_revision_diff',
        base.RULE_ADMIN_API,
        "Show revision diff between two revisions.",
        [
            {
                'method': 'GET',
                'path': ('/api/v1.0/revisions/{revision_id}/diff/'
                         '{comparison_revision_id}')
            }
        ]),
]


def list_rules():
    return revision_policies
