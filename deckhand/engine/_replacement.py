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

"""Functions for validation replacement logic."""
from deckhand import errors


def check_document_with_replacement_field_has_parent(
        parent_meta, parent, document):
    """Validate that a document with ``metadata.replacement`` has a parent."""
    if not parent_meta or not parent:
        error_message = (
            'Document replacement requires that the document with '
            '`replacement: true` have a parent.')
        raise errors.InvalidDocumentReplacement(
            schema=document.schema, name=document.name,
            layer=document.layer, reason=error_message)


def check_replacement_and_parent_same_schema_and_name(
        parent, document):
    """Validate that replacement-child and replacement-parent documents have
    the same ``schema`` and ``metadata.name`` values which is a hard
    requirement for replacement.

    """
    # This checks that a document can only be a replacement for
    # another document with the same `metadata.name` and `schema`.
    if not (document.schema == parent.schema and
            document.name == parent.name):
        error_message = (
            'Document replacement requires that both documents '
            'have the same `schema` and `metadata.name`.')
        raise errors.InvalidDocumentReplacement(
            schema=document.schema, name=document.name,
            layer=document.layer, reason=error_message)


def check_child_and_parent_different_metadata_name(
        parent, document):
    """Validate that "regular" child and parent documents (without a
    replacement relationship) have the same ``schema`` but different
    ``metadata.name``.

    """
    if (parent and document.schema == parent.schema and
            document.name == parent.name):
        error_message = (
            'Non-replacement documents cannot have the same `schema` '
            'and `metadata.name` as their parent. Either add '
            '`replacement: true` to the document or give the document '
            'a different name.')
        raise errors.InvalidDocumentReplacement(
            schema=document.schema, name=document.name,
            layer=document.layer, reason=error_message)


def check_only_one_level_of_replacement(src_ref):
    """Validate that only one level of replacement exists, meaning that
    a replacement document cannot itself be replaced by yet another
    replacement document.

    """
    # If the document has a replacement, use the replacement as the
    # substitution source instead.
    if src_ref.is_replacement:
        error_message = ('A replacement document cannot itself'
                         ' be replaced by another document.')
        raise errors.InvalidDocumentReplacement(
            schema=src_ref.schema, name=src_ref.name,
            layer=src_ref.layer, reason=error_message)
