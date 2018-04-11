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
from deckhand.control.views import validation as validation_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class ValidationsResource(api_base.BaseResource):
    """API resource for realizing validations endpoints."""

    view_builder = validation_view.ViewBuilder()

    @policy.authorize('deckhand:create_validation')
    def on_post(self, req, resp, revision_id, validation_name):
        validation_data = self.from_yaml(
            req, expect_list=False, allow_empty=False)

        if not all([validation_data.get(x) for x in ('status', 'validator')]):
            error_msg = 'Validation payload must contain keys: %s.' % (
                ', '.join(['"status"', '"validator"']))
            LOG.error(error_msg)
            raise falcon.HTTPBadRequest(description=error_msg)

        try:
            resp_body = db_api.validation_create(
                revision_id, validation_name, validation_data)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                LOG.exception(e.format_message())

        resp.status = falcon.HTTP_201
        resp.append_header('Content-Type', 'application/x-yaml')
        resp.body = self.view_builder.show(resp_body)

    def on_get(self, req, resp, revision_id, validation_name=None,
               entry_id=None):
        if all([validation_name, entry_id]):
            resp_body = self._show_validation_entry(
                req, resp, revision_id, validation_name, entry_id)
        elif validation_name:
            resp_body = self._list_validation_entries(req, resp, revision_id,
                                                      validation_name)
        else:
            resp_body = self._list_all_validations(req, resp, revision_id)

        resp.status = falcon.HTTP_200
        resp.append_header('Content-Type', 'application/x-yaml')
        resp.body = resp_body

    @policy.authorize('deckhand:show_validation')
    def _show_validation_entry(self, req, resp, revision_id, validation_name,
                               entry_id):
        try:
            entry_id = int(entry_id)
        except ValueError:
            raise falcon.HTTPBadRequest(
                description='The {entry_id} parameter must be an integer.')

        try:
            entry = db_api.validation_get_entry(
                revision_id, validation_name, entry_id)
        except (errors.RevisionNotFound,
                errors.ValidationNotFound) as e:
            with excutils.save_and_reraise_exception():
                LOG.exception(e.format_message())

        resp_body = self.view_builder.show_entry(entry)
        return resp_body

    @policy.authorize('deckhand:list_validations')
    def _list_validation_entries(self, req, resp, revision_id,
                                 validation_name):
        try:
            entries = db_api.validation_get_all_entries(revision_id,
                                                        validation_name)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                LOG.exception(e.format_message())

        resp_body = self.view_builder.list_entries(entries)
        return resp_body

    @policy.authorize('deckhand:list_validations')
    def _list_all_validations(self, req, resp, revision_id):
        try:
            validations = db_api.validation_get_all(revision_id)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                LOG.exception(e.format_message())

        resp_body = self.view_builder.list(validations)
        return resp_body
