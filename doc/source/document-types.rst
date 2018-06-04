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

.. _document-types:

Document Types
==============

Control Documents
-----------------

Control documents (documents which have ``metadata.schema=metadata/Control/v1``),
are special, and are used to control the behavior of Deckhand at runtime. Only
the following types of control documents are allowed.

DataSchema
^^^^^^^^^^

``DataSchema`` documents are used by various services to register new schemas
that Deckhand can use for validation. No ``DataSchema`` documents with names
beginning with ``deckhand/`` or ``metadata/`` are allowed.  The ``metadata.name``
field of each ``DataSchema`` document specifies the top level ``schema`` that it
is used to validate against.

The contents of its ``data`` key are expected to be the JSON schema definition
for the target document type from the target's top level ``data`` key down.

.. TODO: give valid, tiny schema as example

.. code-block:: yaml

  ---
  schema: deckhand/DataSchema/v1  # This specifies the official JSON schema meta-schema.
  metadata:
    schema: metadata/Control/v1
    name: promenade/Node/v1  # Specifies the documents to be used for validation.
    labels:
      application: promenade
  data:  # Valid JSON Schema is expected here.
    $schema: http://blah
  ...

LayeringPolicy
^^^^^^^^^^^^^^

Only one ``LayeringPolicy`` document can exist within the system at any time.
It is an error to attempt to insert a new ``LayeringPolicy`` document if it has
a different ``metadata.name`` than the existing document. If the names match,
it is treated as an update to the existing document.

This document defines the strict order in which documents are merged together
from their component parts. It should result in a validation error if a
document refers to a layer not specified in the ``LayeringPolicy``.

.. code-block:: yaml

  ---
  schema: deckhand/LayeringPolicy/v1
  metadata:
    schema: metadata/Control/v1
    name: layering-policy
  data:
    layerOrder:
      - global
      - site-type
      - region
      - site
      - force
  ...

ValidationPolicy
^^^^^^^^^^^^^^^^

Unlike ``LayeringPolicy``, many ``ValidationPolicy`` documents are allowed. This
allows services to check whether a particular revision (described below) of
documents meets a configurable set of validations without having to know up
front the complete list of validations.

Each validation ``name`` specified here is a reference to data that is POSTable
by other services. Names beginning with ``deckhand`` are reserved for internal
use. See the Validation section below for more details.

Since validations may indicate interactions with external and changing
circumstances, an optional ``expiresAfter`` key may be specified for each
validation as an ISO8601 duration. If no ``expiresAfter`` is specified, a
successful validation does not expire. Note that expirations are specific to
the combination of ``ValidationPolicy`` and validation, not to each validation
by itself.

.. code-block:: yaml

  ---
  schema: deckhand/ValidationPolicy/v1
  metadata:
    schema: metadata/Control/v1
    name: site-deploy-ready
  data:
    validations:
      - name: deckhand-schema-validation
      - name: drydock-site-validation
        expiresAfter: P1W
      - name: promenade-site-validation
        expiresAfter: P1W
      - name: armada-deployability-validation
  ...

Provided Utility Document Kinds
-------------------------------

These are documents that use the ``Document`` metadata schema, but live in the
``deckhand`` namespace.

Certificate
^^^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/Certificate/v1
  metadata:
    schema: metadata/Document/v1
    name: application-api
    storagePolicy: cleartext
  data: |-
    -----BEGIN CERTIFICATE-----
    MIIDYDCCAkigAwIBAgIUKG41PW4VtiphzASAMY4/3hL8OtAwDQYJKoZIhvcNAQEL
    ...snip...
    P3WT9CfFARnsw2nKjnglQcwKkKLYip0WY2wh3FE7nrQZP6xKNaSRlh6p2pCGwwwH
    HkvVwA==
    -----END CERTIFICATE-----
  ...

CertificateAuthority
^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/CertificateAuthority/v1
  metadata:
    schema: metadata/Document/v1
    name: application-ca
    storagePolicy: cleartext
  data: some-ca
  ...

CertificateAuthorityKey
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/CertificateAuthorityKey/v1
  metadata:
    schema: metadata/Document/v1
    name: application-ca-key
    storagePolicy: encrypted
  data: |-
    -----BEGIN CERTIFICATE-----
    MIIDYDCCAkigAwIBAgIUKG41PW4VtiphzASAMY4/3hL8OtAwDQYJKoZIhvcNAQEL
    ...snip...
    P3WT9CfFARnsw2nKjnglQcwKkKLYip0WY2wh3FE7nrQZP6xKNaSRlh6p2pCGwwwH
    HkvVwA==
    -----END CERTIFICATE-----
  ...

CertificateKey
^^^^^^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/CertificateKey/v1
  metadata:
    schema: metadata/Document/v1
    name: application-api
    storagePolicy: encrypted
  data: |-
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpQIBAAKCAQEAx+m1+ao7uTVEs+I/Sie9YsXL0B9mOXFlzEdHX8P8x4nx78/T
    ...snip...
    Zf3ykIG8l71pIs4TGsPlnyeO6LzCWP5WRSh+BHnyXXjzx/uxMOpQ/6I=
    -----END RSA PRIVATE KEY-----
  ...

Passphrase
^^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/Passphrase/v1
  metadata:
    schema: metadata/Document/v1
    name: application-admin-password
    storagePolicy: encrypted
  data: some-password
  ...

PrivateKey
^^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/PrivateKey/v1
  metadata:
    schema: metadata/Document/v1
    name: application-private-key
    storagePolicy: encrypted
  data: some-private-key
  ...

PublicKey
^^^^^^^^^

.. code-block:: yaml

  ---
  schema: deckhand/PublicKey/v1
  metadata:
    schema: metadata/Document/v1
    name: application-public-key
    storagePolicy: cleartext
  data: some-password
  ...
