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

import collections
import re

from oslo_serialization import jsonutils as json
from oslo_utils import uuidutils
import six
import yaml

_URL_RE = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|'
                     '(?:%[0-9a-fA-F][0-9a-fA-F]))+')


class DocumentDict(dict):
    """Wrapper for a document.

    Implements convenient properties for nested, commonly accessed document
    keys. Property setters are only implemented for mutable data.

    Useful for accessing nested dictionary keys without having to worry about
    exceptions getting thrown.

    .. note::

        As a rule of thumb, setters for any metadata properties should be
        avoided. Only implement or use for well-understood edge cases.

    """

    @property
    def meta(self):
        return (self.schema, self.layer, self.name)

    @property
    def metadata(self):
        return self.get('metadata') or DocumentDict({})

    @property
    def data(self):
        return self.get('data')

    @data.setter
    def data(self, value):
        self['data'] = value

    @property
    def name(self):
        return self.metadata.get('name') or ''

    @property
    def schema(self):
        return self.get('schema') or ''

    @property
    def layer(self):
        return self.layering_definition.get('layer') or ''

    @property
    def is_abstract(self):
        return self.layering_definition.get('abstract') is True

    @property
    def is_control(self):
        return self.schema.startswith('deckhand/Control')

    @property
    def layering_definition(self):
        metadata = self.metadata or {}
        return metadata.get('layeringDefinition') or DocumentDict({})

    @property
    def layeringDefinition(self):
        metadata = self.metadata or {}
        return metadata.get('layeringDefinition') or DocumentDict({})

    @property
    def layer_order(self):
        if not self.schema.startswith('deckhand/LayeringPolicy'):
            raise TypeError(
                'layer_order only exists for LayeringPolicy documents')
        return self.data.get('layerOrder', [])

    @property
    def parent_selector(self):
        return self.layering_definition.get(
            'parentSelector') or DocumentDict({})

    @property
    def labels(self):
        return self.metadata.get('labels') or DocumentDict({})

    @property
    def substitutions(self):
        return self.metadata.get('substitutions', [])

    @substitutions.setter
    def substitutions(self, value):
        self.metadata.substitutions = value

    @property
    def actions(self):
        return self.layering_definition.get('actions', [])

    @property
    def storage_policy(self):
        return self.metadata.get('storagePolicy') or ''

    @storage_policy.setter
    def storage_policy(self, value):
        self.metadata['storagePolicy'] = value

    @property
    def is_encrypted(self):
        return self.storage_policy == 'encrypted'

    @property
    def has_barbican_ref(self):
        try:
            secret_ref = self.data
            secret_uuid = secret_ref.split('/')[-1]
        except Exception:
            secret_uuid = None
        return (
            isinstance(secret_ref, six.string_types) and
            _URL_RE.match(secret_ref) and
            'secrets' in secret_ref and
            uuidutils.is_uuid_like(secret_uuid)
        )

    @property
    def is_replacement(self):
        return self.metadata.get('replacement') is True

    @property
    def has_replacement(self):
        return isinstance(self.replaced_by, DocumentDict)

    @property
    def replaced_by(self):
        return getattr(self, '_replaced_by', None)

    @replaced_by.setter
    def replaced_by(self, other):
        setattr(self, '_replaced_by', other)

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True))

    @classmethod
    def from_list(cls, documents):
        """Convert an iterable of documents into instances of this class.

        :param documents: Documents to wrap in this class.
        :type documents: iterable
        """
        if not isinstance(documents, collections.Iterable):
            documents = [documents]

        return [DocumentDict(d) for d in documents]


def document_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', dict(data))


yaml.add_representer(DocumentDict, document_dict_representer)
# Required for py27 compatibility: yaml.safe_dump/safe_dump_all doesn't
# work unless SafeRepresenter add_representer method is called.
safe_representer = yaml.representer.SafeRepresenter
safe_representer.add_representer(DocumentDict, document_dict_representer)
