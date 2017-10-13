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

.. _bucket:

Buckets
=======

Collections of documents, called buckets, are managed together. All documents
belong to a bucket and all documents that are part of a bucket must be fully
specified together.

To create or update a new document in, e.g. bucket ``mop``, one must PUT the
entire set of documents already in ``mop`` along with the new or modified
document. Any documents not included in that PUT will be automatically
deleted in the created revision.

This feature allows the separation of concerns when delivering different
categories of documents, while making the delivered payload more declarative.
