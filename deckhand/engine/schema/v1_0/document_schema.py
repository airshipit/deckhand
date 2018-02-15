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

substitution_schema = {
    'type': 'object',
    'properties': {
        'dest': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'pattern': {'type': 'string'}
            },
            'additionalProperties': False,
            'required': ['path']
        },
        'src': {
            'type': 'object',
            'properties': {
                'schema': {
                    'type': 'string',
                    'pattern': '^[A-Za-z]+/[A-Za-z]+/v\d+(.0)?$'
                },
                'name': {'type': 'string'},
                'path': {'type': 'string'}
            },
            'additionalProperties': False,
            'required': ['schema', 'name', 'path']
        }
    },
    'additionalProperties': False,
    'required': ['dest', 'src']
}

schema = {
    'type': 'object',
    'properties': {
        'schema': {
            'type': 'string',
            'pattern': '^[A-Za-z]+/[A-Za-z]+/v\d+(.0)?$'
        },
        'metadata': {
            'type': 'object',
            'properties': {
                'schema': {
                    'type': 'string',
                    'pattern': '^metadata/Document/v\d+(.0)?$'
                },
                'name': {'type': 'string'},
                'labels': {'type': 'object'},
                'layeringDefinition': {
                    'type': 'object',
                    'properties': {
                        'layer': {'type': 'string'},
                        'abstract': {'type': 'boolean'},
                        # "parentSelector" is optional.
                        'parentSelector': {'type': 'object'},
                        # "actions" is optional.
                        'actions': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'method': {'enum': ['replace', 'delete',
                                                        'merge']},
                                    'path': {'type': 'string'}
                                },
                                'additionalProperties': False,
                                'required': ['method', 'path']
                            }
                        }
                    },
                    'additionalProperties': False,
                    'required': ['layer']
                },
                # "substitutions" is optional.
                'substitutions': {
                    'type': 'array',
                    'items': substitution_schema
                },
                'storagePolicy': {
                    'type': 'string',
                    'enum': ['encrypted', 'cleartext']
                }
            },
            'additionalProperties': False,
            'required': ['schema', 'name', 'layeringDefinition']
        },
        'data': {
            'type': ['string', 'integer', 'array', 'object']
        }
    },
    'additionalProperties': False,
    'required': ['schema', 'metadata', 'data']
}
"""JSON schema against which all documents with ``metadata/Document/v1``
``metadata.schema`` are validated.

.. literalinclude:: ../../deckhand/engine/schema/v1_0/document_schema.py
   :language: python
   :lines: 15-102

This schema is used to sanity-check all "metadata/Document" documents that are
passed to Deckhand. This validation comes into play when a new schema is
registered under the ``data`` section of a ``deckhand/DataSchema/v1`` document.

This schema is only enforced after validation for
:py:data:`~deckhand.engine.schema.base_schema` has passed. Failure to pass
this schema will result in an error entry being created for the validation
with name ``deckhand-schema-validation`` corresponding to the created revision.
"""

__all__ = ['schema']
