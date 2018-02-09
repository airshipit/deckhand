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

from deckhand.engine import document_wrapper
from deckhand.engine import secrets_manager
from deckhand.engine import utils as engine_utils
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

    def _replace_older_parent_with_younger_parent(self, child, parent,
                                                  all_children):
        # If child has layer N, parent N+1, and current_parent N+2, then swap
        # parent with current_parent. In other words, if parent's layer is
        # closer to child's layer than current_parent's layer, then use parent.
        current_parent = self._parents.get((child.name, child.schema))
        if current_parent:
            if (self._layer_order.index(parent.layer) >
                self._layer_order.index(current_parent.layer)):
                self._parents[(child.name, child.schema)] = parent
                self._children[
                    (current_parent.name, current_parent.schema)].remove(child)
                all_children[child] -= 1
        else:
            self._parents.setdefault((child.name, child.schema), parent)

    def _is_actual_child_document(self, document, potential_child):
        if document == potential_child:
            return False

        document_layer_idx = self._layer_order.index(document.layer)
        child_layer_idx = self._layer_order.index(potential_child.layer)

        parent_selector = potential_child.parent_selector
        labels = document.labels
        # Labels are key-value pairs which are unhashable, so use ``all``
        # instead.
        is_actual_child = all(
            labels.get(x) == y for x, y in parent_selector.items())

        if is_actual_child:
            # Documents with different `schema`s are never layered together,
            # so consider only documents with same schema as candidates.
            if potential_child.schema != document.schema:
                reason = ('Child has parentSelector which references parent, '
                          'but their `schema`s do not match.')
                LOG.error(reason)
                raise errors.InvalidDocumentParent(
                    parent_schema=document.schema, parent_name=document.name,
                    document_schema=potential_child.schema,
                    document_name=potential_child.name, reason=reason)

            # The highest order is 0, so the parent should be lower than the
            # child.
            if document_layer_idx >= child_layer_idx:
                reason = ('Child has parentSelector which references parent, '
                          'but the child layer %s must be lower than the '
                          'parent layer %s for layerOrder %s.' % (
                              potential_child.layer, document.layer,
                              ', '.join(self._layer_order)))
                LOG.error(reason)
                raise errors.InvalidDocumentParent(
                    parent_schema=document.schema, parent_name=document.name,
                    document_schema=potential_child.schema,
                    document_name=potential_child.name, reason=reason)

        return is_actual_child

    def _calc_document_children(self, document):
        potential_children = set()
        for label_key, label_val in document.labels.items():
            _potential_children = self._documents_by_labels.get(
                (label_key, label_val), [])
            potential_children |= set(_potential_children)

        for potential_child in potential_children:
            if self._is_actual_child_document(document, potential_child):
                yield potential_child

    def _calc_all_document_children(self):
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
        :rtype: List[:class:`DocumentDict`]
        :raises IndeterminateDocumentParent: If more than one parent document
            was found for a document.
        """
        # ``all_children`` is a counter utility for verifying that each
        # document has exactly one parent.
        all_children = collections.Counter()
        # Mapping of (doc.name, doc.metadata.name) => children, where children
        # are the documents whose `parentSelector` references the doc.
        self._children = {}
        self._parents = {}
        self._parentless_documents = []

        for layer in self._layer_order:
            documents_in_layer = self._documents_by_layer.get(layer, [])
            for document in documents_in_layer:
                children = list(self._calc_document_children(document))
                self._children[(document.name, document.schema)] = children

                if children:
                    all_children.update(children)

                for child in children:
                    self._replace_older_parent_with_younger_parent(
                        child, document, all_children)

        all_children_elements = list(all_children.elements())
        secondary_documents = []
        for layer, documents in self._documents_by_layer.items():
            if self._layer_order and layer != self._layer_order[0]:
                secondary_documents.extend(documents)

        for doc in secondary_documents:
            # Unless the document is the topmost document in the
            # `layerOrder` of the LayeringPolicy, it should be a child document
            # of another document.
            if doc not in all_children_elements:
                LOG.info('Could not find parent for document with name=%s, '
                         'schema=%s, layer=%s, parentSelector=%s.',
                         doc.name, doc.schema, doc.layer, doc.parent_selector)
                self._parentless_documents.append(doc)
            # If the document is a child document of more than 1 parent, then
            # the document has too many parents, which is a validation error.
            elif all_children[doc] > 1:
                LOG.info('%d parent documents were found for child document '
                         'with name=%s, schema=%s, layer=%s, parentSelector=%s'
                         '. Each document must have exactly 1 parent.',
                         all_children[doc], doc.name, doc.schema, doc.layer,
                         doc.parent_selector)
                raise errors.IndeterminateDocumentParent(document=doc)

    def _get_layering_order(self, layering_policy):
        # Pre-processing stage that removes empty layers from the
        # ``layerOrder`` in the layering policy.
        layer_order = list(layering_policy.layer_order)
        for layer in layer_order[:]:
            documents_by_layer = self._documents_by_layer.get(layer, [])
            if not documents_by_layer:
                LOG.info('%s is an empty layer with no documents. It will be '
                         'discarded from the layerOrder during the layering '
                         'process.', layer)
                layer_order.remove(layer)
        if not layer_order:
            LOG.info('Either the layerOrder in the LayeringPolicy was empty '
                     'to begin with or no document layers were found in the '
                     'layerOrder, causing it to become empty. No layering '
                     'will be performed.')
        return layer_order

    def __init__(self, documents, substitution_sources=None):
        """Contructor for ``DocumentLayering``.

        :param layering_policy: The document with schema
            ``deckhand/LayeringPolicy`` needed for layering.
        :param documents: List of all other documents to be layered together
            in accordance with the ``layerOrder`` defined by the
            LayeringPolicy document.
        :type documents: List[dict]
        :param substitution_sources: List of documents that are potential
            sources for substitution. Should only include concrete documents.
        :type substitution_sources: List[dict]

        :raises LayeringPolicyNotFound: If no LayeringPolicy was found among
            list of ``documents``.
        :raises InvalidDocumentLayer: If document layer not found in layerOrder
            for provided LayeringPolicy.
        :raises InvalidDocumentParent: If child references parent but they
            don't have the same schema or their layers are incompatible.
        :raises IndeterminateDocumentParent: If more than one parent document
            was found for a document.
        """
        self._documents_to_layer = []
        self._documents_by_layer = {}
        self._documents_by_labels = {}
        self._layering_policy = None

        layering_policies = list(
            filter(lambda x: x.get('schema').startswith(
                   types.LAYERING_POLICY_SCHEMA), documents))
        if layering_policies:
            self._layering_policy = document_wrapper.DocumentDict(
                layering_policies[0])
            if len(layering_policies) > 1:
                LOG.warning('More than one layering policy document was '
                            'passed in. Using the first one found: [%s] %s.',
                            self._layering_policy.schema,
                            self._layering_policy.name)

        if self._layering_policy is None:
            error_msg = (
                'No layering policy found in the system so could not render '
                'documents.')
            LOG.error(error_msg)
            raise errors.LayeringPolicyNotFound()

        for document in documents:
            document = document_wrapper.DocumentDict(document)
            if document.layering_definition:
                self._documents_to_layer.append(document)
            if document.layer:
                if document.layer not in self._layering_policy.layer_order:
                    LOG.error('Document layer %s for document [%s] %s not '
                              'in layerOrder: %s.', document.layer,
                              document.schema, document.name,
                              self._layering_policy.layer_order)
                    raise errors.InvalidDocumentLayer(
                        document_schema=document.schema,
                        document_name=document.name,
                        layer_order=', '.join(
                            self._layering_policy.layer_order),
                        layering_policy_name=self._layering_policy.name)
                self._documents_by_layer.setdefault(document.layer, [])
                self._documents_by_layer[document.layer].append(document)
            if document.parent_selector:
                for label_key, label_val in document.parent_selector.items():
                    self._documents_by_labels.setdefault(
                        (label_key, label_val), [])
                    self._documents_by_labels[
                        (label_key, label_val)].append(document)

        self._layer_order = self._get_layering_order(self._layering_policy)
        self._calc_all_document_children()
        self._substitution_sources = substitution_sources or []
        self.secrets_substitution = secrets_manager.SecretsSubstitution(
            self._substitution_sources)

        del self._documents_by_layer
        del self._documents_by_labels

    def _apply_action(self, action, child_data, overall_data):
        """Apply actions to each layer that is rendered.

        Supported actions include:

            * `merge` - a "deep" merge that layers new and modified data onto
              existing data
            * `replace` - overwrite data at the specified path and replace it
              with the data given in this document
            * `delete` - remove the data at the specified path

        :raises UnsupportedActionMethod: If the layering action isn't found
            among ``self.SUPPORTED_METHODS``.
        :raises MissingDocumentKey: If a layering action path isn't found
            in both the parent and child documents being layered together.
        """
        method = action['method']
        if method not in self.SUPPORTED_METHODS:
            raise errors.UnsupportedActionMethod(
                action=action, document=child_data)

        # Use copy to prevent these data from being updated referentially.
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
                    engine_utils.deep_merge(
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

    def _get_children(self, document):
        """Recursively retrieve all children.

        Used in the layering module when calculating children for each
        document.

        :returns: List of nested children.
        :rtype: Generator[:class:`DocumentDict`]
        """
        for child in self._children.get((document.name, document.schema), []):
            yield child
            grandchildren = self._get_children(child)
            for grandchild in grandchildren:
                yield grandchild

    def render(self):
        """Perform layering on the list of documents passed to ``__init__``.

        Each concrete document will undergo layering according to the actions
        defined by its ``metadata.layeringDefinition``. Documents are layered
        with their parents. A parent document's ``schema`` must match that of
        the child, and its ``metadata.labels`` must much the child's
        ``metadata.layeringDefinition.parentSelector``.

        :returns: The list of rendered documents (does not include layering
            policy document).
        :rtype: List[dict]

        :raises UnsupportedActionMethod: If the layering action isn't found
            among ``self.SUPPORTED_METHODS``.
        :raises MissingDocumentKey: If a layering action path isn't found
            in both the parent and child documents being layered together.
        """
        # ``rendered_data_by_layer`` tracks the set of changes across all
        # actions across each layer for a specific document.
        rendered_data_by_layer = document_wrapper.DocumentDict()

        # NOTE(fmontei): ``global_docs`` represents the topmost documents in
        # the system. It should probably be impossible for more than 1
        # top-level doc to exist, but handle multiple for now.
        global_docs = [
            doc for doc in self._documents_to_layer
            if self._layer_order and doc.layer == self._layer_order[0]
        ]

        for doc in global_docs:
            layer_idx = self._layer_order.index(doc.layer)
            if doc.substitutions:
                substituted_data = list(
                    self.secrets_substitution.substitute_all(doc))
                if substituted_data:
                    rendered_data_by_layer[layer_idx] = substituted_data[0]
            else:
                rendered_data_by_layer[layer_idx] = doc

            # Keep iterating as long as a child exists.
            for child in self._get_children(doc):
                # Retrieve the most up-to-date rendered_data (by referencing
                # the child's parent's data).
                child_layer_idx = self._layer_order.index(child.layer)
                parent = self._parents[child.name, child.schema]
                parent_layer_idx = self._layer_order.index(parent.layer)
                rendered_data = rendered_data_by_layer[parent_layer_idx]

                # Apply each action to the current document.
                for action in child.actions:
                    LOG.debug('Applying action %s to child document with '
                              'name=%s, schema=%s, layer=%s.', action,
                              child.name, child.schema, child.layer)
                    rendered_data = self._apply_action(
                        action, child, rendered_data)

                # Update the actual document data if concrete.
                if not child.is_abstract:
                    child.data = rendered_data.data
                    substituted_data = list(
                        self.secrets_substitution.substitute_all(child))
                    if substituted_data:
                        rendered_data = substituted_data[0]
                    child_index = self._documents_to_layer.index(child)
                    self._documents_to_layer[child_index].data = (
                        rendered_data.data)

                # Update ``rendered_data_by_layer`` for this layer so that
                # children in deeper layers can reference the most up-to-date
                # changes.
                rendered_data_by_layer[child_layer_idx] = rendered_data

        # Handle edge case for parentless documents that require substitution.
        # If a document has no parent, then the for loop above doesn't iterate
        # over the parentless document, so substitution must be done here for
        # parentless documents.
        for doc in self._parentless_documents:
            if not doc.is_abstract and doc.substitutions:
                substituted_data = list(
                    self.secrets_substitution.substitute_all(doc))
                if substituted_data:
                    doc = substituted_data[0]

        return self._documents_to_layer
