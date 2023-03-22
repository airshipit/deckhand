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

from deckhand.control import base as api_base
from deckhand.control.views import revision as revision_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class RollbackResource(api_base.BaseResource):
    """API resource for realizing revision rollback."""

    view_builder = revision_view.ViewBuilder()

    @policy.authorize('deckhand:create_cleartext_documents')
    def on_post(self, req, resp, revision_id):
        try:
            latest_revision = db_api.revision_get_latest()
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        for document in latest_revision['documents']:
            if document['metadata'].get('storagePolicy') == 'encrypted':
                policy.conditional_authorize(
                    'deckhand:create_encrypted_documents', req.context)
                break

        try:
            rollback_revision = db_api.revision_rollback(
                revision_id, latest_revision)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        revision_resp = self.view_builder.show(rollback_revision)
        resp.status = falcon.HTTP_201
        resp.body = revision_resp
