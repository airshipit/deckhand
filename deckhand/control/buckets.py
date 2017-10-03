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
import six

from deckhand.control import base as api_base
from deckhand.control.views import document as document_view
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import document_validation
from deckhand.engine import secrets_manager
from deckhand import errors as deckhand_errors
from deckhand import policy
from deckhand import types

LOG = logging.getLogger(__name__)


class BucketsResource(api_base.BaseResource):
    """API resource for realizing CRUD operations for buckets."""

    view_builder = document_view.ViewBuilder()
    secrets_mgr = secrets_manager.SecretsManager()

    @policy.authorize('deckhand:create_cleartext_documents')
    def on_put(self, req, resp, bucket_name=None):
        document_data = req.stream.read(req.content_length or 0)
        try:
            documents = list(yaml.safe_load_all(document_data))
        except yaml.YAMLError as e:
            error_msg = ("Could not parse the document into YAML data. "
                         "Details: %s." % e)
            LOG.error(error_msg)
            raise falcon.HTTPBadRequest(description=six.text_type(e))

        # NOTE: Must validate documents before doing policy enforcement,
        # because we expect certain formatting of the documents while doing
        # policy enforcement.
        validation_policies = self._create_validation_policies(documents)

        for document in documents:
            if document['metadata'].get('storagePolicy') == 'encrypted':
                policy.conditional_authorize(
                    'deckhand:create_encrypted_documents', req.context)
                break

        self._prepare_secret_documents(documents)

        # Save all the documents, including validation policies.
        documents_to_create = documents + validation_policies
        created_documents = self._create_revision_documents(
            bucket_name, list(documents_to_create))

        if created_documents:
            resp.body = self.to_yaml_body(
                self.view_builder.list(created_documents))
        resp.status = falcon.HTTP_200
        resp.append_header('Content-Type', 'application/x-yaml')

    def _create_validation_policies(self, documents):
        # All concrete documents in the payload must successfully pass their
        # JSON schema validations. Otherwise raise an error.
        try:
            validation_policies = document_validation.DocumentValidation(
                documents).validate_all()
        except deckhand_errors.InvalidDocumentFormat as e:
            # FIXME(fmontei): Save the malformed documents and the failed
            # validation policy in the DB for future debugging, and only
            # afterward raise an exception.
            raise falcon.HTTPBadRequest(description=e.format_message())
        return validation_policies

    def _prepare_secret_documents(self, secret_documents):
        # Encrypt data for secret documents, if any.
        for document in secret_documents:
            # TODO(fmontei): Move all of this to document validation directly.
            if document['metadata'].get('storagePolicy') == 'encrypted':
                secret_data = self.secrets_mgr.create(document)
                document['data'] = secret_data
            elif any([document['schema'].startswith(t)
                      for t in types.DOCUMENT_SECRET_TYPES]):
                document['data'] = {'secret': document['data']}

    def _create_revision_documents(self, bucket_name, documents):
        try:
            created_documents = db_api.documents_create(bucket_name, documents)
        except deckhand_errors.DocumentExists as e:
            raise falcon.HTTPConflict(description=e.format_message())
        except Exception as e:
            raise falcon.HTTPInternalServerError(description=six.text_type(e))

        return created_documents
