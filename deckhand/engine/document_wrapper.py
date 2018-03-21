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

from oslo_serialization import jsonutils as json

from deckhand import utils


class DocumentDict(dict):
    """Wrapper for a document.

    Implements convenient properties for nested, commonly accessed document
    keys. Property setters are only implemented for mutable data.

    Useful for accessing nested dictionary keys without having to worry about
    exceptions getting thrown.

    """

    @property
    def is_abstract(self):
        return utils.jsonpath_parse(
            self, 'metadata.layeringDefinition.abstract') is True

    @property
    def is_control(self):
        return self.metadata.get('schema', '').startswith('deckhand/Control')

    @property
    def schema(self):
        schema = self.get('schema')
        return schema if schema is not None else ''

    @property
    def metadata(self):
        metadata = self.get('metadata')
        return metadata if metadata is not None else {}

    @property
    def data(self):
        data = self.get('data')
        return data if data is not None else {}

    @data.setter
    def data(self, value):
        self['data'] = value

    @property
    def name(self):
        return utils.jsonpath_parse(self, 'metadata.name') or ''

    @property
    def layering_definition(self):
        return utils.jsonpath_parse(self, 'metadata.layeringDefinition')

    @property
    def layer(self):
        return utils.jsonpath_parse(
            self, 'metadata.layeringDefinition.layer')

    @property
    def layer_order(self):
        return utils.jsonpath_parse(self, 'data.layerOrder')

    @property
    def parent_selector(self):
        return utils.jsonpath_parse(
            self, 'metadata.layeringDefinition.parentSelector') or {}

    @property
    def labels(self):
        return utils.jsonpath_parse(self, 'metadata.labels') or {}

    @property
    def substitutions(self):
        return utils.jsonpath_parse(self, 'metadata.substitutions') or []

    @substitutions.setter
    def substitutions(self, value):
        return utils.jsonpath_replace(self, value, 'metadata.substitutions')

    @property
    def actions(self):
        return utils.jsonpath_parse(
            self, 'metadata.layeringDefinition.actions') or []

    @property
    def storage_policy(self):
        return utils.jsonpath_parse(self, 'metadata.storagePolicy') or ''

    @property
    def is_encrypted(self):
        return self.storage_policy == 'encrypted'

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True))
