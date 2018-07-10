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
from oslo_utils import excutils
import six

from deckhand.common import utils
from deckhand.common import validation_message as vm
from deckhand.control import base as api_base
from deckhand.control import common
from deckhand.control.views import document as document_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import document_validation
from deckhand.engine import layering
from deckhand.engine import secrets_manager
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
        'status.bucket', 'order', 'sort', 'limit'])
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
        limit = sanitized_params.pop('limit', None)

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
        if limit is not None:
            documents = documents[:limit]

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
        'metadata.label', 'status.bucket', 'order', 'sort', 'limit'])
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
        encryption_sources = self._retrieve_encrypted_documents(documents)

        try:
            # NOTE(fmontei): `validate` is False because documents have already
            # been pre-validated during ingestion. Documents are post-validated
            # below, regardless.
            document_layering = layering.DocumentLayering(
                documents, encryption_sources=encryption_sources,
                validate=False)
            rendered_documents = document_layering.render()
        except (errors.BarbicanClientException,
                errors.BarbicanServerException,
                errors.InvalidDocumentLayer,
                errors.InvalidDocumentParent,
                errors.InvalidDocumentReplacement,
                errors.IndeterminateDocumentParent,
                errors.LayeringPolicyNotFound,
                errors.MissingDocumentKey,
                errors.SubstitutionSourceDataNotFound,
                errors.SubstitutionSourceNotFound,
                errors.UnknownSubstitutionError,
                errors.UnsupportedActionMethod) as e:
            with excutils.save_and_reraise_exception():
                LOG.exception(e.format_message())
        except errors.EncryptionSourceNotFound as e:
            # This branch should be unreachable, but if an encryption source
            # wasn't found, then this indicates the controller fed bad data
            # to the engine, in which case this is a 500.
            e.code = 500
            raise e

        # Filters to be applied post-rendering, because many documents are
        # involved in rendering. User filters can only be applied once all
        # documents have been rendered. Note that `layering` module only
        # returns concrete documents, so no filtering for that is needed here.
        order_by = sanitized_params.pop('order', None)
        sort_by = sanitized_params.pop('sort', None)
        limit = sanitized_params.pop('limit', None)
        user_filters = sanitized_params.copy()

        rendered_documents = [
            d for d in rendered_documents if utils.deepfilter(
                d, **user_filters)]

        if sort_by:
            rendered_documents = utils.multisort(
                rendered_documents, sort_by, order_by)

        if limit is not None:
            rendered_documents = rendered_documents[:limit]

        resp.status = falcon.HTTP_200
        self._post_validate(rendered_documents)
        resp.body = self.view_builder.list(rendered_documents)

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

    def _retrieve_encrypted_documents(self, documents):
        encryption_sources = {}
        for document in documents:
            if document.is_encrypted and document.has_barbican_ref:
                try:
                    unecrypted_data = secrets_manager.SecretsManager.get(
                        secret_ref=document.data, src_doc=document)
                except Exception as e:
                    LOG.error(
                        'An unknown exception occurred while trying to resolve'
                        ' a secret reference for substitution source document '
                        '[%s, %s] %s.', document.schema, document.layer,
                        document.name)
                    raise errors.UnknownSubstitutionError(
                        src_schema=document.schema, src_layer=document.layer,
                        src_name=document.name, details=str(e))
                encryption_sources.setdefault(document.data, unecrypted_data)
        return encryption_sources

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
            # Post-rendering validation errors likely indicate an internal
            # rendering bug, so override the default code to 500.
            e.code = 500
            LOG.error('Failed to post-validate rendered documents.')
            LOG.exception(e.format_message())
            raise e
        else:
            error_list = []

            for validation in validations:
                if validation['status'] == 'failure':
                    error_list.extend([
                        vm.ValidationMessage(
                            message=error['message'],
                            name=vm.DOCUMENT_POST_RENDERING_FAILURE,
                            doc_schema=error['schema'],
                            doc_name=error['name'],
                            doc_layer=error['layer'],
                            diagnostic={
                                k: v for k, v in error.items() if k in (
                                    'schema_path',
                                    'validation_schema',
                                    'error_section'
                                )
                            }
                        )
                        for error in validation['errors']
                    ])

            if error_list:
                raise errors.InvalidDocumentFormat(
                    error_list=error_list,
                    reason='Validation'
                )
