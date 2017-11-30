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

.. _validation:

Document Validation
===================

Validations
-----------

The validation system provides a unified approach to complex validations that
require coordination of multiple documents and business logic that resides in
consumer services.

Deckhand focuses on two types of validations: schema validations and policy
validations.

Deckhand-Provided Validations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deckhand provides a few internal validations which are made available
immediately upon document ingestion.

Here is a list of internal validations:

* ``deckhand-document-schema-validation`` - All concrete documents in the
  revision successfully pass their JSON schema validations. Will cause
  this to report an error.
* ``deckhand-policy-validation`` - All required policy documents are in-place,
  and existing documents conform to those policies.  E.g. if a 3rd party
  document specifies a ``layer`` that is not present in the layering policy,
  that will cause this validation to report an error.

Externally Provided Validations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As mentioned, other services can report whether named validations that have
been registered by those services as success or failure. ``DataSchema`` control
documents are used to register a new validation mapping that other services
can reference to verify whether a Deckhand bucket is in a valid configuration.
For more information, refer to the ``DataSchema`` section in
:ref:`document-types`.

Schema Validations
^^^^^^^^^^^^^^^^^^

Schema validations are controlled by two mechanisms:

1) Deckhand's internal schema validation for sanity-checking the formatting
   of the default documents that it understands. For example, Deckhand
   will check that a ``LayeringPolicy``, ``ValidationPolicy`` or ``DataSchema``
   adhere to the "skeleton" or schemas registered under
   ``deckhand.engine.schema``.

   .. note::

      Each document is always subjected to 2 stages of document validation:
      the first stage checks whether the document adheres to the fundamental
      building blocks: Does it have a ``schema``, ``metadata``, and ``data``
      section? The second stage then checks whether the document's ``schema``
      passes a more nuanced schema validation specific to that ``schema``.

2) Externally provided validations via ``DataSchema`` documents. These
   documents can be registered by external services and subject the target
   document's data section to *additional* validations, validations specified
   by the ``data`` section of the ``DataSchema`` document.

   For more information about ``DataSchema`` documents, please refer to
   :ref:`document-types`.

Policy Validations
^^^^^^^^^^^^^^^^^^

*Not yet implemented*.

Validation Policies
^^^^^^^^^^^^^^^^^^^

Validation policies allow services to report success or failure of named
validations for a given revision. Those validations can then be referenced by
many ``ValidationPolicy`` control documents. The intended purpose use is to
allow a simple mapping that enables consuming services to be able to quickly
check whether the configuration in Deckhand is in a valid state for performing
a specific action.

.. note::

  ``ValidationPolicy`` documents are not the same as ``DataSchema`` documents.
  A ``ValidationPolicy`` document can reference a list of internal Deckhand
  validations in addition to externally registered ``DataSchema`` documents.
  Once all the validations specified in the ``ValidationPolicy`` are executed
  and succeed, then services can check whether the documents in a bucket are
  stable, in accordance with the ``ValidationPolicy``.

Validation Module
-----------------

.. autoclass:: deckhand.engine.document_validation.DocumentValidation
   :members:
   :private-members:

.. _schemas:

Validation Schemas
==================

Below are the schemas deckhand uses to validate documents.

.. automodule:: deckhand.engine.schema.base_schema
  :members: schema

.. automodule:: deckhand.engine.schema.v1_0.certificate_key_schema
  :members: schema

.. automodule:: deckhand.engine.schema.v1_0.certificate_schema
  :members: schema

.. automodule:: deckhand.engine.schema.v1_0.data_schema_schema
  :members: schema

.. automodule:: deckhand.engine.schema.v1_0.layering_policy_schema
  :members: schema

.. automodule:: deckhand.engine.schema.v1_0.passphrase_schema
  :members: schema

.. automodule:: deckhand.engine.schema.v1_0.validation_policy_schema
  :members: schema
