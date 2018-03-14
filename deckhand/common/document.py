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
import functools
import inspect

from oslo_serialization import jsonutils as json

from deckhand.common import utils


class DocumentDict(dict):
    """Wrapper for a document.

    Implements convenient properties for nested, commonly accessed document
    keys. Property setters are only implemented for mutable data.

    Useful for accessing nested dictionary keys without having to worry about
    exceptions getting thrown.

    """

    def __init__(self, *args, **kwargs):
        super(DocumentDict, self).__init__(*args, **kwargs)
        self._replaced_by = None

    @classmethod
    def from_dict(self, documents):
        """Convert a list of documents or single document into an instance of
        this class.

        :param documents: Documents to wrap in this class.
        :type documents: list or dict
        """
        if isinstance(documents, collections.Iterable):
            return [DocumentDict(d) for d in documents]
        return DocumentDict(documents)

    @property
    def meta(self):
        return (self.schema, self.layer, self.name)

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
        return utils.jsonpath_parse(self, 'metadata.name')

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

    @property
    def is_replacement(self):
        return utils.jsonpath_parse(self, 'metadata.replacement') is True

    @property
    def has_replacement(self):
        return isinstance(self._replaced_by, DocumentDict)

    @property
    def replaced_by(self):
        return self._replaced_by

    @replaced_by.setter
    def replaced_by(self, other):
        self._replaced_by = other

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True))


def wrap_documents(f):
    """Decorator to wrap dictionary-formatted documents in instances of
    ``DocumentDict``.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        fargs = inspect.getargspec(f)
        if 'documents' in fargs[0]:
            pos = fargs[0].index('documents')
            new_args = list(args)
            if new_args[pos] and not isinstance(
                    new_args[pos][0], DocumentDict):
                new_args[pos] = DocumentDict.from_dict(args[pos])
            return f(*tuple(new_args), **kwargs)
    return wrapper
