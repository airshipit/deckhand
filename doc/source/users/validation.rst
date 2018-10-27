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
immediately upon document ingestion. Deckhand's internal schema validations are
defined as ``DataSchema`` documents.

Here is a list of internal validations:

* ``deckhand-document-schema-validation`` - All concrete documents in the
  revision successfully pass their JSON schema validations. Will cause
  this to report an error.
* ``deckhand-policy-validation`` (TODO) - All required policy documents are in-place,
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

Validation Codes
^^^^^^^^^^^^^^^^

* D001 - Indicates document sanity-check validation failure pre- or
  post-rendering. This means that the document structure is fundamentally
  broken.
* D002 - Indicates document post-rendering validation failure. This means
  that after a document has rendered, the document may fail validation.
  For example, if a ``DataSchema`` document for a given revision indicates
  that ``.data.a`` is a required field but a layering action during rendering
  deletes ``.data.a``, then post-rendering validation will necessarily
  fail. This implies a conflict in the set of document requirements.

Schema Validations
------------------

Schema validations are controlled by two mechanisms:

1) Deckhand's internal schema validation for sanity-checking the formatting
   of the default documents that it understands. For example, Deckhand
   will check that a ``LayeringPolicy``, ``ValidationPolicy`` or ``DataSchema``
   adhere to the appropriate internal schemas.

2) Externally provided validations via ``DataSchema`` documents. These
   documents can be registered by external services and subject the target
   document's ``data`` section to *additional* validations, validations
   specified by the ``data`` section of the ``DataSchema`` document.

Policy Validations
------------------

*Not yet implemented*.

Validation Policies
-------------------

Validation policies are optional. Deckhand will perform all internal and
externally registered schema validations against all documents, with or without
any Validation Policies.

All ``ValidationPolicy`` documents in Deckhand are externally registered. They
allow services to report success or failure of named validations for a given
revision. The intended purpose is to allow a simple mapping that enables
consuming services to be able to quickly check whether the configuration in
Deckhand is in a valid state for performing a specific action.

``ValidationPolicy`` documents are not the same as ``DataSchema`` documents.
A ``ValidationPolicy`` document can reference a list of internal Deckhand
validations in addition to externally registered ``DataSchema`` documents.
Whereas a ``DataSchema`` document specifies a new set of validations to check
against relevant documents, a ``ValidationPolicy`` is a bookkeeping device
that merely lists the set of validations in a revision that need to succeed
in order for the revision itself to be valid.

For example, given Revision 1 which contains a ``ValidationPolicy`` of:

::

  ---
  schema: deckhand/ValidationPolicy/v1
  metadata:
    schema: metadata/Control/v1
    name: later-validation
    layeringDefinition:
      abstract: False
      layer: site
  data:
    validations:
      - name: deckhand-schema-validation
      - name: drydock-site-validation

Deckhand automatically creates ``deckhand-schema-validation`` as soon as the
revision itself is created. Afterward, Drydock can POST its result for
``drydock-site-validation`` using Deckhand's Validations API. Finally, Shipyard
query Deckhand's Validations API which in turn checks whether all validations
contained in the ``ValidationPolicy`` above are successful, before it proceeds
to the next stage in its workflow.

Missing Validations
^^^^^^^^^^^^^^^^^^^

Validations contained in a ``ValidationPolicy`` but which were never created
in Deckhand for a given revision are considered missing. Missing validations
result in the entire validation result reporting "failure".

If, for example, Drydock never POSTed a result for ``drydock-site-validation``
then the Deckhand Validations API will return a "failure" result, even if
``deckhand-schema-validation`` reports "success".

Extra Validations
^^^^^^^^^^^^^^^^^

Validations that are registered in Deckhand via the Validations API
but are not included in the ``ValidationPolicy`` (if one exists) for a given
revision are **ignored** (with the original status reported as
"ignored [failure]" or "ignored [success]").

For example, given the ``ValidationPolicy`` example above, if Promenade POSTs
``promenade-schema-validation`` with a result of "failure", then the *overall*
validation status for the given revision returned by Deckhand will be *success*
because the "failure" result from Promenade, since it was never registered,
will be ignored.

Validation Stages
-----------------

Deckhand performs pre- and post-rendering validation on documents.

Pre-Rendering
^^^^^^^^^^^^^

Carried out during document ingestion.

For pre-rendering validation 3 types of behavior are possible:

#. Successfully validated documents are stored in Deckhand's database.
#. Failure to validate a document's basic properties will result in a 400
   Bad Request error getting raised.
#. Failure to validate a document's schema-specific properties will result
   in a validation error created in the database, which can be later
   returned via the Validations API.

Post-Rendering
^^^^^^^^^^^^^^

Carried out after rendering all documents.

For post-rendering validation, 2 types of behavior are possible:

#. Successfully validated post-rendered documents are returned to the user.
#. Failure to validate post-rendered documents results in a 500 Internal Server
   Error getting raised.

.. _schemas:

Validation Schemas
==================

Below are the schemas Deckhand uses to validate documents.

Base Schema
-----------

* Base schema.

  Base JSON schema against which all Deckhand documents are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/base_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Base schema that applies to all documents.

  This schema is used to sanity-check all documents that are passed to
  Deckhand. Failure to pass this schema results in a critical error.

Metadata Schemas
----------------

Metadata schemas validate the ``metadata`` section of every document
ingested by Deckhand.

* ``Metadata Control`` schema.

  JSON schema against which the metadata section of each ``metadata/Control``
  document type is validated. Applies to all static documents meant to
  configure Deckhand behavior, like LayeringPolicy, ValidationPolicy,
  and DataSchema documents.

  .. literalinclude:: ../../../deckhand/engine/schemas/metadata_control.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``metadata/Control`` metadata document sections.

* ``Metadata Document`` schema.

  JSON schema against which the metadata section of each ``metadata/Document``
  document type is validated. Applies to all site definition documents or
  "regular" documents that require rendering.

  .. literalinclude:: ../../../deckhand/engine/schemas/metadata_document.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``metadata/Document`` metadata document sections.

.. _validation-schemas:

Validation Schemas
------------------

DataSchema schemas validate the ``data`` section of every document ingested
by Deckhand.

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
    ../../../deckhand/engine/schemas/certificate_authority_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``CertificateAuthorityKey`` documents.

  This schema is used to sanity-check all CertificateAuthorityKey documents
  that are passed to Deckhand.

* ``CertificateAuthority`` schema.

  JSON schema against which all documents with
  ``deckhand/CertificateAuthority/v1`` schema are validated.

  .. literalinclude::
    ../../../deckhand/engine/schemas/certificate_authority_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``CertificateAuthority`` documents.

  This schema is used to sanity-check all ``CertificateAuthority`` documents
  that are passed to Deckhand.

* ``CertificateKey`` schema.

  JSON schema against which all documents with ``deckhand/CertificateKey/v1``
  schema are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/certificate_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``CertificateKey`` documents.

  This schema is used to sanity-check all ``CertificateKey`` documents that are
  passed to Deckhand.

* ``Certificate`` schema.

  JSON schema against which all documents with ``deckhand/Certificate/v1``
  schema are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/certificate_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``Certificate`` documents.

  This schema is used to sanity-check all ``Certificate`` documents that are
  passed to Deckhand.

* ``LayeringPolicy`` schema.

  JSON schema against which all documents with ``deckhand/LayeringPolicy/v1``
  schema are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/layering_policy_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``LayeringPolicy`` documents.

  This schema is used to sanity-check all ``LayeringPolicy`` documents that are
  passed to Deckhand.

* ``PrivateKey`` schema.

  JSON schema against which all documents with ``deckhand/PrivateKey/v1``
  schema are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/passphrase_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``PrivateKey`` documents.

  This schema is used to sanity-check all ``PrivateKey`` documents that are
  passed to Deckhand.

* ``PublicKey`` schema.

  JSON schema against which all documents with ``deckhand/PublicKey/v1``
  schema are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/public_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``PublicKey`` documents.

  This schema is used to sanity-check all ``PublicKey`` documents that are
  passed to Deckhand.

* ``Passphrase`` schema.

  JSON schema against which all documents with ``deckhand/Passphrase/v1``
  schema are validated.

  .. literalinclude:: ../../../deckhand/engine/schemas/private_key_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``Passphrase`` documents.

  This schema is used to sanity-check all ``Passphrase`` documents that are
  passed to Deckhand.

* ``ValidationPolicy`` schema.

  JSON schema against which all documents with ``deckhand/ValidationPolicy/v1``
  schema are validated.

  .. literalinclude::
    ../../../deckhand/engine/schemas/validation_policy_schema.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``ValidationPolicy`` documents.

  This schema is used to sanity-check all ``ValidationPolicy`` documents that
  are passed to Deckhand.
