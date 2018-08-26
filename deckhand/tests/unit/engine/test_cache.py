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

from threading import Thread
import time

import testtools

from deckhand.engine import cache
from deckhand import factories
from deckhand.tests.unit import base as test_base


class RenderedDocumentsCacheTest(test_base.DeckhandTestCase):

    def test_lookup_by_revision_id_cache(self):
        """Validate ``lookup_by_revision_id`` caching works.

        Passing in None in lieu of the actual documents proves that:

        * if the payload is in the cache, then no error is thrown since the
          cache is hit so no further processing is performed, where otherwise a
          method would be called on `None`
        * if the payload is not in the cache, then following logic above,
          method is called on `None`, raising AttributeError
        """

        document_factory = factories.DocumentFactory(1, [1])
        documents = document_factory.gen_test({})

        # Validate that caching the ref returns expected payload.
        rendered_documents, cache_hit = cache.lookup_by_revision_id(
            1, documents)
        self.assertIsInstance(rendered_documents, list)
        self.assertFalse(cache_hit)

        # Validate that the cache actually works.
        next_rendered_documents, cache_hit = cache.lookup_by_revision_id(
            1, None)
        self.assertEqual(rendered_documents, next_rendered_documents)
        self.assertTrue(cache_hit)

        # No documents passed in and revision ID 2 isn't cached - so expect
        # this to blow up.
        with testtools.ExpectedException(AttributeError):
            cache.lookup_by_revision_id(2, None)

        # Invalidate the cache and ensure the original data isn't there.
        cache.invalidate()

        # The cache won't be hit this time - expect AttributeError.
        with testtools.ExpectedException(AttributeError):
            cache.lookup_by_revision_id(1, None)

    def test_lookup_by_revision_id_cache_multiple_threads(self):
        """Validate that cache works across multiple threads: each thread
        should use the same set of rendered documents.
        """
        document_factory = factories.DocumentFactory(1, [1])
        documents1 = document_factory.gen_test({})
        documents2 = document_factory.gen_test({})
        # Sanity-check that the document sets differ.
        self.assertNotEqual(documents1, documents2)

        rendered_documents_by_thread = []
        cache_hit_by_thread = []

        def threaded_function(documents):
            # Validate that caching the ref returns expected payload.
            rendered_documents, cache_hit = cache.lookup_by_revision_id(
                1, documents)
            rendered_documents_by_thread.append(rendered_documents)
            cache_hit_by_thread.append(cache_hit)

        thread1 = Thread(target=threaded_function,
                         kwargs={'documents': documents1})
        thread2 = Thread(target=threaded_function,
                         kwargs={'documents': documents2})
        thread1.start()
        # NOTE(felipemonteiro): Add a sleep here to avoid a data race where the
        # cache might not be populated fast enough before the second thread
        # checks the cache -- and finds nothing thereby proceeding with another
        # render request. In real scenarios, though, this is highly unlikely.
        time.sleep(1)
        thread2.start()
        thread1.join()
        thread2.join()

        # Validate that 2nd thread uses 1st thread's document set which proves
        # caching working across threads.
        self.assertEqual(2, len(rendered_documents_by_thread))
        self.assertEqual(rendered_documents_by_thread[0],
                         rendered_documents_by_thread[1])
        self.assertFalse(cache_hit_by_thread[0])  # 1st time missing in cache.
        self.assertTrue(cache_hit_by_thread[1])  # 2nd time should hit cache.
