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


class Validation(base.Resource):
    def __repr__(self):
        return ("<Validation>")


class ValidationManager(base.Manager):
    """Manage :class:`Validation` resources."""
    resource_class = Validation

    def list(self, revision_id):
        """Get list of revision validations."""
        url = '/revisions/%s/validations' % revision_id
        return self._list(url)

    def list_entries(self, revision_id, validation_name):
        """Get list of entries for a validation."""
        url = '/revisions/%s/validations/%s' % (revision_id, validation_name)
        # Call `_get` instead of `_list` because the response from the server
        # is a dict of form `{"count": n, "results": []}`.
        return self._get(url)

    def get_entry(self, revision_id, validation_name, entry_id):
        """Get entry details for a validation."""
        url = '/revisions/%s/validations/%s/entries/%s' % (
            revision_id, validation_name, entry_id)
        return self._get(url)

    def create(self, revision_id, validation_name, data):
        """Associate a validation with a revision."""
        url = '/revisions/%s/validations/%s' % (revision_id, validation_name)
        return self._create(url, data=data)
