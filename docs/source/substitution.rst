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

.. _substitution:

Document Substitution
=====================

Document substitution, simply put, allows one document to overwrite *parts* of
its own data with that of another document. Substitution involves a source
document sharing data with a destination document, which replaces its own data
with the shared data.

Substitution is primarily designed as a mechanism for inserting secrets into
configuration documents, but works for unencrypted source documents as well.
Substitution is applied at each layer after all merge actions occur.

.. note::

  Substitution is only applied to the ``data`` section of a document. This is
  because a document's ``metadata`` and ``schema`` sections should be
  immutable within the scope of a revision, for obvious reasons.

Concrete (non-abstract) documents can be used as a source of substitution
into other documents. This substitution is layer-independent, so given the 3
layer example above, which includes ``global``, ``region`` and ``site`` layers,
a document in the ``region`` layer could insert data from a document in the
``site`` layer.

Here is a sample set of documents demonstrating substitution:

.. code-block:: yaml

  ---
  schema: deckhand/Certificate/v1
  metadata:
    name: example-cert
    storagePolicy: cleartext
    layeringDefinition:
      layer: site
  data: |
    CERTIFICATE DATA
  ---
  schema: deckhand/CertificateKey/v1
  metadata:
    name: example-key
    storagePolicy: encrypted
    layeringDefinition:
      layer: site
  data: |
    KEY DATA
  ---
  schema: deckhand/Passphrase/v1
  metadata:
    name: example-password
    storagePolicy: encrypted
    layeringDefinition:
      layer: site
  data: my-secret-password
  ---
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    storagePolicy: cleartext
    layeringDefinition:
      layer: region
    substitutions:
      - dest:
          path: .chart.values.tls.certificate
        src:
          schema: deckhand/Certificate/v1
          name: example-cert
          path: .
      - dest:
          path: .chart.values.tls.key
        src:
          schema: deckhand/CertificateKey/v1
          name: example-key
          path: .
      - dest:
          path: .chart.values.some_url
          pattern: INSERT_[A-Z]+_HERE
        src:
          schema: deckhand/Passphrase/v1
          name: example-password
          path: .
  data:
    chart:
      details:
        data: here
      values:
        some_url: http://admin:INSERT_PASSWORD_HERE@service-name:8080/v1
  ...

The rendered document will look like:

.. code-block:: yaml

  ---
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    storagePolicy: cleartext
    layeringDefinition:
      layer: region
    substitutions:
      - dest:
          path: .chart.values.tls.certificate
        src:
          schema: deckhand/Certificate/v1
          name: example-cert
          path: .
      - dest:
          path: .chart.values.tls.key
        src:
          schema: deckhand/CertificateKey/v1
          name: example-key
          path: .
      - dest:
          path: .chart.values.some_url
          pattern: INSERT_[A-Z]+_HERE
        src:
          schema: deckhand/Passphrase/v1
          name: example-password
          path: .
  data:
    chart:
      details:
        data: here
      values:
        some_url: http://admin:my-secret-password@service-name:8080/v1
        tls:
          certificate: |
            CERTIFICATE DATA
          key: |
            KEY DATA
  ...

This substitution is also ``schema`` agnostic, meaning that source and
destination documents can have a different ``schema``.
