..
  Copyright 2017 AT&T Intellectual Property.
  All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License"); you may
  not use this file except in compliance with the License. You may obtain
  a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
  License for the specific language governing permissions and limitations
  under the License.

.. _revision-history:

Revision History
================

Revision History
----------------

Documents will be ingested in batches which will be given a revision index.
This provides a common language for describing complex validations on sets of
documents.

Revisions can be thought of as commits in a linear git history, thus looking
at a revision includes all content from previous revisions.

Revision Diffing
----------------

By maintaining a linear history of all the documents in each revision, Deckhand
is able to diff different revisions together to report what has changed
across revisions, allowing external services to determine whether the Deckhand
configuration undergone any changes since the service last queried the Deckhand
API.

The revision difference is calculated by comparing the `overall` difference
across all the documents in the buckets associated with the two revisions that
are diffed. For example, if a bucket shared between two revisions contains two
documents, and between the first revision and the second revision, if only
one of those two documents has been modified, the bucket itself is tagged
as ``modified``. For more information about revision diffing, please reference
the :ref:`api-ref`.

Revision Rollback
-----------------

As all the changes to documents are maintained via revisions, it is possible to
rollback the latest revision in Deckhand to a prior revision. This behavior can
be loosely compared to a ``git rebase`` in which it is possible to squash the
latest revision in order to go back to the previous revision. This behavior is
useful for undoing accidental changes and returning to a stable internal
configuration.
