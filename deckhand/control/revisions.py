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

from deckhand.control import base as api_base
from deckhand.control.views import revision as revision_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand import errors


class RevisionsResource(api_base.BaseResource):
    """API resource for realizing CRUD operations for revisions."""

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

    def _show_revision(self, req, resp, revision_id):
        """Returns detailed description of a particular revision.

        The status of each ValidationPolicy belonging to the revision is also
        included.
        """
        try:
            revision = db_api.revision_get(revision_id)
        except errors.RevisionNotFound as e:
            return self.return_error(resp, falcon.HTTP_404, message=e)

        revision_resp = revision_view.ViewBuilder().show(revision)
        resp.status = falcon.HTTP_200
        resp.append_header('Content-Type', 'application/x-yaml')
        resp.body = self.to_yaml_body(revision_resp)

    def _list_revisions(self, req, resp):
        revisions = db_api.revision_get_all()
        revisions_resp = revision_view.ViewBuilder().list(revisions)

        resp.status = falcon.HTTP_200
        resp.append_header('Content-Type', 'application/x-yaml')
        resp.body = self.to_yaml_body(revisions_resp)
