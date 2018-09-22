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

.. _api-ref:

Deckhand API Documentation
==========================

API
---

This API will only support YAML as a serialization format. Since the IETF
does not provide an official media type for YAML, this API will use
``application/x-yaml``.

This is a description of the ``v1.0`` API. Documented paths are considered
relative to ``/api/v1.0``.

PUT ``/buckets/{bucket_name}/documents``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Accepts a multi-document YAML body and creates a new revision that updates the
contents of the ``bucket_name`` bucket.  Documents from the specified bucket that
exist in previous revisions, but are absent from the request are removed from
that revision (though still accessible via older revisions).

Documents in other buckets are not changed and will be included in queries for
documents of the newly created revision.

Updates are detected based on exact match to an existing document of ``schema`` +
``metadata.name``.  It is an error that responds with ``409 Conflict`` to attempt
to PUT a document with the same ``schema`` + ``metadata.name`` as an existing
document from a different bucket in the most-recent revision.

This endpoint is the only way to add, update, and delete documents. This
triggers Deckhand's internal schema validations for all documents.

If no changes are detected, a new revision should not be created. This allows
services to periodically re-register their schemas without creating
unnecessary revisions.

GET ``/revisions/{revision_id}/documents``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Returns a multi-document YAML response containing all the documents matching
the filters specified via query string parameters. Returned documents will be
as originally added with no substitutions or layering applied.

Supported query string parameters:

* ``schema`` - string, optional - The top-level ``schema`` field to select. This
  may be partially specified by section, e.g., ``schema=promenade`` would select all
  ``kind`` and ``version`` schemas owned by promenade, or ``schema=promenade/Node``
  which would select all versions of ``promenade/Node`` documents. One may not
  partially specify the namespace or kind, so ``schema=promenade/No`` would not
  select ``promenade/Node/v1`` documents, and ``schema=prom`` would not select
  ``promenade`` documents.
* ``metadata.name`` - string, optional
* ``metadata.layeringDefinition.abstract`` - string, optional - Valid values are
  the "true" and "false".
* ``metadata.layeringDefinition.layer`` - string, optional - Only return
  documents from the specified layer.
* ``metadata.label`` - string, optional, repeatable - Uses the format
  ``metadata.label=key=value``. Repeating this parameter indicates all
  requested labels must apply (AND not OR).
* ``status.bucket`` - string, optional, repeatable - Used to select documents
  only from a particular bucket.  Repeating this parameter indicates documents
  from any of the specified buckets should be returned.
* ``sort`` - string, optional, repeatable - Defines the sort order for returning
  results.  Default is by creation date.  Repeating this parameter indicates use
  of multi-column sort with the most significant sorting column applied first.
* ``order`` - string, optional - Valid values are "asc" and "desc". Default is
  "asc". Controls the order in which the ``sort`` result is returned: "asc"
  returns sorted results in ascending order, while "desc" returns results in
  descending order.
* ``limit`` - int, optional - Controls number of documents returned by this
   endpoint.

GET ``/revisions/{revision_id}/rendered-documents``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Returns a multi-document YAML of fully layered and substituted documents. No
abstract documents will be returned. This is the primary endpoint that
consumers will interact with for their configuration.

Valid query parameters are the same as for
``/revisions/{revision_id}/documents``, minus the parameters in
``metadata.layeringDefinition``, which are not supported.

Raises a ``409 Conflict`` if a ``layeringPolicy`` document could not be found.

Raises a ``500 Internal Server Error`` if rendered documents fail schema
validation.

GET ``/revisions``
^^^^^^^^^^^^^^^^^^

Lists existing revisions and reports basic details including a summary of
validation status for each ``deckhand/ValidationPolicy`` that is part of that
revision.

Supported query string parameters:

* ``tag`` - string, optional, repeatable - Used to select revisions that have
  been tagged with particular tags.
* ``sort`` - string, optional, repeatable - Defines the sort order for returning
  results.  Default is by creation date.  Repeating this parameter indicates use
  of multi-column sort with the most significant sorting column applied first.
* ``order`` - string, optional - Valid values are "asc" and "desc". Default is
  "asc". Controls the order in which the ``sort`` result is returned: "asc"
  returns sorted results in ascending order, while "desc" returns results in
  descending order.

Sample response:

.. code-block:: yaml

  ---
  count: 7
  next: https://deckhand/api/v1.0/revisions?limit=2&offset=2
  prev: null
  results:
    - id: 1
      url: https://deckhand/api/v1.0/revisions/1
      createdAt: 2017-07-14T21:23Z
      buckets: [mop]
      tags:
        a: {}
      validationPolicies:
        site-deploy-validation:
          status: failure
    - id: 2
      url: https://deckhand/api/v1.0/revisions/2
      createdAt: 2017-07-16T01:15Z
      buckets: [flop, mop]
      tags:
        b:
          random: stuff
          foo: bar
      validationPolicies:
        site-deploy-validation:
          status: success

DELETE ``/revisions``
^^^^^^^^^^^^^^^^^^^^^

Permanently delete all documents.

.. warning::

  This removes all revisions and resets the data store.

GET ``/revisions/{{revision_id}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Get a detailed description of a particular revision. The status of each
``ValidationPolicy`` belonging to the revision is also included. Valid values
for the status of each validation policy are:

* ``success`` - All validations associated with the policy are ``success``.
* ``failure`` - Any validation associated with the policy has status ``failure``,
  ``expired`` or ``missing``.

Sample response:

.. code-block:: yaml

  ---
  id: 1
  url: https://deckhand/api/v1.0/revisions/1
  createdAt: 2017-07-14T021:23Z
  buckets: [mop]
  tags:
    a:
      random: stuff
      url: https://deckhand/api/v1.0/revisions/1/tags/a
  validationPolicies:
    site-deploy-validation:
      url: https://deckhand/api/v1.0/revisions/1/documents?schema=deckhand/ValidationPolicy/v1&name=site-deploy-validation
      status: failure
      validations:
        - name: deckhand-schema-validation
          url: https://deckhand/api/v1.0/revisions/1/validations/deckhand-schema-validation/entries/0
          status: success
        - name: drydock-site-validation
          status: missing
        - name: promenade-site-validation
          url: https://deckhand/api/v1.0/revisions/1/validations/promenade-site-validation/entries/0
          status: expired
        - name: armada-deployability-validation
          url: https://deckhand/api/v1.0/revisions/1/validations/armada-deployability-validation/entries/0
          status: failure

Validation status is always for the most recent entry for a given validation.
A status of ``missing`` indicates that no entries have been created. A status
of ``expired`` indicates that the validation had succeeded, but the
``expiresAfter`` limit specified in the ``ValidationPolicy`` has been exceeded.

GET ``/revisions/{{revision_id}}/diff/{{comparison_revision_id}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This endpoint provides a basic comparison of revisions in terms of how the
buckets involved have changed.  Only buckets with existing documents in either
of the two revisions in question will be reported; buckets with documents that
are only present in revisions between the two being compared are omitted from
this report. That is, buckets with documents that were accidentally created
(and then deleted to rectify the mistake) that are not directly present in
the two revisions being compared are omitted.

The response will contain a status of ``created``, ``deleted``, ``modified``, or
``unmodified`` for each bucket.

The ordering of the two revision ids is not important.

For the purposes of diffing, the ``revision_id`` "0" is treated as a revision
with no documents, so queries comparing revision "0" to any other revision will
report "created" for each bucket in the compared revision.

Diffing a revision against itself will respond with the each of the buckets in
the revision as ``unmodified``.

Diffing revision "0" against itself results in an empty dictionary as the response.

Examples
""""""""

A response for a typical case, ``GET /api/v1.0/revisions/6/diff/3`` (or
equivalently ``GET /api/v1.0/revisions/3/diff/6``).

.. code-block:: yaml

  ---
  bucket_a: created
  bucket_b: deleted
  bucket_c: modified
  bucket_d: unmodified

A response for diffing against an empty revision, ``GET /api/v1.0/revisions/0/diff/6``:

.. code-block:: yaml

  ---
  bucket_a: created
  bucket_c: created
  bucket_d: created

A response for diffing a revision against itself, ``GET /api/v1.0/revisions/6/diff/6``:

.. code-block:: yaml

  ---
  bucket_a: unmodified
  bucket_c: unmodified
  bucket_d: unmodified

Diffing two revisions that contain the same documents, ``GET /api/v1.0/revisions/8/diff/11``:

.. code-block:: yaml

  ---
  bucket_e: unmodified
  bucket_f: unmodified
  bucket_d: unmodified

Diffing revision zero with itself, ``GET /api/v1.0/revisions/0/diff/0``:

.. code-block:: yaml

  ---
  {}

GET ``/revisions/{{revision_id}}/deepdiff/{{comparison_revision_id}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is an advanced version of ``diff`` api. It provides deepdiff between
two revisions of modified buckets.

The response will contain ``modified``, ``added``, ``deleted``
documents deepdiff details. Modified documents diff will consist of data
and metadata change details. In case the document storagePolicy is encrypted,
deepdiff will hide data and will return only ``{'encrypted': True}``.

Examples
""""""""

A response for a typical case, ``GET /api/v1.0/revisions/3/deepdiff/4``

.. code-block:: yaml

  ---
  bucket_a: created
  bucket_b: deleted
  bucket_c: modified
  bucket_c diff:
    document_changed:
      count: 1
      details:
        ('example/Kind/v1', 'doc-b'):
          data_changed:
            values_changed:
              root['foo']: {new_value: 3, old_value: 2}
          metadata_changed: {}

Document added deepdiff response, ``GET /api/v1.0/revisions/4/deepdiff/5``

.. code-block:: yaml

  ---
  bucket_a: created
  bucket_c: modified
  bucket_c diff:
    document_added:
      count: 1
      details:
      - [example/Kind/v1, doc-c]

Document deleted deepdiff response, ``GET /api/v1.0/revisions/5/deepdiff/6``

.. code-block:: yaml

  ---
  bucket_a: created
  bucket_c: modified
  bucket_c diff:
    document_deleted:
      count: 1
      details:
      - [example/Kind/v1, doc-c]

A response for deepdiffing against an empty revision, ``GET /api/v1.0/revisions/0/deepdiff/2``:

.. code-block:: yaml

  ---
  bucket_a: created
  bucket_b: created

A response for deepdiffing a revision against itself, ``GET /api/v1.0/revisions/6/deepdiff/6``:

.. code-block:: yaml

  ---
  bucket_a: unmodified
  bucket_c: unmodified
  bucket_d: unmodified

DeepDiffing two revisions that contain the same documents, ``GET /api/v1.0/revisions/1/deepdiff/2``:

.. code-block:: yaml

  ---
  bucket_a: unmodified
  bucket_b: unmodified

DeepDiffing revision zero with itself, ``GET /api/v1.0/revisions/0/deepdiff/0``:

.. code-block:: yaml

  ---
  {}

POST ``/revisions/{{revision_id}}/validations/{{name}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Add the results of a validation for a particular revision.

An example ``POST`` request body indicating validation success:

.. code-block:: yaml

  ---
  status: success
  validator:
    name: promenade
    version: 1.1.2

An example ``POST`` request indicating validation failure:

::

  POST /api/v1.0/revisions/3/validations/promenade-site-validation
  Content-Type: application/x-yaml

  ---
  status: failure
  errors:
    - documents:
        - schema: promenade/Node/v1
          name: node-document-name
        - schema: promenade/Masters/v1
          name: kubernetes-masters
      message: Node has master role, but not included in cluster masters list.
  validator:
    name: promenade
    version: 1.1.2

GET ``/revisions/{{revision_id}}/validations``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Gets the list of validations which have been reported for this revision.

Sample response:

.. code-block:: yaml

  ---
  count: 2
  next: null
  prev: null
  results:
    - name: deckhand-schema-validation
      url: https://deckhand/api/v1.0/revisions/4/validations/deckhand-schema-validation
      status: success
    - name: promenade-site-validation
      url: https://deckhand/api/v1.0/revisions/4/validations/promenade-site-validation
      status: failure

GET ``/revisions/{{revision_id}}/validations/detail``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Gets the list of validations, with details, which have been reported for this
revision.

Sample response:

.. code-block:: yaml

  ---
  count: 1
  next: null
  prev: null
  results:
    - name: promenade-site-validation
      url: https://deckhand/api/v1.0/revisions/4/validations/promenade-site-validation/entries/0
      status: failure
      createdAt: 2017-07-16T02:03Z
      expiresAfter: null
      expiresAt: null
      errors:
        - documents:
            - schema: promenade/Node/v1
              name: node-document-name
            - schema: promenade/Masters/v1
              name: kubernetes-masters
          message: Node has master role, but not included in cluster masters list.

GET ``/revisions/{{revision_id}}/validations/{{name}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Gets the list of validation entry summaries that have been posted.

Sample response:

.. code-block:: yaml

  ---
  count: 1
  next: null
  prev: null
  results:
    - id: 0
      url: https://deckhand/api/v1.0/revisions/4/validations/promenade-site-validation/entries/0
      status: failure

GET ``/revisions/{{revision_id}}/validations/{{name}}/entries/{{entry_id}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Gets the full details of a particular validation entry, including all posted
error details.

Sample response:

.. code-block:: yaml

  ---
  name: promenade-site-validation
  url: https://deckhand/api/v1.0/revisions/4/validations/promenade-site-validation/entries/0
  status: failure
  createdAt: 2017-07-16T02:03Z
  expiresAfter: null
  expiresAt: null
  errors:
    - documents:
        - schema: promenade/Node/v1
          name: node-document-name
        - schema: promenade/Masters/v1
          name: kubernetes-masters
      message: Node has master role, but not included in cluster masters list.

POST ``/revisions/{{revision_id}}/tags/{{tag}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Associate the revision with a collection of metadata, if provided, by way of
a tag. The tag itself can be used to label the revision. If a tag by name
``tag`` already exists, the tag's associated metadata is updated.

Sample request with body:

::

  POST ``/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar``
  Content-Type: application/x-yaml

  ---
  thing: bar

Sample response:

::

  Content-Type: application/x-yaml
  HTTP/1.1 201 Created
  Location: https://deckhand/api/v1.0/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar

  ---
  tag: foobar
  data:
    thing: bar

Sample request without body:

::

  POST ``/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar``
  Content-Type: application/x-yaml

Sample response:

::

  Content-Type: application/x-yaml
  HTTP/1.1 201 Created
  Location: https://deckhand/api/v1.0/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar

  ---
  tag: foobar
  data: {}

GET ``/revisions/{{revision_id}}/tags``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

List the tags associated with a revision.

Sample request with body:

::

  GET ``/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags``

Sample response:

::

  Content-Type: application/x-yaml
  HTTP/1.1 200 OK

  ---
  - tag: foo
    data:
      thing: bar
  - tag: baz
    data:
      thing: qux

GET ``/revisions/{{revision_id}}/tags/{{tag}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Show tag details for tag associated with a revision.

Sample request with body:

::

  GET ``/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foo``

Sample response:

::

  Content-Type: application/x-yaml
  HTTP/1.1 200 OK

  ---
  tag: foo
  data:
    thing: bar

DELETE ``/revisions/{{revision_id}}/tags/{{tag}}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Delete tag associated with a revision.

Sample request with body:

::

  GET ``/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foo``

Sample response:

::

  Content-Type: application/x-yaml
  HTTP/1.1 204 No Content

DELETE ``/revisions/{{revision_id}}/tags``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Delete all tags associated with a revision.

Sample request with body:

::

  GET ``/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags``

Sample response:

::

  Content-Type: application/x-yaml
  HTTP/1.1 204 No Content

POST ``/rollback/{target_revision_id}``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a new revision that contains exactly the same set of documents as the
revision specified by ``target_revision_id``.
