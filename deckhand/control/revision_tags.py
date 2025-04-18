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
from deckhand.control.views import revision_tag as revision_tag_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class RevisionTagsResource(api_base.BaseResource):
    """API resource for realizing CRUD for revision tags."""

    @policy.authorize('deckhand:create_tag')
    def on_post(self, req, resp, revision_id, tag=None):
        """Creates a revision tag."""
        tag_data = self.from_yaml(req, expect_list=False, allow_empty=True)

        try:
            resp_tag = db_api.revision_tag_create(revision_id, tag, tag_data)
        except (errors.RevisionNotFound,
                errors.RevisionTagBadFormat,
                errors.errors.RevisionTagNotFound) as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        resp_body = revision_tag_view.ViewBuilder().show(resp_tag)
        resp.status = falcon.HTTP_201
        resp.text = utils.safe_yaml_dump(resp_body)

    def on_get(self, req, resp, revision_id, tag=None):
        """Show tag details or list all tags for a revision."""
        if tag:
            self._show_tag(req, resp, revision_id, tag)
        else:
            self._list_all_tags(req, resp, revision_id)

    @policy.authorize('deckhand:show_tag')
    def _show_tag(self, req, resp, revision_id, tag):
        """Retrieve details for a specified tag."""
        try:
            resp_tag = db_api.revision_tag_get(revision_id, tag)
        except (errors.RevisionNotFound,
                errors.RevisionTagNotFound) as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        resp_body = revision_tag_view.ViewBuilder().show(resp_tag)
        resp.status = falcon.HTTP_200
        resp.text = utils.safe_yaml_dump(resp_body)

    @policy.authorize('deckhand:list_tags')
    def _list_all_tags(self, req, resp, revision_id):
        """List all tags for a revision."""
        try:
            resp_tags = db_api.revision_tag_get_all(revision_id)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        resp_body = revision_tag_view.ViewBuilder().list(resp_tags)
        resp.status = falcon.HTTP_200
        resp.text = utils.safe_yaml_dump(resp_body)

    def on_delete(self, req, resp, revision_id, tag=None):
        """Deletes a single tag or deletes all tags for a revision."""
        if tag:
            self._delete_tag(req, resp, revision_id, tag)
        else:
            self._delete_all_tags(req, resp, revision_id)

    @policy.authorize('deckhand:delete_tag')
    def _delete_tag(self, req, resp, revision_id, tag):
        """Delete a specified tag."""
        try:
            db_api.revision_tag_delete(revision_id, tag)
        except (errors.RevisionNotFound,
                errors.RevisionTagNotFound) as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        resp.status = falcon.HTTP_204

    @policy.authorize('deckhand:delete_tags')
    def _delete_all_tags(self, req, resp, revision_id):
        """Delete all tags for a revision."""
        try:
            db_api.revision_tag_delete_all(revision_id)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        resp.status = falcon.HTTP_204
