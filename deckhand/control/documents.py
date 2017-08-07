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

import yaml

import falcon

from oslo_db import exception as db_exc
from oslo_log import log as logging

from deckhand.control import base as api_base
from deckhand.control.views import document as document_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import document_validation
from deckhand import errors as deckhand_errors

LOG = logging.getLogger(__name__)


class DocumentsResource(api_base.BaseResource):
    """API resource for realizing CRUD endpoints for Documents."""

    def on_post(self, req, resp):
        """Create a document. Accepts YAML data only."""
        if req.content_type != 'application/x-yaml':
            LOG.warning('Requires application/yaml payload.')

        document_data = req.stream.read(req.content_length or 0)

        try:
            documents = [d for d in yaml.safe_load_all(document_data)]
        except yaml.YAMLError as e:
            error_msg = ("Could not parse the document into YAML data. "
                         "Details: %s." % e)
            LOG.error(error_msg)
            return self.return_error(resp, falcon.HTTP_400, message=error_msg)

        # All concrete documents in the payload must successfully pass their
        # JSON schema validations. Otherwise raise an error.
        try:
            validation_policies = document_validation.DocumentValidation(
                documents).validate_all()
        except (deckhand_errors.InvalidDocumentFormat,
                deckhand_errors.UnknownDocumentFormat) as e:
            return self.return_error(resp, falcon.HTTP_400, message=e)

        try:
            created_documents = db_api.documents_create(
                documents, validation_policies)
        except db_exc.DBDuplicateEntry as e:
            return self.return_error(resp, falcon.HTTP_409, message=e)
        except Exception as e:
            return self.return_error(resp, falcon.HTTP_500, message=e)

        if created_documents:
            resp.status = falcon.HTTP_201
            resp.append_header('Content-Type', 'application/x-yaml')
            resp_body = document_view.ViewBuilder().list(created_documents)
            resp.body = self.to_yaml_body(resp_body)
        else:
            resp.status = falcon.HTTP_204
