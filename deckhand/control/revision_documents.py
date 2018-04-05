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

import falcon
from oslo_log import log as logging
import six

from deckhand.common import utils
from deckhand.control import base as api_base
from deckhand.control import common
from deckhand.control.views import document as document_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import document_validation
from deckhand.engine import layering
from deckhand import errors
from deckhand import policy
from deckhand import types

LOG = logging.getLogger(__name__)


class RevisionDocumentsResource(api_base.BaseResource):
    """API resource for realizing revision documents endpoint."""

    view_builder = document_view.ViewBuilder()

    @policy.authorize('deckhand:list_cleartext_documents')
    @common.sanitize_params([
        'schema', 'metadata.name', 'metadata.layeringDefinition.abstract',
        'metadata.layeringDefinition.layer', 'metadata.label',
        'status.bucket', 'order', 'sort'])
    def on_get(self, req, resp, sanitized_params, revision_id):
        """Returns all documents for a `revision_id`.

        Returns a multi-document YAML response containing all the documents
        matching the filters specified via query string parameters. Returned
        documents will be as originally posted with no substitutions or
        layering applied.
        """
        include_encrypted = policy.conditional_authorize(
            'deckhand:list_encrypted_documents', req.context, do_raise=False)

        order_by = sanitized_params.pop('order', None)
        sort_by = sanitized_params.pop('sort', None)

        filters = sanitized_params.copy()
        filters['metadata.storagePolicy'] = ['cleartext']
        if include_encrypted:
            filters['metadata.storagePolicy'].append('encrypted')
        filters['deleted'] = False  # Never return deleted documents to user.

        try:
            documents = db_api.revision_documents_get(
                revision_id, **filters)
        except errors.RevisionNotFound as e:
            LOG.exception(six.text_type(e))
            raise falcon.HTTPNotFound(description=e.format_message())

        # Sorts by creation date by default.
        documents = utils.multisort(documents, sort_by, order_by)

        resp.status = falcon.HTTP_200
        resp.body = self.view_builder.list(documents)


class RenderedDocumentsResource(api_base.BaseResource):
    """API resource for realizing rendered documents endpoint.

    Rendered documents are also revision documents, but unlike revision
    documents, they are finalized documents, having undergone secret
    substitution and document layering.

    Returns a multi-document YAML response containing all the documents
    matching the filters specified via query string parameters. Returned
    documents will have secrets substituted into them and be layered with
    other documents in the revision, in accordance with the ``LayeringPolicy``
    that currently exists in the system.
    """

    view_builder = document_view.ViewBuilder()

    @policy.authorize('deckhand:list_cleartext_documents')
    @common.sanitize_params([
        'schema', 'metadata.name', 'metadata.layeringDefinition.layer',
        'metadata.label', 'status.bucket', 'order', 'sort'])
    def on_get(self, req, resp, sanitized_params, revision_id):
        include_encrypted = policy.conditional_authorize(
            'deckhand:list_encrypted_documents', req.context, do_raise=False)
        filters = {
            'metadata.storagePolicy': ['cleartext'],
            'deleted': False
        }
        if include_encrypted:
            filters['metadata.storagePolicy'].append('encrypted')

        documents = self._retrieve_documents_for_rendering(revision_id,
                                                           **filters)

        try:
            # NOTE(fmontei): `validate` is False because documents have already
            # been pre-validated during ingestion. Documents are post-validated
            # below, regardless.
            document_layering = layering.DocumentLayering(
                documents, validate=False)
            rendered_documents = document_layering.render()
        except (errors.InvalidDocumentLayer,
                errors.InvalidDocumentParent,
                errors.InvalidDocumentReplacement,
                errors.IndeterminateDocumentParent,
                errors.MissingDocumentKey,
                errors.SubstitutionSourceDataNotFound,
                errors.UnsupportedActionMethod) as e:
            raise falcon.HTTPBadRequest(description=e.format_message())
        except (errors.LayeringPolicyNotFound,
                errors.SubstitutionSourceNotFound) as e:
            raise falcon.HTTPConflict(description=e.format_message())
        except (errors.DeckhandException,
                errors.UnknownSubstitutionError) as e:
            raise falcon.HTTPInternalServerError(
                description=e.format_message())

        # Filters to be applied post-rendering, because many documents are
        # involved in rendering. User filters can only be applied once all
        # documents have been rendered. Note that `layering` module only
        # returns concrete documents, so no filtering for that is needed here.
        order_by = sanitized_params.pop('order', None)
        sort_by = sanitized_params.pop('sort', None)
        user_filters = sanitized_params.copy()

        rendered_documents = [
            d for d in rendered_documents if utils.deepfilter(
                d, **user_filters)]

        if sort_by:
            rendered_documents = utils.multisort(
                rendered_documents, sort_by, order_by)

        resp.status = falcon.HTTP_200
        resp.body = self.view_builder.list(rendered_documents)
        self._post_validate(rendered_documents)

    def _retrieve_documents_for_rendering(self, revision_id, **filters):
        """Retrieve all necessary documents needed for rendering. If a layering
        policy isn't found in the current revision, retrieve it in a subsequent
        call and add it to the list of documents.
        """
        try:
            documents = db_api.revision_documents_get(revision_id, **filters)
        except errors.RevisionNotFound as e:
            LOG.exception(six.text_type(e))
            raise falcon.HTTPNotFound(description=e.format_message())

        if not any([d['schema'].startswith(types.LAYERING_POLICY_SCHEMA)
                    for d in documents]):
            try:
                layering_policy_filters = {
                    'deleted': False,
                    'schema': types.LAYERING_POLICY_SCHEMA
                }
                layering_policy = db_api.document_get(
                    **layering_policy_filters)
            except errors.DocumentNotFound as e:
                LOG.exception(e.format_message())
            else:
                documents.append(layering_policy)

        return documents

    def _post_validate(self, rendered_documents):
        # Perform schema validation post-rendering to ensure that rendering
        # and substitution didn't break anything.
        data_schemas = db_api.revision_documents_get(
            schema=types.DATA_SCHEMA_SCHEMA, deleted=False)
        doc_validator = document_validation.DocumentValidation(
            rendered_documents, data_schemas, pre_validate=False)
        try:
            validations = doc_validator.validate_all()
        except errors.InvalidDocumentFormat as e:
            LOG.error('Failed to post-validate rendered documents.')
            LOG.exception(e.format_message())
            raise falcon.HTTPInternalServerError(
                description=e.format_message())
        else:
            failed_validations = [
                v for v in validations if v['status'] == 'failure']
            if failed_validations:
                raise falcon.HTTPBadRequest(description=failed_validations)
