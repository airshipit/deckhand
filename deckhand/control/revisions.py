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
from deckhand.db.sqlalchemy import api as db_api


class RevisionsResource(api_base.BaseResource):
    """API resource for realizing CRUD endpoints for Document Revisions."""

    def on_get(self, req, resp):
        """Returns list of existing revisions.
        
        Lists existing revisions and reports basic details including a summary
        of validation status for each `deckhand/ValidationPolicy` that is part
        of each revision.
        """
        revisions = db_api.revision_get_all()

        resp.status = falcon.HTTP_200
        resp.body = self.to_yaml_body(revisions)
