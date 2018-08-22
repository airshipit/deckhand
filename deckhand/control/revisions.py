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

from deckhand.common import utils
from deckhand.control import base as api_base
from deckhand.control import common
from deckhand.control.views import revision as revision_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import secrets_manager
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class RevisionsResource(api_base.BaseResource):
    """API resource for realizing CRUD operations for revisions."""

    view_builder = revision_view.ViewBuilder()

    def on_get(self, req, resp, revision_id=None):
        """Returns list of existing revisions.

        Lists existing revisions and reports basic details including a summary
        of validation status for each `deckhand/ValidationPolicy` that is part
        of each revision.
        """
        if revision_id:
            self._show_revision(req, resp, revision_id=revision_id)
        else:
            self._list_revisions(req, resp)

    @policy.authorize('deckhand:show_revision')
    def _show_revision(self, req, resp, revision_id):
        """Returns detailed description of a particular revision.

        The status of each ValidationPolicy belonging to the revision is also
        included.
        """
        try:
            revision = db_api.revision_get(revision_id)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                LOG.exception(e.format_message())

        revision_resp = self.view_builder.show(revision)
        resp.status = falcon.HTTP_200
        resp.body = revision_resp

    @policy.authorize('deckhand:list_revisions')
    @common.sanitize_params(['tag', 'order', 'sort'])
    def _list_revisions(self, req, resp, sanitized_params):
        order_by = sanitized_params.pop('order', None)
        sort_by = sanitized_params.pop('sort', None)

        revisions = db_api.revision_get_all(**sanitized_params)
        if sort_by:
            revisions = utils.multisort(revisions, sort_by, order_by)

        resp.status = falcon.HTTP_200
        resp.body = self.view_builder.list(revisions)

    def _delete_all_barbican_secrets(self):
        filters = {'metadata.storagePolicy': 'encrypted'}
        # NOTE(felipemonteiro): Don't pass `unique_only` because we want
        # all unique secret references (just the data section), not unique
        # documents, which considers all attributes.
        encrypted_documents = db_api.document_get_all(**filters)

        for document in encrypted_documents:
            secrets_manager.SecretsManager.delete(document)

    @policy.authorize('deckhand:delete_revisions')
    def on_delete(self, req, resp):
        self._delete_all_barbican_secrets()  # Delete all Barbican secrets.
        db_api.revision_delete_all()  # Delete all revisions.
        common.invalidate_cache_data()  # Invalidate all cached data.
        resp.status = falcon.HTTP_204
