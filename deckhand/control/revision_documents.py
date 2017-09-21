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

from deckhand.control import base as api_base
from deckhand.control import common
from deckhand.control.views import document as document_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class RevisionDocumentsResource(api_base.BaseResource):
    """API resource for realizing CRUD endpoints for revision documents."""

    view_builder = document_view.ViewBuilder()

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
        include_cleartext = policy.conditional_authorize(
            'deckhand:list_cleartext_documents', req.context, do_raise=False)
        include_encrypted = policy.conditional_authorize(
            'deckhand:list_encrypted_documents', req.context, do_raise=False)

        filters = sanitized_params.copy()
        filters['metadata.storagePolicy'] = []
        if include_cleartext:
            filters['metadata.storagePolicy'].append('cleartext')
        if include_encrypted:
            filters['metadata.storagePolicy'].append('encrypted')

        # Never return deleted documents to user.
        filters['deleted'] = False

        try:
            documents = db_api.revision_get_documents(
                revision_id, **filters)
        except errors.RevisionNotFound as e:
            raise falcon.HTTPNotFound(description=e.format_message())

        resp.status = falcon.HTTP_200
        resp.append_header('Content-Type', 'application/x-yaml')
        resp.body = self.to_yaml_body(self.view_builder.list(documents))
