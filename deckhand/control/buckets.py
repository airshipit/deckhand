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
from deckhand.common import document as document_wrapper
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

    @policy.authorize('deckhand:create_cleartext_documents')
    def on_put(self, req, resp, bucket_name=None):
        data = self.from_yaml(req, expect_list=True, allow_empty=True)
        documents = document_wrapper.DocumentDict.from_list(data)

        # NOTE: Must validate documents before doing policy enforcement,
        # because we expect certain formatting of the documents while doing
        # policy enforcement. If any documents fail basic schema validaiton
        # raise an exception immediately.
        data_schemas = db_api.revision_documents_get(
            schema=types.DATA_SCHEMA_SCHEMA, deleted=False)
        try:
            doc_validator = document_validation.DocumentValidation(
                documents, data_schemas, pre_validate=True)
            doc_validator.validate_all()
        except deckhand_errors.InvalidDocumentFormat as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        for document in documents:
            if secrets_manager.SecretsManager.requires_encryption(document):
                policy.conditional_authorize(
                    'deckhand:create_encrypted_documents', req.context)
                break

        documents = self._encrypt_secret_documents(documents)

        created_documents = self._create_revision_documents(
            bucket_name, documents)

        resp.text = utils.safe_yaml_dump(
            self.view_builder.list(created_documents))
        resp.status = falcon.HTTP_200

    def _encrypt_secret_documents(self, documents):
        # Encrypt data for secret documents, if any.
        for document in documents:
            if secrets_manager.SecretsManager.requires_encryption(document):
                secret_ref = secrets_manager.SecretsManager.create(document)
                document['data'] = secret_ref
        return documents

    def _create_revision_documents(self, bucket_name, documents):
        try:
            created_documents = db_api.documents_create(bucket_name, documents)
        except (deckhand_errors.DuplicateDocumentExists,
                deckhand_errors.SingletonDocumentConflict) as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        return created_documents
