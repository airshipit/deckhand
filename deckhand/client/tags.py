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


class RevisionTag(base.Resource):
    def __repr__(self):
        try:
            return ("<Revision Tag: %s>" % self.tag)
        except AttributeError:
            return ("<Revision Tag>")


class RevisionTagManager(base.Manager):
    """Manage :class:`RevisionTag` resources."""
    resource_class = RevisionTag

    def list(self, revision_id):
        """Get list of revision tags."""
        url = '/revisions/%s/tags' % revision_id
        return self._list(url)

    def get(self, revision_id, tag):
        """Get details for a revision tag."""
        url = '/revisions/%s/tags/%s' % (revision_id, tag)
        return self._get(url)

    def create(self, revision_id, tag, data=None):
        """Create a revision tag."""
        url = '/revisions/%s/tags/%s' % (revision_id, tag)
        return self._create(url, data=data)

    def delete(self, revision_id, tag):
        """Delete a revision tag."""
        url = '/revisions/%s/tags/%s' % (revision_id, tag)
        return self._delete(url)

    def delete_all(self, revision_id):
        """Delete all revision tags."""
        url = '/revisions/%s/tags' % revision_id
        return self._delete(url)
