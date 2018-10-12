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
from deckhand import engine
from deckhand.engine import document_validation
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
        'status.bucket', 'order', 'sort', 'limit', 'cleartext-secrets'])
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
        cleartext_secrets = sanitized_params.pop('cleartext-secrets', None)

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

        if cleartext_secrets not in [True, 'true', 'True']:
            documents = utils.redact_documents(documents)

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

        rendered_documents, cache_hit = common.get_rendered_docs(
            revision_id, **filters)

        # If the rendered documents result set is cached, then post-validation
        # for that result set has already been performed successfully, so it
        # can be safely skipped over as an optimization.
        if not cache_hit:
            data_schemas = db_api.revision_documents_get(
                schema=types.DATA_SCHEMA_SCHEMA, deleted=False)
            validator = document_validation.DocumentValidation(
                rendered_documents, data_schemas, pre_validate=False)
            engine.validate_render(revision_id, rendered_documents, validator)

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
        resp.body = self.view_builder.list(rendered_documents)
