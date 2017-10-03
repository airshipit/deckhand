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

import six


class Document(object):
    """Object wrapper for documents.

    After "raw" documents undergo schema validation, they can be wrapped with
    this class to allow nested dictionary entries to be quickly retrieved.
    """

    def __init__(self, data):
        """Constructor for ``Document``.

        :param data: Dictionary of all document data (includes metadata, data,
            schema, etc.).
        """
        self._inner = data

    def to_dict(self):
        return self._inner

    def is_abstract(self):
        """Return whether the document is abstract.

        Not all documents contain this property; in that case they are
        concrete.
        """
        try:
            abstract = self._inner['metadata']['layeringDefinition'][
                'abstract']
            return six.text_type(abstract) == 'True'
        except KeyError:
            return False

    def get_schema(self):
        return self._inner['schema']

    def get_name(self):
        return self._inner['metadata']['name']

    def get_layer(self):
        return self._inner['metadata']['layeringDefinition']['layer']

    def get_parent_selector(self):
        """Return the `parentSelector` for the document.

        The topmost document defined by the `layerOrder` in the LayeringPolicy
        does not have a `parentSelector` as it has no parent.

        :returns: `parentSelcetor` for the document if present, else None.
        """
        try:
            return self._inner['metadata']['layeringDefinition'][
                'parentSelector']
        except KeyError:
            return None

    def get_labels(self):
        return self._inner['metadata']['labels']

    def get_substitutions(self):
        return self._inner['metadata'].get('substitutions', None)

    def get_actions(self):
        try:
            return self._inner['metadata']['layeringDefinition']['actions']
        except KeyError:
            return []

    def get_children(self, nested=False):
        """Get document children, if any.

        :param nested: Recursively retrieve all children for each child
            document.
        :type nested: boolean
        :returns: List of children of type `Document`.
        """
        if not nested:
            return self._inner.get('children', [])
        else:
            return self._get_nested_children(self, [])

    def _get_nested_children(self, doc, nested_children):
        for child in doc.get('children', []):
            nested_children.append(child)
            if 'children' in child._inner:
                self._get_nested_children(child, nested_children)
        return nested_children

    def get(self, k, default=None):
        return self.__getitem__(k, default=default)

    def __getitem__(self, k, default=None):
        return self._inner.get(k, default)

    def __setitem__(self, k, val):
        self._inner[k] = val

    def __delitem__(self, k):
        if self.__contains__(k):
            del self._inner[k]

    def __contains__(self, k):
        return self.get(k, default=None) is not None

    def __missing__(self, k):
        return not self.__contains__(k)

    def __repr__(self):
        return '(%s, %s)' % (self.get_schema(), self.get_name())

    def __str__(self):
        return str(self._inner)
