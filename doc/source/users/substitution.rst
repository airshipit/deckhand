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

Introduction
------------

Document substitution, simply put, allows one document to overwrite *parts* of
its own data with that of another document. Substitution involves a source
document sharing data with a destination document, which replaces its own data
with the shared data.

Substitution may be leveraged as a mechanism for:

* inserting secrets into configuration documents
* reducing data duplication by declaring common data within one document and
  having multiple other documents substitute data from the common location as
  needed

During document rendering, substitution is applied at each layer after all
merge actions occur. For more information on the interaction between
document layering and substitution, see: :ref:`rendering`.

Requirements
------------

Substitutions between documents are not restricted by ``schema``, ``name``,
nor ``layer``.  Source and destination documents do not need to share the same
``schema``.

No substitution dependency cycle may exist between a series of substitutions.
For example, if A substitutes from B, B from C, and C from A, then Deckhand
will raise an exception as it is impossible to determine the source data to use
for substitution in the presence of a dependency cycle.

Substitution works like this:

The source document is resolved via the ``src.schema`` and ``src.name``
keys and the ``src.path`` key is used relative to the source document's
``data`` section to retrieve the substitution data, which is then injected
into the ``data`` section of the destination document using the ``dest.path``
key.

If all the constraints above are correct, then the substitution source data
is injected into the destination document's ``data`` section, at the path
specified by ``dest.path``.

The injection of data into the destination document can be more fine-tuned
using a regular expression; see the :ref:`substitution-pattern` section
below for more information.

.. note::

  Substitution is only applied to the ``data`` section of a document. This is
  because a document's ``metadata`` and ``schema`` sections should be
  immutable within the scope of a revision, for obvious reasons.

Rendering Documents with Substitution
-------------------------------------

Concrete (non-abstract) documents can be used as a source of substitution
into other documents. This substitution is layer-independent, so given the 3
layer example above, which includes ``global``, ``region`` and ``site`` layers,
a document in the ``region`` layer could insert data from a document in the
``site`` layer.

Example
^^^^^^^

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

.. _substitution-pattern:

Substitution with Patterns
--------------------------

Substitution can be controlled in a more fine-tuned fashion using
``dest.pattern`` (optional) which functions as a regular expression underneath
the hood. The ``dest.pattern`` has the following constraints:

* ``dest.path`` key must already exist in the ``data`` section of the
  destination document and must have an associated value.
* The ``dest.pattern`` must be a valid regular expression string.
* The ``dest.pattern`` must be resolvable in the value of ``dest.path``.

If the above constraints are met, then more precise substitution via a pattern
can be carried out. If ``dest.path`` is a string or multiline string then all
occurrences of ``dest.pattern`` found in ``dest.path`` will be replaced. To handle
a more complex ``dest.path`` read `Recursive Replacement of Patterns`_.

Example
^^^^^^^

.. code-block:: yaml

  ---
  # Source document.
  schema: deckhand/Passphrase/v1
  metadata:
    name: example-password
    schema: metadata/Document/v1
    layeringDefinition:
      layer: site
    storagePolicy: cleartext
  data: my-secret-password
  ---
  # Another source document.
  schema: deckhand/Passphrase/v1
  metadata:
    name: another-password
    schema: metadata/Document/v1
    layeringDefinition:
      layer: site
    storagePolicy: cleartext
  data: another-secret-password
  ---
  # Destination document.
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    schema: metadata/Document/v1
    layeringDefinition:
      layer: region
    substitutions:
      - dest:
          path: .chart.values.some_url
          pattern: INSERT_[A-Z]+_HERE
        src:
          schema: deckhand/Passphrase/v1
          name: example-password
          path: .
      - dest:
          path: .chart.values.script
          pattern: INSERT_ANOTHER_PASSWORD
        src:
          schema: deckhand/Passphrase/v1
          name: another-password
          path: .
  data:
    chart:
      details:
        data: here
      values:
        some_url: http://admin:INSERT_PASSWORD_HERE@service-name:8080/v1
        script: |
         some_function("INSERT_ANOTHER_PASSWORD")
         another_function("INSERT_ANOTHER_PASSWORD")

After document rendering, the output for ``example-chart-01`` (the destination
document) will be:

.. code-block:: yaml

  ---
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    schema: metadata/Document/v1
    [...]
  data:
    chart:
      details:
        data: here
      values:
        # Notice string replacement occurs at exact location specified by
        # ``dest.pattern``.
        some_url: http://admin:my-secret-password@service-name:8080/v1
        script: |
         some_function("another-secret-password")
         another_function("another-secret-password")

Recursive Replacement of Patterns
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Patterns may also be replaced recursively. This can be achieved by specifying
a ``pattern`` value and ``recurse`` as ``True`` (it otherwise defaults to
``False``). Best practice is to limit the scope of the recursion as much as
possible: e.g. avoid passing in "$" as the ``jsonpath``, but rather a JSON path
that lives closer to the nested strings in question.

.. note::

  Recursive selection of patterns will only consider matching patterns.
  Non-matching patterns will be ignored. Thus, even if recursion can "pass
  over" non-matching patterns, they will be silently ignored.

.. code-block:: yaml

  ---
  # Source document.
  schema: deckhand/Passphrase/v1
  metadata:
    name: example-password
    schema: metadata/Document/v1
    layeringDefinition:
      layer: site
    storagePolicy: cleartext
  data: my-secret-password
  ---
  # Destination document.
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    schema: metadata/Document/v1
    layeringDefinition:
      layer: region
    substitutions:
      - dest:
          # Note that the path encapsulates all 3 entries that require pattern
          # replacement.
          path: .chart.values
          pattern: INSERT_[A-Z]+_HERE
          recurse:
            # Note that specifying the depth is mandatory. -1 means that all
            # layers are recursed through.
            depth: -1
        src:
          schema: deckhand/Passphrase/v1
          name: example-password
          path: .
  data:
    chart:
      details:
        data: here
      values:
        # Notice string replacement occurs for all paths recursively captured
        # by dest.path, since all their patterns match dest.pattern.
        admin_url: http://admin:INSERT_PASSWORD_HERE@service-name:35357/v1
        internal_url: http://internal:INSERT_PASSWORD_HERE@service-name:5000/v1
        public_url: http://public:INSERT_PASSWORD_HERE@service-name:5000/v1

After document rendering, the output for ``example-chart-01`` (the destination
document) will be:

.. code-block:: yaml

  ---
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    schema: metadata/Document/v1
    [...]
  data:
    chart:
      details:
        data: here
      values:
        # Notice how the data from the source document is injected into the
        # exact location specified by ``dest.pattern``.
        admin_url: http://admin:my-secret-password@service-name:35357/v1
        internal_url: http://internal:my-secret-passwor@service-name:5000/v1
        public_url: http://public:my-secret-passwor@service-name:5000/v1

Note that the recursion depth must be specified. -1 effectively ignores the
depth. Any other positive integer will specify how many levels deep to recurse
in order to optimize recursive pattern replacement. Take care to specify the
required recursion depth or else too-deep patterns won't be replaced.

Source Pattern Matching (Substring Extraction)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In some cases, only a substring of the substitution source is needed in the
destination document. For example, the source document may specify a full image
path, while the destination chart requires the repo and tag as separate fields.

This type of substitution can be accomplished with the optional parameters:
* ``src.pattern`` - a regular expression, with optional capture groups.
* ``src.match_group`` - the number of the desired capture group.

.. note::

  It is an error to specify ``src.pattern`` if the substitution source is not a
  string (e.g. an object or an array).

.. note::

  If the regex does not match, a warning is logged, and the entire source
  string is used.

.. note::

  The default ``src.match_group`` is 0 (i.e. the entire match). This allows the
  use of expressions like ``sha256:.*`` without parentheses, and without
  explicitly specifying a match group.

For example, given the following source documents, the distinct values for
``repo`` and ``tag`` will be extracted from the source image:

.. code-block:: yaml

  ---
  # Source document.
  schema: pegleg/SoftwareVersions/v1
  metadata:
    schema: metadata/Document/v1
    name: software-versions
    layeringDefinition:
      abstract: false
      layer: global
    storagePolicy: cleartext
  data:
    images:
      hello: docker.io/library/hello-world:latest
  ---
  # Destination document.
  schema: armada/Chart/v1
  metadata:
    name: example-chart-01
    schema: metadata/Document/v1
    layeringDefinition:
      abstract: false
      layer: global
    substitutions:
      - src:
          schema: pegleg/SoftwareVersions/v1
          name: software-versions
          path: .images.hello
          pattern: '^(.*):(.*)'
          match_group: 1
        dest:
          path: .values.images.hello.repo
      - src:
          schema: pegleg/SoftwareVersions/v1
          name: software-versions
          path: .images.hello
          pattern: '^(.*):(.*)'
          match_group: 2
        dest:
          path: .values.images.hello.tag
  data:
    values:
      images:
        hello:
          repo:  # docker.io/library/hello-world
          tag:   # latest

Substitution of Encrypted Data
------------------------------

Deckhand allows :ref:`data to be encrypted using Barbican <encryption>`.
Substitution of encrypted data works the same as substitution of cleartext
data.

Note that during the rendering process, source and destination documents
receive the secrets stored in Barbican.
