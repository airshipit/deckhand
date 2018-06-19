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

====================================
Welcome to Deckhand's documentation!
====================================

Deckhand is a document-based configuration storage service built with
auditability and validation in mind. It serves as the back-end storage service
for UCP.

Deckhand's primary responsibilities include validating and storing YAML
documents that are layered together to produce finalized documents, containing
site configuration data, including sensitive data. Secrets can be stored using
specialized secret storage management services like Barbican and later
substituted into finalized or "rendered" documents.

The service understands a variety of document formats, the combination of which
describe the manner in which Deckhand renders finalized documents for
consumption by other UCP services.

User's Guide
============

.. toctree::
   :maxdepth: 2

   getting-started
   overview
   revision-history
   documents
   document-types
   encryption
   validation
   rendering
   substitution
   layering
   replacement
   api_ref
   api_client
   exceptions

Developer's Guide
=================

.. toctree::
   :maxdepth: 2

   HACKING
   policy-enforcement
   testing

Release Notes
=============

.. toctree::
   :maxdepth: 1

   releasenotes/index.rst

Glossary
========

.. toctree::
   :maxdepth: 1

   glossary
