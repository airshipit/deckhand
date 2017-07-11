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
        'dest': {'type': 'string'},
        'src': {
            'type': 'object',
            'properties': {
                'apiVersion': {
                    'type': 'string',
                    'choices': ['deckhand/v1']
                },
                'kind': {'type': 'string'},
                'name': {'type': 'string'}
            },
            'additionalProperties': False,
            'required': ['apiVersion', 'kind', 'name']
        }
    },
    'additionalProperties': False,
    'required': ['dest', 'src']
}

schema = {
    'type': 'object',
    'properties': {
        'apiVersion': {
            'type': 'string',
            'pattern': '^([A-Za-z]+\/v[0-9]{1})$'
        },
        'kind': {
            'type': 'string',
            'pattern': '^([A-Za-z]+$'
        },
        'metadata': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'storage': {'type': 'string'},
                'substitutions': {
                    'type': 'array',
                    'items': substitution_schema
                }
            },
            'additionalProperties': False,
            'required': ['name', 'storage', 'substitutions']
        },
        'data': {
            'type': 'object'
        }
    },
    'additionalProperties': False,
    'required': ['apiVersion', 'kind', 'metadata', 'data']
}
