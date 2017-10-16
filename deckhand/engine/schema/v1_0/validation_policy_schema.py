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
            'pattern': '^(deckhand/ValidationPolicy/v[1]{1}(\.[0]{1}){0,1})$'
        },
        'metadata': {
            'type': 'object',
            'properties': {
                'schema': {
                    'type': 'string',
                    'pattern': '^(metadata/Control/v[1]{1}(\.[0]{1}){0,1})$'
                },
                'name': {'type': 'string'},
                'storagePolicy': {
                    'type': 'string',
                    'enum': ['encrypted', 'cleartext']
                }
            },
            'additionalProperties': False,
            'required': ['schema', 'name']
        },
        'data': {
            'type': 'object',
            'properties': {
                'validations': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'name': {
                                'type': 'string',
                                'pattern': '^.*-(validation|verification)$'
                            },
                            # 'expiresAfter' is optional.
                            'expiresAfter': {'type': 'string'}
                        },
                        'additionalProperties': False,
                        'required': ['name']
                    }
                }
            },
            'additionalProperties': True,
            'required': ['validations']
        }
    },
    'additionalProperties': False,
    'required': ['schema', 'metadata', 'data']
}
