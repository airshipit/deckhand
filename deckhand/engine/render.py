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

from deckhand.engine import cache

__all__ = ('render',)


def render(revision_id, documents, encryption_sources=None):
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
        validate=False)
