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

import networkx
from networkx.algorithms.cycles import find_cycle
from networkx.algorithms.dag import topological_sort
from oslo_log import log as logging
from oslo_utils import excutils

from deckhand.common.document import DocumentDict as dd
from deckhand.common import utils
from deckhand.common.validation_message import ValidationMessage
from deckhand.engine import document_validation
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

    __slots__ = ('_documents_by_index', '_documents_by_labels',
                 '_documents_by_layer', '_layer_order', '_layering_policy',
                 '_parents', '_sorted_documents', 'secrets_substitution')

    _SUPPORTED_METHODS = (_MERGE_ACTION, _REPLACE_ACTION, _DELETE_ACTION) = (
        'merge', 'replace', 'delete')

    def _calc_replacements_and_substitutions(
            self, substitution_sources):

        def _check_document_with_replacement_field_has_parent(
                parent_meta, parent, document):
            if not parent_meta or not parent:
                error_message = (
                    'Document replacement requires that the document with '
                    '`replacement: true` have a parent.')
                raise errors.InvalidDocumentReplacement(
                    schema=document.schema, name=document.name,
                    layer=document.layer, reason=error_message)

        def _check_replacement_and_parent_same_schema_and_name(
                parent, document):
            # This checks that a document can only be a replacement for
            # another document with the same `metadata.name` and `schema`.
            if not (document.schema == parent.schema and
                    document.name == parent.name):
                error_message = (
                    'Document replacement requires that both documents '
                    'have the same `schema` and `metadata.name`.')
                raise errors.InvalidDocumentReplacement(
                    schema=document.schema, name=document.name,
                    layer=document.layer, reason=error_message)

        def _check_non_replacement_and_parent_different_schema_and_name(
                parent, document):
            if (parent and document.schema == parent.schema and
                    document.name == parent.name):
                error_message = (
                    'Non-replacement documents cannot have the same `schema` '
                    'and `metadata.name` as their parent. Either add '
                    '`replacement: true` to the document or give the document '
                    'a different name.')
                raise errors.InvalidDocumentReplacement(
                    schema=document.schema, name=document.name,
                    layer=document.layer, reason=error_message)

        def _check_replacement_not_itself_replaced_by_another(src_ref):
            # If the document has a replacement, use the replacement as the
            # substitution source instead.
            if src_ref.is_replacement:
                error_message = ('A replacement document cannot itself'
                                 ' be replaced by another document.')
                raise errors.InvalidDocumentReplacement(
                    schema=src_ref.schema, name=src_ref.name,
                    layer=src_ref.layer, reason=error_message)

        for document in self._documents_by_index.values():
            parent_meta = self._parents.get(document.meta)
            parent = self._documents_by_index.get(parent_meta)

            if document.is_replacement:
                _check_document_with_replacement_field_has_parent(
                    parent_meta, parent, document)
                _check_replacement_and_parent_same_schema_and_name(
                    parent, document)
                parent.replaced_by = document
            else:
                _check_non_replacement_and_parent_different_schema_and_name(
                    parent, document)

        # Since a substitution source only provides the document's
        # `metadata.name` and `schema`, their tuple acts as the dictionary key.
        # If a substitution source has a replacement, the replacement is used
        # instead.
        substitution_source_map = {}

        for src in substitution_sources:
            src_ref = dd(src)
            if src_ref.meta in self._documents_by_index:
                src_ref = self._documents_by_index[src_ref.meta]
                if src_ref.has_replacement:
                    _check_replacement_not_itself_replaced_by_another(src_ref)
                    src_ref = src_ref.replaced_by
            substitution_source_map[(src_ref.schema, src_ref.name)] = src_ref

        return substitution_source_map

    def _replace_older_parent_with_younger_parent(self, child, parent,
                                                  all_children):
        # If child has layer N, parent N+1, and current_parent N+2, then swap
        # parent with current_parent. In other words, if parent's layer is
        # closer to child's layer than current_parent's layer, then use parent.
        parent_meta = self._parents.get(child.meta)
        current_parent = self._documents_by_index.get(parent_meta, None)
        if current_parent:
            if (self._layer_order.index(parent.layer) >
                    self._layer_order.index(current_parent.layer)):
                self._parents[child.meta] = parent.meta
                all_children[child] -= 1
        else:
            self._parents.setdefault(child.meta, parent.meta)

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
        potential_children = []
        for label_key, label_val in document.labels.items():
            _potential_children = self._documents_by_labels.get(
                (label_key, label_val), [])
            potential_children.extend(_potential_children)
        unique_potential_children = set(potential_children)

        for potential_child in unique_potential_children:
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
        self._parents = {}

        for layer in self._layer_order:
            documents_in_layer = self._documents_by_layer.get(layer, [])
            for document in documents_in_layer:
                children = list(self._calc_document_children(document))

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
                if doc.parent_selector:
                    LOG.debug(
                        'Could not find parent for document with name=%s, '
                        'schema=%s, layer=%s, parentSelector=%s.', doc.name,
                        doc.schema, doc.layer, doc.parent_selector)
            # If the document is a child document of more than 1 parent, then
            # the document has too many parents, which is a validation error.
            elif all_children[doc] > 1:
                LOG.info('%d parent documents were found for child document '
                         'with name=%s, schema=%s, layer=%s, parentSelector=%s'
                         '. Each document must have exactly 1 parent.',
                         all_children[doc], doc.name, doc.schema, doc.layer,
                         doc.parent_selector)
                raise errors.IndeterminateDocumentParent(
                    name=doc.name, schema=doc.schema, layer=doc.layer,
                    found=all_children[doc])

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

    def _topologically_sort_documents(self, substitution_sources):
        """Topologically sorts the DAG formed from the documents' layering
        and substitution dependency chain.
        """
        result = []

        def _get_ancestor(doc, parent_meta):
            parent = self._documents_by_index.get(parent_meta)
            # Return the parent's replacement, but if that replacement is the
            # document itself then return the parent.
            use_replacement = (
                parent and parent.has_replacement and
                parent.replaced_by is not doc
            )
            if use_replacement:
                parent = parent.replaced_by
            return parent

        g = networkx.DiGraph()
        for document in self._documents_by_index.values():
            if document.parent_selector:
                # NOTE: A child-replacement depends on its parent-replacement
                # the same way any child depends on its parent: so that the
                # child layers with its parent only after the parent has
                # received all layering and substitution data. But other
                # non-replacement child documents must first wait for the
                # child-relacement to layer with the parent, so that they
                # can use the replaced data.
                parent_meta = self._parents.get(document.meta)
                ancestor = _get_ancestor(document, parent_meta)
                if ancestor:
                    g.add_edge(document.meta, ancestor.meta)

            for sub in document.substitutions:
                # Retrieve the correct substitution source using
                # ``substitution_sources``. Necessary for 2 reasons:
                # 1) It accounts for document replacements.
                # 2) It effectively maps a 2-tuple key to a 3-tuple document
                #    unique identifier (meta).
                src = substitution_sources.get(
                    (sub['src']['schema'], sub['src']['name']))
                if src:
                    g.add_edge(document.meta, src.meta)

        try:
            cycle = find_cycle(g, orientation='reverse')
        except networkx.exception.NetworkXNoCycle:
            pass
        else:
            LOG.error('Cannot determine substitution order as a dependency '
                      'cycle exists for the following documents: %s.', cycle)
            raise errors.SubstitutionDependencyCycle(cycle=cycle)

        sorted_documents = reversed(list(topological_sort(g)))

        for document_meta in sorted_documents:
            if document_meta in self._documents_by_index:
                result.append(self._documents_by_index[document_meta])
        for document in self._documents_by_index.values():
            if document not in result:
                result.append(document)

        return result

    def _pre_validate_documents(self, documents):
        LOG.debug('%s performing document pre-validation.',
                  self.__class__.__name__)
        validator = document_validation.DocumentValidation(
            documents, pre_validate=True)
        results = validator.validate_all()

        error_list = []
        for result in results:
            for e in result['errors']:
                LOG.error('Document [%s, %s] %s failed with pre-validation '
                          'error: %s.', e['schema'], e['layer'], e['name'],
                          e['message'])
                error_list.append(
                    ValidationMessage(
                        message=e['message'],
                        doc_schema=e['schema'],
                        doc_name=e['name'],
                        doc_layer=e['layer']
                    )
                )

        if error_list:
            raise errors.InvalidDocumentFormat(error_list=error_list)

    def __init__(self,
                 documents,
                 validate=True,
                 fail_on_missing_sub_src=True,
                 encryption_sources=None):
        """Contructor for ``DocumentLayering``.

        :param layering_policy: The document with schema
            ``deckhand/LayeringPolicy`` needed for layering.
        :param documents: List of all other documents to be layered together
            in accordance with the ``layerOrder`` defined by the
            LayeringPolicy document.
        :type documents: List[dict]
        :param validate: Whether to pre-validate documents using built-in
            schema validation. Skips over externally registered ``DataSchema``
            documents to avoid false positives. Default is True.
        :type validate: bool
        :param fail_on_missing_sub_src: Whether to fail on a missing
            substitution source. Default is True.
        :type fail_on_missing_sub_src: bool
        :param encryption_sources: A dictionary that maps the reference
            contained in the destination document's data section to the
            actual unecrypted data. If encrypting data with Barbican, the
            reference will be a Barbican secret reference.
        :type encryption_sources: dict

        :raises LayeringPolicyNotFound: If no LayeringPolicy was found among
            list of ``documents``.
        :raises InvalidDocumentLayer: If document layer not found in layerOrder
            for provided LayeringPolicy.
        :raises InvalidDocumentParent: If child references parent but they
            don't have the same schema or their layers are incompatible.
        :raises IndeterminateDocumentParent: If more than one parent document
            was found for a document.
        """
        self._documents_by_layer = {}
        self._documents_by_labels = {}
        self._layering_policy = None
        self._sorted_documents = {}
        self._documents_by_index = {}

        # TODO(felipemonteiro): Add a hook for post-validation too.
        if validate:
            self._pre_validate_documents(documents)

        layering_policies = list(
            filter(lambda x: x.get('schema').startswith(
                   types.LAYERING_POLICY_SCHEMA), documents))
        if layering_policies:
            self._layering_policy = dd(layering_policies[0])
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
            document = dd(document)

            self._documents_by_index.setdefault(document.meta, document)

            if document.layer:
                if document.layer not in self._layering_policy.layer_order:
                    LOG.error('Document layer %s for document [%s] %s not '
                              'in layerOrder: %s.', document.layer,
                              document.schema, document.name,
                              self._layering_policy.layer_order)
                    raise errors.InvalidDocumentLayer(
                        document_layer=document.layer,
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

        substitution_sources = self._calc_replacements_and_substitutions(
            [
                d for d in self._documents_by_index.values()
                if not d.is_abstract
            ])

        self.secrets_substitution = secrets_manager.SecretsSubstitution(
            substitution_sources,
            encryption_sources=encryption_sources,
            fail_on_missing_sub_src=fail_on_missing_sub_src)

        self._sorted_documents = self._topologically_sort_documents(
            substitution_sources)

        del self._documents_by_layer
        del self._documents_by_labels

    def _log_data_for_layering_failure(self, child, parent, action):
        child_data = copy.deepcopy(child.data)
        parent_data = copy.deepcopy(parent.data)

        engine_utils.deep_scrub(child_data, None)
        engine_utils.deep_scrub(parent_data, None)

        LOG.debug('An exception occurred while attempting to layer child '
                  'document [%s] %s with parent document [%s] %s using '
                  'layering action: %s.\nScrubbed child document data: %s.\n'
                  'Scrubbed parent document data: %s.', child.schema,
                  child.name, parent.schema, parent.name, action, child_data,
                  parent_data)

    def _log_data_for_substitution_failure(self, document):
        document_data = copy.deepcopy(document.data)
        engine_utils.deep_scrub(document_data, None)

        LOG.debug('An exception occurred while attempting to add substitutions'
                  ' %s into document [%s] %s\nScrubbed document data: %s.',
                  document.substitutions, document.schema, document.name,
                  document_data)

    def _apply_action(self, action, child_data, overall_data):
        """Apply actions to each layer that is rendered.

        Supported actions include:

            * ``merge`` - a "deep" merge that layers new and modified data onto
              existing data
            * ``replace`` - overwrite data at the specified path and replace it
              with the data given in this document
            * ``delete`` - remove the data at the specified path

        :raises UnsupportedActionMethod: If the layering action isn't found
            among ``self.SUPPORTED_METHODS``.
        :raises MissingDocumentKey: If a layering action path isn't found
            in the child document.
        """

        method = action['method']
        if method not in self._SUPPORTED_METHODS:
            raise errors.UnsupportedActionMethod(
                action=action, document=child_data)

        # Use copy to prevent these data from being updated referentially.
        overall_data = copy.deepcopy(overall_data)
        child_data = copy.deepcopy(child_data)

        # If None is used, then consider it as a placeholder and coerce the
        # data into a dictionary.
        if overall_data is None:
            overall_data = {}
        if child_data is None:
            child_data = {}

        action_path = action['path']

        if action_path.startswith('.data'):
            action_path = action_path[5:]
        elif action_path.startswith('$.data'):
            action_path = action_path[6:]
        if not (action_path.startswith('.') or action_path.startswith('$.')):
            action_path = '.' + action_path

        if method == self._DELETE_ACTION:
            if action_path == '.':
                overall_data.data = {}
            else:
                from_child = utils.jsonpath_parse(overall_data.data,
                                                  action_path)
                if from_child is None:
                    raise errors.MissingDocumentKey(
                        child_schema=child_data.schema,
                        child_layer=child_data.layer,
                        child_name=child_data.name,
                        parent_schema=overall_data.schema,
                        parent_layer=overall_data.layer,
                        parent_name=overall_data.name,
                        action=action)

                engine_utils.deep_delete(from_child, overall_data.data, None)

        elif method == self._MERGE_ACTION:
            from_overall = utils.jsonpath_parse(overall_data.data, action_path)
            from_child = utils.jsonpath_parse(child_data.data, action_path)

            if from_child is None:
                raise errors.MissingDocumentKey(
                    child_schema=child_data.schema,
                    child_layer=child_data.layer,
                    child_name=child_data.name,
                    parent_schema=overall_data.schema,
                    parent_layer=overall_data.layer,
                    parent_name=overall_data.name,
                    action=action)

            # If both the child and parent data are dictionaries, then
            # traditional merging is possible using JSON path resolution.
            # Otherwise, JSON path resolution is not possible, so the only
            # way to perform layering is to prioritize the child data over
            # that of the parent. This applies when the child data is a
            # non-dict, the parent data is a non-dict, or both.
            if all(isinstance(x, dict) for x in (from_overall, from_child)):
                engine_utils.deep_merge(from_overall, from_child)
            else:
                LOG.info('Child data is type: %s for [%s, %s] %s. Parent data '
                         'is type: %s for [%s, %s] %s. Both must be '
                         'dictionaries for regular JSON path merging to work. '
                         'Because this is not the case, child data will be '
                         'prioritized over parent data for "merge" action.',
                         type(from_child), child_data.schema, child_data.layer,
                         child_data.name, type(from_overall),
                         overall_data.schema, overall_data.layer,
                         overall_data.name)
                from_overall = from_child

            if from_overall is not None:
                overall_data.data = utils.jsonpath_replace(
                    overall_data.data, from_overall, action_path)
            else:
                overall_data.data = utils.jsonpath_replace(
                    overall_data.data, from_child, action_path)
        elif method == self._REPLACE_ACTION:
            from_child = utils.jsonpath_parse(child_data.data, action_path)

            if from_child is None:
                raise errors.MissingDocumentKey(
                    child_schema=child_data.schema,
                    child_layer=child_data.layer,
                    child_name=child_data.name,
                    parent_schema=overall_data.schema,
                    parent_layer=overall_data.layer,
                    parent_name=overall_data.name,
                    action=action)

            overall_data.data = utils.jsonpath_replace(
                overall_data.data, from_child, action_path)

        return overall_data

    def render(self):
        """Perform layering on the list of documents passed to ``__init__``.

        Each concrete document will undergo layering according to the actions
        defined by its ``metadata.layeringDefinition``. Documents are layered
        with their parents. A parent document's ``schema`` must match that of
        the child, and its ``metadata.labels`` must much the child's
        ``metadata.layeringDefinition.parentSelector``.

        :returns: The list of concrete rendered documents.
        :rtype: List[dict]

        :raises UnsupportedActionMethod: If the layering action isn't found
            among ``self.SUPPORTED_METHODS``.
        :raises MissingDocumentKey: If a layering action path isn't found
            in both the parent and child documents being layered together.
        """
        for doc in self._sorted_documents:
            # Control documents don't need to be layered.
            if doc.is_control:
                continue

            LOG.debug("Rendering document %s:%s:%s", *doc.meta)

            if doc.parent_selector:
                parent_meta = self._parents.get(doc.meta)

                if parent_meta:
                    LOG.debug("Using parent %s:%s:%s", *parent_meta)
                    parent = self._documents_by_index[parent_meta]

                    if doc.actions:
                        rendered_data = parent
                        # Apply each action to the current document.
                        for action in doc.actions:
                            LOG.debug('Applying action %s to document with '
                                      'schema=%s, layer=%s, name=%s.', action,
                                      *doc.meta)
                            try:
                                rendered_data = self._apply_action(
                                    action, doc, rendered_data)
                            except Exception:
                                with excutils.save_and_reraise_exception():
                                    try:
                                        self._log_data_for_layering_failure(
                                            doc, parent, action)
                                    except Exception:  # nosec
                                        pass
                        doc.data = rendered_data.data
                        self.secrets_substitution.update_substitution_sources(
                            doc.meta, rendered_data.data)
                        self._documents_by_index[doc.meta] = rendered_data
                    else:
                        LOG.debug(
                            'Skipped layering for document [%s, %s] %s which '
                            'has a parent [%s, %s] %s, but no associated '
                            'layering actions.', doc.schema, doc.layer,
                            doc.name, parent.schema, parent.layer, parent.name)

            # Perform substitutions on abstract data for child documents that
            # inherit from it, but only update the document's data if concrete.
            if doc.substitutions:
                try:
                    substituted_data = list(
                        self.secrets_substitution.substitute_all(doc))
                except Exception:
                    with excutils.save_and_reraise_exception():
                        try:
                            self._log_data_for_substitution_failure(doc)
                        except Exception:  # nosec
                            pass
                if substituted_data:
                    rendered_data = substituted_data[0]
                    # Update the actual document data if concrete.
                    doc.data = rendered_data.data
                    if not doc.has_replacement:
                        self.secrets_substitution.update_substitution_sources(
                            doc.meta, rendered_data.data)
                    self._documents_by_index[doc.meta] = rendered_data
            # Otherwise, retrieve the encrypted data for the document if its
            # data has been encrypted so that future references use the actual
            # secret payload, rather than the Barbican secret reference.
            elif doc.is_encrypted and doc.has_barbican_ref:
                encrypted_data = self.secrets_substitution\
                    .get_unencrypted_data(doc.data, doc, doc)
                if not doc.is_abstract:
                    doc.data = encrypted_data
                self.secrets_substitution.update_substitution_sources(
                    doc.meta, encrypted_data)
                self._documents_by_index[doc.meta] = encrypted_data

            # NOTE: Since the child-replacement is always prioritized, before
            # other children, as soon as the child-replacement layers with the
            # parent (which already has undergone layering and substitution
            # itself), replace the parent data with that of the replacement.
            if doc.is_replacement:
                parent.data = doc.data

        # Return only concrete documents and non-replacements.
        return [d for d in self._sorted_documents
                if d.is_abstract is False and d.has_replacement is False]

    @property
    def documents(self):
        return self._sorted_documents
