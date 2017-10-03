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


document_policies = [
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'create_cleartext_documents',
        base.RULE_ADMIN_API,
        """Create a batch of documents specified in the request body, whereby
a new revision is created. Also, roll back a revision to a previous one in the
revision history, whereby the target revision's documents are re-created for
the new revision.""",
        [
            {
                'method': 'PUT',
                'path': '/api/v1.0/bucket/{bucket_name}/documents'
            },
            {
                'method': 'POST',
                'path': '/api/v1.0/rollback/{target_revision_id}'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'create_encrypted_documents',
        base.RULE_ADMIN_API,
        """Create a batch of documents specified in the request body, whereby
a new revision is created. Also, roll back a revision to a previous one in the
history, whereby the target revision's documents are re-created for the new
revision.

Only enforced after ``create_cleartext_documents`` passes.

Conditionally enforced for the endpoints below if the any of the documents in
the request body have a ``metadata.storagePolicy`` of "encrypted".""",
        [
            {
                'method': 'PUT',
                'path': '/api/v1.0/bucket/{bucket_name}/documents'
            },
            {
                'method': 'POST',
                'path': '/api/v1.0/rollback/{target_revision_id}'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'list_cleartext_documents',
        base.RULE_ADMIN_API,
        """List cleartext documents for a revision (with no layering or
substitution applied) as well as fully layered and substituted concrete
documents.""",
        [
            {
                'method': 'GET',
                'path': 'api/v1.0/revisions/{revision_id}/documents'
            },
            {
                'method': 'GET',
                'path': 'api/v1.0/revisions/{revision_id}/rendered-documents'
            }
        ]),
    policy.DocumentedRuleDefault(
        base.POLICY_ROOT % 'list_encrypted_documents',
        base.RULE_ADMIN_API,
        """List encrypted documents for a revision (with no layering or
substitution applied) as well as fully layered and substituted concrete
documents.

Only enforced after ``list_cleartext_documents`` passes.

Conditionally enforced for the endpoints below if any of the documents in the
request body have a ``metadata.storagePolicy`` of "encrypted". If policy
enforcement fails, encrypted documents are exluded from the response.""",
        [
            {
                'method': 'GET',
                'path': 'api/v1.0/revisions/{revision_id}/documents'
            },
            {
                'method': 'GET',
                'path': 'api/v1.0/revisions/{revision_id}/rendered-documents'
            }
        ]),
]


def list_rules():
    return document_policies
