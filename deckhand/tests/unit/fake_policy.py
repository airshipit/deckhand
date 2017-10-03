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


policy_data = """
"admin_api": "role:admin"
"deckhand:create_cleartext_documents": "rule:admin_api"
"deckhand:create_encrypted_documents": "rule:admin_api"
"deckhand:list_cleartext_documents": "rule:admin_api"
"deckhand:list_encrypted_documents": "rule:admin_api"
"deckhand:show_revision": "rule:admin_api"
"deckhand:list_revisions": "rule:admin_api"
"deckhand:delete_revisions": "rule:admin_api"
"deckhand:show_revision_diff": "rule:admin_api"
"deckhand:create_tag": "rule:admin_api"
"deckhand:show_tag": "rule:admin_api"
"deckhand:list_tags": "rule:admin_api"
"deckhand:delete_tag": "rule:admin_api"
"deckhand:delete_tags": "rule:admin_api"
"""
