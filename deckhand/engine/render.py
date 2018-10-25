# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from oslo_log import log as logging

from deckhand.common import validation_message as vm
from deckhand.engine import cache
from deckhand import errors

LOG = logging.getLogger(__name__)

__all__ = ('render',
           'validate_render')


def render(revision_id, documents, encryption_sources=None,
           cleartext_secrets=False):
    """Render revision documents for ``revision_id`` using raw ``documents``.

    :param revision_id: Key used for caching rendered documents by.
    :type revision_id: int
    :param documents: List of raw documents corresponding to ``revision_id``
        to render.
    :type documents: List[dict]
    :param encryption_sources: A dictionary that maps the reference
        contained in the destination document's data section to the
        actual unecrypted data. If encrypting data with Barbican, the
        reference will be a Barbican secret reference.
    :type encryption_sources: dict
    :param cleartext_secrets: Whether to show unencrypted data as cleartext.
    :type cleartext_secrets: bool
    :returns: Rendered documents for ``revision_id``.
    :rtype: List[dict]

    """

    # NOTE(felipemonteiro): `validate` is False because documents have
    # already been pre-validated during ingestion. Documents are
    # post-validated below, regardless.
    return cache.lookup_by_revision_id(
        revision_id,
        documents,
        encryption_sources=encryption_sources,
        validate=False,
        cleartext_secrets=cleartext_secrets)


def validate_render(revision_id, rendered_documents, validator):
    """Validate rendered documents using ``validator``.

    :param revision_id: Key used for caching rendered documents by.
    :type revision_id: int
    :param documents: List of rendered documents corresponding to
        ``revision_id``.
    :type documents: List[dict]
    :param validator: Validation object used for validating
        ``rendered_documents``.
    :type validator: deckhand.engine.document_validation.DocumentValidation
    :raises: InvalidDocumentFormat if validation fails.

    """

    # Perform schema validation post-rendering to ensure that rendering
    # and substitution didn't break anything.
    try:
        validations = validator.validate_all()
    except errors.InvalidDocumentFormat as e:
        # Invalidate cache entry so that future lookups also fail.
        cache.invalidate_one(revision_id)
        # Post-rendering validation errors likely indicate an internal
        # rendering bug, so override the default code to 500.
        e.code = 500
        LOG.error('Failed to post-validate rendered documents.')
        LOG.exception(e.format_message())
        raise e

    error_list = []

    for validation in validations:
        if validation['status'] == 'failure':
            error_list.extend([
                vm.ValidationMessage(
                    message=error['message'],
                    name=vm.DOCUMENT_POST_RENDERING_FAILURE,
                    doc_schema=error['schema'],
                    doc_name=error['name'],
                    doc_layer=error['layer'],
                    diagnostic={
                        k: v for k, v in error.items() if k in (
                            'schema_path',
                            'validation_schema',
                            'error_section'
                        )
                    }
                )
                for error in validation['errors']
            ])

    if error_list:
        # Invalidate cache entry so that future lookups also fail.
        cache.invalidate_one(revision_id)
        raise errors.InvalidDocumentFormat(
            error_list=error_list,
            reason='Validation',
        )
