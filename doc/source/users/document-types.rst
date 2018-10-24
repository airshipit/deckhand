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

.. _application-documents:

Application Documents
---------------------

Application documents are those whose ``metadata.schema`` begins with
``metadata/Document``. These documents define all the data that make up
a site deployment, including but not limited to: networking, hardware, host,
bare metal, software, etc. site information. Prior to ingestion by Deckhand,
application documents are known as "raw documents". After rendering, they are
known as "rendered documents". Application documents are subject to the
following :ref:`rendering` operations:

* :ref:`encryption`
* :ref:`layering`
* :ref:`substitution`
* :ref:`replacement`

.. _control-documents:

Control Documents
-----------------

Control documents (documents which have ``metadata.schema`` of
``metadata/Control/v1``), are special, and are used to control
the behavior of Deckhand at runtime. Control documents are immutable so
any document mutation or manipulation does not apply to them.

Control documents only exist to control how :ref:`application-documents` are
validated and rendered.

.. note::

  Unlike :ref:`application-documents`, control documents do not require
  ``storagePolicy`` or ``layeringDefinition`` properties; in fact, it is
  recommended that such properties not be used for control documents. Again,
  this is because such documents should not themselves undergo layering,
  substitution or encryption. It is not meaningful to treat them like normal
  documents. See :ref:`validation-schemas` for more information on required
  document properties.

Only the following types of control documents are allowed:

DataSchema
^^^^^^^^^^

``DataSchema`` documents are used by various services to register new schemas
that Deckhand can use for validation. No ``DataSchema`` documents with names
beginning with ``deckhand/`` or ``metadata/`` are allowed. The
``metadata.name`` field of each ``DataSchema`` document references the
top-level ``schema`` of  :ref:`application-documents`: when there is a match
between both values, the ``data`` section of all :ref:`application-documents`
is validated against the JSON schema found in the matching ``DataSchema``
document.

The JSON schema definition is found in the ``data`` key of each ``DataSchema``
document. The entire ``data`` section of the target document is validated.

The following is an example of a sample ``DataSchema`` document, whose ``data``
section features a simplistic JSON schema:

.. code-block:: yaml

  ---
  # This specifies the official JSON schema meta-schema.
  schema: deckhand/DataSchema/v1
  metadata:
    schema: metadata/Control/v1
    name: promenade/Node/v1  # Specifies the documents to be used for validation.
    labels:
      application: promenade
  data:  # Valid JSON Schema is expected here.
    $schema: http://blah
    properties:
      foo:
        enum:
          - bar
          - baz
          - qux
    required:
      - foo
  ...

The JSON schema abvove requires that the ``data`` section of
:ref:`application-documents` that match this ``DataSchema`` have a property
called ``foo`` whose value must be one of: "bar", "baz", or "qux".

Reference the `JSON schema`_ documentation for more information on writing
correct schemas.

.. _JSON schema: http://json-schema.org

.. _layering-policy:

LayeringPolicy
^^^^^^^^^^^^^^

This document defines the strict order in which documents are layered together
from their component parts.

Only one ``LayeringPolicy`` document can exist within the system at any time.
It is an error to attempt to insert a new ``LayeringPolicy`` document if it has
a different ``metadata.name`` than the existing document. If the names match,
it is treated as an update to the existing document.

.. note::

  In order to create a new ``LayeringPolicy`` document in Deckhand, submit
  an **empty** payload via ``PUT /buckets/{bucket_name}/documents``. Afterward,
  submit another request containing the new batch of documents, including
  the new ``LayeringPolicy``.

This document defines the strict order in which documents are merged together
from their component parts. An error is raised if a document refers to a layer
not specified in the ``LayeringPolicy``.

Below is an example of a ``LayeringPolicy`` document:

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

In the ``LayeringPolicy`` above, a 5-tier ``layerOrder`` is created, in which
the topmost layer is ``global`` and the bottommost layer is ``force``. This
means that ``global`` constitutes the "base" layer onto which other documents
belonging to sub-layers can be layered. In practice, this means that
documents with ``site-type`` can layer with documents with ``global`` and
documents with ``region`` can layer with documents with ``site-type``, etc.

Note that in the absence of any document belonging to an "intermediate" layer,
base layers can layer with "interspersed" sub-layers, no matter the number of
layers between them. This means that a document with layer ``force`` could
layer with a document with layer ``global``, *provided* no document exists
with a layer of ``site-type``, ``region``, or ``site``. For more information
about document layering, reference the :ref:`layering` documentation.

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
