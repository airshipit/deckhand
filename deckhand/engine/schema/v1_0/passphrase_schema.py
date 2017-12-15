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
            'pattern': '^deckhand/Passphrase/v\d+(.0)?$'
        },
        'metadata': {
            'type': 'object',
            'properties': {
                'schema': {
                    'type': 'string',
                    'pattern': '^metadata/Document/v\d+(.0)?$',
                },
                'name': {'type': 'string'},
                # Not strictly needed.
                'layeringDefinition': {
                    'type': 'object',
                    'properties': {
                        'layer': {'type': 'string'},
                        'abstract': {'type': 'boolean'}
                    }
                },
                'storagePolicy': {
                    'type': 'string',
                    'enum': ['encrypted', 'cleartext']
                }
            },
            'additionalProperties': False,
            'required': ['schema', 'name', 'storagePolicy']
        },
        'data': {'type': 'string'}
    },
    'additionalProperties': False,
    'required': ['schema', 'metadata', 'data']
}
"""JSON schema against which all documents with ``deckhand/Passphrase/v1``
``schema`` are validated.

.. literalinclude:: ../../deckhand/engine/schema/v1_0/passphrase_schema.py
   :language: python
   :lines: 15-49

This schema is used to sanity-check all Passphrase documents that are
passed to Deckhand. This schema is only enforced after validation for
:py:data:`~deckhand.engine.schema.base_schema` has passed. Failure to pass
this schema will result in an error entry being created for the validation
with name ``deckhand-schema-validation`` corresponding to the created revision.
"""

__all__ = ['schema']
