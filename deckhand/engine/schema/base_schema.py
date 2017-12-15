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

schema = {
    'type': 'object',
    'properties': {
        'schema': {
            'type': 'string',
            # Currently supported versions include v1/v1.0 only.
            'pattern': '^[A-Za-z]+\/[A-Za-z]+\/v\d+(.0)?$'
        },
        'metadata': {
            'type': 'object',
            'properties': {
                'schema': {'type': 'string'},
                'name': {'type': 'string'}
            },
            'additionalProperties': True,
            'required': ['schema', 'name']
        },
        'data': {'type': ['string', 'integer', 'array', 'object']}
    },
    'additionalProperties': False,
    'required': ['schema', 'metadata']
}
"""Base JSON schema against which all Deckhand documents are validated.

.. literalinclude:: ../../deckhand/engine/schema/base_schema.py
   :language: python
   :lines: 15-36

This schema is used to sanity-check all documents that are passed to Deckhand.
Failure to pass this schema results in a critical error.
"""

__all__ = ['schema']
