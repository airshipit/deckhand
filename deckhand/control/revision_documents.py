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

from deckhand.control import base as api_base
from deckhand.control import common
from deckhand.control.views import document as document_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import secrets_manager
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class RevisionDocumentsResource(api_base.BaseResource):
    """API resource for realizing revision documents endpoint."""

    view_builder = document_view.ViewBuilder()

    @policy.authorize('deckhand:list_cleartext_documents')
    @common.sanitize_params([
        'schema', 'metadata.name', 'metadata.layeringDefinition.abstract',
        'metadata.layeringDefinition.layer', 'metadata.label',
        'status.bucket'])
    def on_get(self, req, resp, sanitized_params, revision_id):
        """Returns all documents for a `revision_id`.

        Returns a multi-document YAML response containing all the documents
        matching the filters specified via query string parameters. Returned
        documents will be as originally posted with no substitutions or
        layering applied.
        """
        include_encrypted = policy.conditional_authorize(
            'deckhand:list_encrypted_documents', req.context, do_raise=False)

        filters = sanitized_params.copy()
        filters['metadata.storagePolicy'] = ['cleartext']
        if include_encrypted:
            filters['metadata.storagePolicy'].append('encrypted')
        # Never return deleted documents to user.
        filters['deleted'] = False

        try:
            documents = db_api.revision_get_documents(
                revision_id, **filters)
        except errors.RevisionNotFound as e:
            LOG.exception(six.text_type(e))
            raise falcon.HTTPNotFound(description=e.format_message())

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
        'schema', 'metadata.name', 'metadata.label'])
    def on_get(self, req, resp, sanitized_params, revision_id):
        include_encrypted = policy.conditional_authorize(
            'deckhand:list_encrypted_documents', req.context, do_raise=False)

        filters = sanitized_params.copy()
        filters['metadata.layeringDefinition.abstract'] = False
        filters['metadata.storagePolicy'] = ['cleartext']
        if include_encrypted:
            filters['metadata.storagePolicy'].append('encrypted')

        try:
            documents = db_api.revision_get_documents(
                revision_id, **filters)
        except errors.RevisionNotFound as e:
            LOG.exception(six.text_type(e))
            raise falcon.HTTPNotFound(description=e.format_message())

        # TODO(fmontei): Currently the only phase of rendering that is
        # performed is secret substitution, which can be done in any randomized
        # order. However, secret substitution logic will have to be moved into
        # a separate module that handles layering alongside substitution once
        # layering has been fully integrated into this endpoint.
        secrets_substitution = secrets_manager.SecretsSubstitution(documents)
        try:
            rendered_documents = secrets_substitution.substitute_all()
        except errors.DocumentNotFound as e:
            LOG.error('Failed to render the documents because a secret '
                      'document could not be found.')
            LOG.exception(six.text_type(e))
            raise falcon.HTTPNotFound(description=e.format_message())

        resp.status = falcon.HTTP_200
        resp.body = self.view_builder.list(rendered_documents)
