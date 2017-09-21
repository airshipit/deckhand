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


revision_tag_policies = [
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'create_tag',
        base.RULE_ADMIN_API,
        "Create a revision tag.",
        [
            {
                'method': 'POST',
                'path': '/api/v1.0/revisions/{revision_id}/tags'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'show_tag',
        base.RULE_ADMIN_API,
        "Show details for a revision tag.",
        [
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions/{revision_id}/tags/{tag}'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'list_tags',
        base.RULE_ADMIN_API,
        "List all tags for a revision.",
        [
            {
                'method': 'GET',
                'path': '/api/v1.0/revisions/{revision_id}/tags'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'delete_tag',
        base.RULE_ADMIN_API,
        "Delete a revision tag.",
        [
            {
                'method': 'DELETE',
                'path': '/api/v1.0/revisions/{revision_id}/tags/{tag}'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'delete_tags',
        base.RULE_ADMIN_API,
        "Delete all tags for a revision.",
        [
            {
                'method': 'DELETE',
                'path': '/api/v1.0/revisions/{revision_id}/tags'
            }
        ])
]


def list_rules():
    return revision_tag_policies
