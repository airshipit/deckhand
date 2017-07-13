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
                'replacePattern': {'type': 'string'}
            },
            'additionalProperties': False,
            # 'replacePattern' is not required.
            'required': ['path']
        },
        'src': {
            'type': 'object',
            'properties': {
                'kind': {'type': 'string'},
                'name': {'type': 'string'},
                'path': {'type': 'string'}
            },
            'additionalProperties': False,
            'required': ['kind', 'name', 'path']
        }
    },
    'additionalProperties': False,
    'required': ['dest', 'src']
}

schema = {
    'type': 'object',
    'properties': {
        'schemaVersion': {
            'type': 'string',
            'pattern': '^([A-Za-z]+\/v[0-9]{1})$'
        },
        # TODO: The kind should be an enum.
        'kind': {'type': 'string'},
        'metadata': {
            'type': 'object',
            'properties': {
                'metadataVersion': {
                    'type': 'string',
                    'pattern': '^([A-Za-z]+\/v[0-9]{1})$'
                },
                'name': {'type': 'string'},
                'labels': {
                    'type': 'object',
                    'properties': {
                        'component': {'type': 'string'},
                        'hostname': {'type': 'string'}
                    },
                    'additionalProperties': False,
                    'required': ['component', 'hostname']
                },
                'layerDefinition': {
                    'type': 'object',
                    'properties': {
                        'layer': {'enum': ['global', 'region', 'site']},
                        'abstract': {'type': 'boolean'},
                        'childSelector': {
                            'type': 'object',
                            'properties': {
                                'label': {'type': 'string'}
                            },
                            'additionalProperties': False,
                            'required': ['label']
                        }
                    },
                    'additionalProperties': False,
                    'required': ['layer', 'abstract', 'childSelector']
                },
                'substitutions': {
                    'type': 'array',
                    'items': substitution_schema
                }
            },
            'additionalProperties': False,
            'required': ['metadataVersion', 'name', 'labels',
                         'layerDefinition', 'substitutions']
        },
        'data': {
            'type': 'object'
        }
    },
    'additionalProperties': False,
    'required': ['schemaVersion', 'kind', 'metadata', 'data']
}
