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

from oslo_log import log as logging

from deckhand.control import base as api_base
from deckhand.engine import document_validation
from deckhand import errors as deckhand_errors
from deckhand.objects import documents

LOG = logging.getLogger(__name__)


class DocumentsResource(api_base.BaseResource):
    """API resource for realizing CRUD endpoints for Documents."""

    def __init__(self, **kwargs):
        super(DocumentsResource, self).__init__(**kwargs)
        self.authorized_roles = ['user']

    def on_get(self, req, resp):
        pass

    def on_head(self, req, resp):
        pass

    def on_post(self, req, resp):
        """Create a document. Accepts YAML data only."""
        if req.content_type != 'application/x-yaml':
            LOG.warning('Requires application/yaml payload.')

        document_data = req.stream.read(req.content_length or 0)

        try:
            document = yaml.safe_load(document_data)
        except yaml.YAMLError as e:
            error_msg = ("Could not parse the document into YAML data. "
                         "Details: %s." % e)
            LOG.error(error_msg)
            return self.return_error(resp, falcon.HTTP_400, message=error_msg)

        # Validate the document before doing anything with it.
        try:
            doc_validation = document_validation.DocumentValidation(document)
        except deckhand_errors.InvalidFormat as e:
            return self.return_error(resp, falcon.HTTP_400, message=e)

        try:
            LOG.debug('Calling Document.create()')
            documents.Document().create(document)
        except Exception as e:
            LOG.exception(e)
            raise

        # Check if a document with the specified name already exists. If so,
        # treat this request as an update.
        doc_name = doc_validation.doc_name

        resp.data = doc_name
        resp.status = falcon.HTTP_201

    def _check_document_exists(self):
        pass
