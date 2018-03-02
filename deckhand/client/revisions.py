# Copyright 2017 AT&T Intellectual Property.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from deckhand.client import base


class Revision(base.Resource):
    def __repr__(self):
        if hasattr(self, 'results'):
            return ', '.join(
                ["<Revision ID: %s>" % r['id'] for r in self.results])
        else:
            try:
                return ("<Revision ID: %s>" % base.getid(self))
            except Exception:
                return ("<Revision Diff>")


class RevisionManager(base.Manager):
    """Manage :class:`Revision` resources."""
    resource_class = Revision

    def list(self, **filters):
        """Get a list of revisions."""
        url = '/revisions'
        # Call `_get` instead of `_list` because the response from the server
        # is a dict of form `{"count": n, "results": []}`.
        return self._get(url, filters=filters)

    def get(self, revision_id):
        """Get details for a revision."""
        url = '/revisions/%s' % revision_id
        return self._get(url)

    def diff(self, revision_id, comparison_revision_id):
        """Get revision diff between two revisions."""
        url = '/revisions/%s/diff/%s' % (
            revision_id, comparison_revision_id)
        return self._get(url)

    def rollback(self, revision_id):
        """Rollback to a previous revision, effectively creating a new one."""
        url = '/rollback/%s' % revision_id
        return self._post(url)

    def documents(self, revision_id, rendered=True, **filters):
        """Get a list of revision documents or rendered documents.

        :param int revision_id: Revision ID.
        :param bool rendered: If True, returns list of rendered documents.
            Else returns list of unmodified, raw documents.
        :param filters: Filters to apply to response body.
        :returns: List of documents or rendered documents.
        :rtype: list[:class:`Revision`]
        """
        if rendered:
            url = '/revisions/%s/rendered-documents' % revision_id
        else:
            url = '/revisions/%s/documents' % revision_id
        return self._list(url, filters=filters)

    def delete_all(self):
        """Delete all revisions.

        .. warning::

            Effectively the same as purging the entire database.
        """
        url = '/revisions'
        return self._delete(url)
