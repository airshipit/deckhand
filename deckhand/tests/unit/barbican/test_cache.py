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

import mock
import testtools

from deckhand.barbican import cache
from deckhand.tests import test_utils
from deckhand.tests.unit import base as test_base


class BarbicanCacheTest(test_base.DeckhandTestCase):

    def setUp(self):
        super(BarbicanCacheTest, self).setUp()
        self.secret_ref = test_utils.rand_barbican_ref()
        self.secret_payload = 'very-secret-payload'
        # Clear the cache between tests.
        cache.invalidate()

    def _mock_barbicanclient(self):
        def call_barbican(action, *args, **kwargs):
            if action == "secrets.create":
                return mock.Mock(**{'store.return_value': self.secret_ref})
            elif action == "secrets.get":
                return mock.Mock(payload=self.secret_payload)

        mock_barbicanclient = mock.Mock()
        mock_barbicanclient.call.side_effect = call_barbican

        return mock_barbicanclient

    @property
    def barbicanclient(self):
        return self._mock_barbicanclient()

    def test_lookup_by_ref_cache(self):
        """Validate ``lookup_by_ref`` caching works.

        Passing in None in lieu of an actual barbican client (or mock object)
        proves that:

        * if the payload is in the cache, then no error is thrown since the
          cache is hit so no further processing is performed, where otherwise a
          method would be called on `None`
        * if the payload is not in the cache, then following logic above,
          method is called on `None`, raising AttributeError
        """

        # Validate that caching the ref returns expected payload.
        secret = cache.lookup_by_ref(self.barbicanclient, self.secret_ref)
        self.assertEqual(self.secret_payload, secret.payload)

        # Validate that the cache actually works.
        next_secret = cache.lookup_by_ref(None, self.secret_ref)
        self.assertEqual(secret.payload, next_secret.payload)

        # Validate that the reverse cache works.
        kwargs = {'payload': secret.payload}
        secret_ref = cache.lookup_by_payload(self.barbicanclient, **kwargs)
        self.assertEqual(self.secret_ref, secret_ref)

        # Different ref isn't in cache - expect AttributeError.
        with testtools.ExpectedException(AttributeError):
            cache.lookup_by_ref(None, secret_ref='uh-oh')

        # Invalidate the cache and ensure the original data isn't there.
        cache.invalidate()

        # The cache won't be hit this time - expect AttributeError.
        with testtools.ExpectedException(AttributeError):
            cache.lookup_by_ref(None, self.secret_ref)

    def test_lookup_by_payload_cache(self):
        """Validate ``lookup_by_payload`` caching works.

        Passing in None in lieu of an actual barbican client (or mock object)
        proves that:

        * if the payload is in the cache, then no error is thrown since the
          cache is hit so no further processing is performed, where otherwise a
          method would be called on `None`
        * if the payload is not in the cache, then following logic above,
          method is called on `None`, raising AttributeError
        """

        # Validate that caching the payload returns expected ref.
        kwargs = {'payload': self.secret_payload}
        secret_ref = cache.lookup_by_payload(self.barbicanclient, **kwargs)
        self.assertEqual(self.secret_ref, secret_ref)

        # Validate that the cache actually works.
        next_secret_ref = cache.lookup_by_payload(None, **kwargs)
        self.assertEqual(secret_ref, next_secret_ref)

        # Validate that the reverse cache works.
        secret = cache.lookup_by_ref(self.barbicanclient, secret_ref)
        self.assertEqual(self.secret_payload, secret.payload)

        # Different payload isn't in cache - expect AttributeError.
        with testtools.ExpectedException(AttributeError):
            cache.lookup_by_payload(None, payload='uh-oh')

        # Invalidate the cache and ensure the original data isn't there.
        cache.invalidate()

        # The cache won't be hit this time - expect AttributeError.
        with testtools.ExpectedException(AttributeError):
            cache.lookup_by_payload(None, **kwargs)
