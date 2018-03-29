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

Overview
========

Deckhand is a storage service for YAML-based configuration documents. Deckhand
stores the documents using version control: Each time a collection of documents
is passed to Deckhand, a new revision is created. Thus, documents have a
revision history, allowing complex configurations to be incrementally modified
and validated. For example, if the first revision of documents fail validation,
deployers can make modifications to the documents and submit them to Deckhand
again, until the documents pass validation and are ready to be rendered into
their finalized state.

Core Responsibilities
=====================

* *revision history* - improves auditability and enables services to provide
  functional validation of a well-defined collection of documents that are
  meant to operate together
* *validation* - allows services to implement and register different kinds of
  validations and report errors
* *buckets* - allow documents to be owned by different services, providing
  write protections around collections of documents
* *layering* - helps reduce duplication in configuration while maintaining
  auditability across many sites
* *substitution* - provides separation between secret data and other
  configuration data, while also providing a mechanism for documents to
  share data among themselves

Revision History
----------------

Like other version control software, Deckhand allows users to track incremental
changes to documents via a revision history, built up through individual
payloads to Deckhand, each forming a separate revision. Each revision, in other
words, contains its own set of immutable documents: Creating a new revision
maintains the existing revision history.

For more information, see the :ref:`revision-history` section.

Validation
----------

For each created revision, built-in :ref:`document-types` are automatically
validated. Validations are always stored in the database, including detailed
error messages explaining why validation failed, to help deployers rectify
syntactical or semantical issues with configuration documents. Regardless of
validation failure, a new revision is **always** created, except when the
documents are completely malformed.

Deckhand validation functionality is extensible via ``DataSchema`` documents,
allowing the ``data`` sections of registered document types to be subjected
to user-provided JSON schemas.

.. note::

  While Deckhand ingests YAML documents, internally it translates them to
  Python objects and can use JSON schemas to validate those objects.

For more information, see the :ref:`validation` section.

Buckets
-------

Collections of documents, called buckets, are managed together. All documents
belong to a bucket and all documents that are part of a bucket must be fully
specified together.

To create or update a new document in, e.g. bucket ``mop``, one must PUT the
entire set of documents already in ``mop`` along with the new or modified
document. Any documents not included in that PUT will be automatically
deleted in the created revision.

Each bucket provides write protections around a group of documents. That is,
only the bucket that owns a collection of documents can manage those documents.
However, documents can be read across different buckets and used together to
render finalized configuration documents, to be consumed by other services like
Armada, Drydock, Promenade or Shipyard.

In other words:

* Documents can be **read** from any bucket.

  This is useful so that documents from different buckets can be used together
  for layering and substitution.

* Documents can only be **written** to by the bucket that owns them.

  This is useful because it offers the concept of ownership to a document in
  which only the bucket that owns the document can manage it.

.. todo::

  Deckhand should offer RBAC (Role-Based Access Control) around buckets. This
  will allow deployers to control permissions around who can write or read
  documents to or from buckets.

.. note::

  The best analogy for a bucket is a folder. Like a folder, which houses files
  and offers read and write permissions, a bucket houses documents and offers
  read and write permissions around them.

  A bucket is **not** akin to a repository, because a repository has its own
  distinct revision history. A bucket, on the other hand, shares its revision
  history with every other bucket.

Layering
--------

Layering provides a restricted data inheritance model intended to help reduce
duplication in configuration. A ``LayeringPolicy`` can be created to declare
the order of inheritance via layers for documents. Parent documents can
provide common data to child documents, who can override their parent data
or tweak it in order to achieve more nuanced configuration that builds on top
of common configurations.

For more information, see the :ref:`layering` section.

Substitution
------------

Substitution is a mechanism for documents to share data among themselves. It
is particularly useful for documents that possess secrets to be stored securely
and on demand provide the secrets to documents that need them. However,
substitution can also apply to any data, not just secrets.

For more information, see the :ref:`substitution` section.

Replacement
-----------

Document replacement provides an advanced mechanism for reducing the overhead
with data duplication across multiple documents.

For more information, see the :ref:`replacement` section.
