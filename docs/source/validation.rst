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

Validation Stages
-----------------

Deckhand performs pre- and post-rendering validation on documents. For
pre-rendering validation 3 types of behavior are possible:

#. Successfully validated docuemnts are stored in Deckhand's database.
#. Failure to validate a document's basic properties will result in a 400
   Bad Request error getting raised.
#. Failure to validate a document's schema-specific properties will result
   in a validation error created in the database, which can be later
   returned via the Validations API.

For post-rendering validation, 2 types of behavior are possible:

#. Successfully valdiated post-rendered documents are returned to the user.
#. Failure to validate post-rendered documents results in a 500 Internal Server
   Error getting raised.

Validation Module
-----------------

.. autoclass:: deckhand.engine.document_validation.DocumentValidation
   :members:
   :private-members:

.. _schemas:

Validation Schemas
==================

Below are the schemas Deckhand uses to validate documents.

Base Schema
-----------

* Base schema.

  Base JSON schema against which all Deckhand documents are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/base_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Base schema that applies to all documents.

  This schema is used to sanity-check all documents that are passed to
  Deckhand. Failure to pass this schema results in a critical error.

DataSchema Schemas
------------------

All schemas below are ``DataSchema`` documents. They define additional
properties not included in the base schema or override default properties in
the base schema.

These schemas are only enforced after validation for the base schema has
passed. Failure to pass these schemas will result in an error entry being
created for the validation with name ``deckhand-schema-validation``
corresponding to the created revision.

* ``CertificateAuthorityKey`` schema.

  JSON schema against which all documents with
  ``deckhand/CertificateAuthorityKey/v1`` schema are validated.

  .. literalinclude::
    ../../deckhand/engine/schemas/certificate_authority_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``CertificateAuthorityKey`` documents.

  This schema is used to sanity-check all CertificateAuthorityKey documents
  that are passed to Deckhand.

* ``CertificateAuthority`` schema.

  JSON schema against which all documents with
  ``deckhand/CertificateAuthority/v1`` schema are validated.

  .. literalinclude::
    ../../deckhand/engine/schemas/certificate_authority_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``CertificateAuthority`` documents.

  This schema is used to sanity-check all ``CertificateAuthority`` documents
  that are passed to Deckhand.

* ``CertificateKey`` schema.

  JSON schema against which all documents with ``deckhand/CertificateKey/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/certificate_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``CertificateKey`` documents.

  This schema is used to sanity-check all ``CertificateKey`` documents that are
  passed to Deckhand.

* ``Certificate`` schema.

  JSON schema against which all documents with ``deckhand/Certificate/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/certificate_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``Certificate`` documents.

  This schema is used to sanity-check all ``Certificate`` documents that are
  passed to Deckhand.

* ``DataSchema`` schema.

  JSON schema against which all documents with ``deckhand/DataSchema/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/dataschema_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``DataSchema`` documents.

  This schema is used to sanity-check all ``DataSchema`` documents that are
  passed to Deckhand.

* ``LayeringPolicy`` schema.

  JSON schema against which all documents with ``deckhand/LayeringPolicy/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/layering_policy_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``LayeringPolicy`` documents.

  This schema is used to sanity-check all ``LayeringPolicy`` documents that are
  passed to Deckhand.

* ``PrivateKey`` schema.

  JSON schema against which all documents with ``deckhand/PrivateKey/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/passphrase_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``PrivateKey`` documents.

  This schema is used to sanity-check all ``PrivateKey`` documents that are
  passed to Deckhand.

* ``PublicKey`` schema.

  JSON schema against which all documents with ``deckhand/PublicKey/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/public_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``PublicKey`` documents.

  This schema is used to sanity-check all ``PublicKey`` documents that are
  passed to Deckhand.

* ``Passphrase`` schema.

  JSON schema against which all documents with ``deckhand/Passphrase/v1``
  schema are validated.

  .. literalinclude:: ../../deckhand/engine/schemas/private_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``Passphrase`` documents.

  This schema is used to sanity-check all ``Passphrase`` documents that are
  passed to Deckhand.

* ``ValidationPolicy`` schema.

  JSON schema against which all documents with ``deckhand/ValidationPolicy/v1``
  schema are validated.

  .. literalinclude::
    ../../deckhand/engine/schemas/validation_policy_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``ValidationPolicy`` documents.

  This schema is used to sanity-check all ``ValidationPolicy`` documents that
  are passed to Deckhand.
