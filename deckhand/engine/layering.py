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
import copy

from oslo_log import log as logging
import six

from deckhand.engine import document
from deckhand.engine import secrets_manager
from deckhand.engine import utils
from deckhand import errors
from deckhand import types

LOG = logging.getLogger(__name__)


class DocumentLayering(object):
    """Class responsible for handling document layering.

    Layering is controlled in two places:

    1. The ``LayeringPolicy`` control document, which defines the valid layers
       and their order of precedence.
    2. In the ``metadata.layeringDefinition`` section of normal
       (``metadata.schema=metadata/Document/v1.0``) documents.

    .. note::

        Only documents with the same ``schema`` are allowed to be layered
        together into a fully rendered document.
    """

    SUPPORTED_METHODS = ('merge', 'replace', 'delete')

    def _calc_document_children(self):
        """Determine each document's children.

        For each document, attempts to find the document's children. Adds a new
        key called "children" to the document's dictionary.

        .. note::

            A document should only have exactly one parent.

            If a document does not have a parent, then its layer must be
            the topmost layer defined by the ``layerOrder``.

        :returns: Ordered list of documents that need to be layered. Each
            document contains a "children" property in addition to original
            data. List of documents returned is ordered from highest to lowest
            layer.
        :rtype: list of deckhand.engine.document.Document objects.
        :raises IndeterminateDocumentParent: If more than one parent document
            was found for a document.
        """
        layered_docs = list(
            filter(lambda x: 'layeringDefinition' in x['metadata'],
                self.documents))

        # ``all_children`` is a counter utility for verifying that each
        # document has exactly one parent.
        all_children = collections.Counter()

        def _get_children(doc):
            children = []
            doc_layer = doc.get_layer()
            try:
                next_layer_idx = self.layer_order.index(doc_layer) + 1
                children_doc_layer = self.layer_order[next_layer_idx]
            except IndexError:
                # The lowest layer has been reached, so no children. Return
                # empty list.
                return children

            for other_doc in layered_docs:
                # Documents with different schemas are never layered together,
                # so consider only documents with same schema as candidates.
                is_potential_child = (
                    other_doc.get_layer() == children_doc_layer and
                    other_doc.get_schema() == doc.get_schema()
                )
                if (is_potential_child):
                    # A document can have many labels but should only have one
                    # explicit label for the parentSelector.
                    parent_sel = other_doc.get_parent_selector()
                    parent_sel_key = list(parent_sel.keys())[0]
                    parent_sel_val = list(parent_sel.values())[0]
                    doc_labels = doc.get_labels()

                    if (parent_sel_key in doc_labels and
                        parent_sel_val == doc_labels[parent_sel_key]):
                        children.append(other_doc)

            return children

        for layer in self.layer_order:
            docs_by_layer = list(filter(
                (lambda x: x.get_layer() == layer), layered_docs))

            for doc in docs_by_layer:
                children = _get_children(doc)

                if children:
                    all_children.update(children)
                    doc.to_dict().setdefault('children', children)

        all_children_elements = list(all_children.elements())
        secondary_docs = list(
            filter(lambda d: d.get_layer() != self.layer_order[0],
            layered_docs))
        for doc in secondary_docs:
            # Unless the document is the topmost document in the
            # `layerOrder` of the LayeringPolicy, it should be a child document
            # of another document.
            if doc not in all_children_elements:
                LOG.info('Could not find parent for document with name=%s, '
                         'schema=%s, layer=%s, parentSelector=%s.',
                         doc.get_name(), doc.get_schema(), doc.get_layer(),
                         doc.get_parent_selector())
            # If the document is a child document of more than 1 parent, then
            # the document has too many parents, which is a validation error.
            elif all_children[doc] != 1:
                LOG.info('%d parent documents were found for child document '
                         'with name=%s, schema=%s, layer=%s, parentSelector=%s'
                         '. Each document must only have 1 parent.',
                         all_children[doc], doc.get_name(), doc.get_schema(),
                         doc.get_layer(), doc.get_parent_selector())
                raise errors.IndeterminateDocumentParent(document=doc)

        return layered_docs

    def _extract_layering_policy(self, documents):
        documents = copy.deepcopy(documents)
        for doc in documents:
            if doc['schema'].startswith(types.LAYERING_POLICY_SCHEMA):
                layering_policy = doc
                documents.remove(doc)
                return (
                    document.Document(layering_policy),
                    [document.Document(d) for d in documents]
                )
        return None, [document.Document(d) for d in documents]

    def __init__(self, documents):
        """Contructor for ``DocumentLayering``.

        :param layering_policy: The document with schema
            ``deckhand/LayeringPolicy`` needed for layering.
        :param documents: List of all other documents to be layered together
            in accordance with the ``layerOrder`` defined by the
            LayeringPolicy document.
        """
        self.layering_policy, self.documents = self._extract_layering_policy(
            documents)
        if self.layering_policy is None:
            error_msg = (
                'No layering policy found in the system so could not reder '
                'documents.')
            LOG.error(error_msg)
            raise errors.LayeringPolicyNotFound()
        self.layer_order = list(self.layering_policy['data']['layerOrder'])
        self.layered_docs = self._calc_document_children()

    def _apply_action(self, action, child_data, overall_data):
        """Apply actions to each layer that is rendered.

        Supported actions include:

            * `merge` - a "deep" merge that layers new and modified data onto
              existing data
            * `replace` - overwrite data at the specified path and replace it
              with the data given in this document
            * `delete` - remove the data at the specified path
        """
        method = action['method']
        if method not in self.SUPPORTED_METHODS:
            raise errors.UnsupportedActionMethod(
                action=action, document=child_data)

        # Use copy prevent these data from being updated referentially.
        overall_data = copy.deepcopy(overall_data)
        child_data = copy.deepcopy(child_data)
        rendered_data = overall_data

        # Remove empty string paths and ensure that "data" is always present.
        path = action['path'].split('.')
        path = [p for p in path if p != '']
        path.insert(0, 'data')
        last_key = 'data' if not path[-1] else path[-1]

        for attr in path:
            if attr == path[-1]:
                break
            rendered_data = rendered_data.get(attr)
            child_data = child_data.get(attr)

        if method == 'delete':
            # If the entire document is passed (i.e. the dict including
            # metadata, data, schema, etc.) then reset data to an empty dict.
            if last_key == 'data':
                rendered_data['data'] = {}
            elif last_key in rendered_data:
                del rendered_data[last_key]
            elif last_key not in rendered_data:
                # If the key does not exist in `rendered_data`, this is a
                # validation error.
                raise errors.MissingDocumentKey(
                    child=child_data, parent=rendered_data, key=last_key)
        elif method == 'merge':
            if last_key in rendered_data and last_key in child_data:
                # If both entries are dictionaries, do a deep merge. Otherwise
                # do a simple merge.
                if (isinstance(rendered_data[last_key], dict)
                    and isinstance(child_data[last_key], dict)):
                    utils.deep_merge(
                        rendered_data[last_key], child_data[last_key])
                else:
                    rendered_data.setdefault(last_key, child_data[last_key])
            elif last_key in child_data:
                rendered_data.setdefault(last_key, child_data[last_key])
            else:
                # If the key does not exist in the child document, this is a
                # validation error.
                raise errors.MissingDocumentKey(
                    child=child_data, parent=rendered_data, key=last_key)
        elif method == 'replace':
            if last_key in rendered_data and last_key in child_data:
                rendered_data[last_key] = child_data[last_key]
            elif last_key in child_data:
                rendered_data.setdefault(last_key, child_data[last_key])
            elif last_key not in child_data:
                # If the key does not exist in the child document, this is a
                # validation error.
                raise errors.MissingDocumentKey(
                    child=child_data, parent=rendered_data, key=last_key)

        return overall_data

    def _apply_substitutions(self, data):
        try:
            secrets_substitution = secrets_manager.SecretsSubstitution(data)
            return secrets_substitution.substitute_all()
        except errors.DocumentNotFound as e:
            LOG.error('Failed to render the documents because a secret '
                      'document could not be found.')
            LOG.exception(six.text_type(e))

    def render(self):
        """Perform layering on the list of documents passed to ``__init__``.

        Each concrete document will undergo layering according to the actions
        defined by its ``metadata.layeringDefinition``. Documents are layered
        with their parents. A parent document's ``schema`` must match that of
        the child, and its ``metadata.labels`` must much the child's
        ``metadata.layeringDefinition.parentSelector``.

        :returns: The list of rendered documents (does not include layering
            policy document).
        :rtype: list[dict]
        """
        # ``rendered_data_by_layer`` tracks the set of changes across all
        # actions across each layer for a specific document.
        rendered_data_by_layer = {}

        # NOTE(fmontei): ``global_docs`` represents the topmost documents in
        # the system. It should probably be impossible for more than 1
        # top-level doc to exist, but handle multiple for now.
        global_docs = [doc for doc in self.layered_docs
                       if doc.get_layer() == self.layer_order[0]]

        for doc in global_docs:
            layer_idx = self.layer_order.index(doc.get_layer())
            if doc.get_substitutions():
                substituted_data = self._apply_substitutions(doc.to_dict())
                rendered_data_by_layer[layer_idx] = substituted_data[0]
            else:
                rendered_data_by_layer[layer_idx] = doc.to_dict()

            # Keep iterating as long as a child exists.
            for child in doc.get_children(nested=True):
                # Retrieve the most up-to-date rendered_data (by
                # referencing the child's parent's data).
                child_layer_idx = self.layer_order.index(child.get_layer())
                rendered_data = rendered_data_by_layer[child_layer_idx - 1]

                # Apply each action to the current document.
                for action in child.get_actions():
                    LOG.debug('Applying action %s to child document with '
                              'name=%s, schema=%s, layer=%s.', action,
                              child.get_name(), child.get_schema(),
                              child.get_layer())
                    rendered_data = self._apply_action(
                        action, child.to_dict(), rendered_data)

                # Update the actual document data if concrete.
                if not child.is_abstract():
                    if child.get_substitutions():
                        rendered_data['metadata'][
                            'substitutions'] = child.get_substitutions()
                        self._apply_substitutions(rendered_data)
                    self.layered_docs[self.layered_docs.index(child)][
                        'data'] = rendered_data['data']

                # Update ``rendered_data_by_layer`` for this layer so that
                # children in deeper layers can reference the most up-to-date
                # changes.
                rendered_data_by_layer[child_layer_idx] = rendered_data

            if 'children' in doc:
                del doc['children']

        return (
            [d.to_dict() for d in self.layered_docs] +
            [self.layering_policy.to_dict()]
        )
