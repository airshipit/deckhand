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


class Bucket(base.Resource):
    def __repr__(self):
        return ("<Bucket name: %s>" % self.status['bucket'])


class BucketManager(base.Manager):
    """Manage :class:`Bucket` resources."""
    resource_class = Bucket

    def update(self, bucket_name, documents):
        """Create, update or delete documents associated with a bucket.

        :param str bucket_name: Gets or creates a bucket by this name.
        :param str documents: YAML-formatted string of Deckhand-compatible
            documents to create in the bucket.
        :returns: The created documents along with their associated bucket
            and revision.
        """
        url = '/buckets/%s/documents' % bucket_name
        return self._update(url, documents)
