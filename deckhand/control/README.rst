Control
=======

This is the external-facing API service to operate on and query
Deckhand-managed data.

v1.0 Endpoints
--------------

POST `/documents`
~~~~~~~~~~~~~~~~~

Accepts a multi-document YAML body and creates a new revision which adds
those documents. Updates are detected based on exact match to an existing
document of `schema` + `metadata.name`. Documents are "deleted" by including
documents with the tombstone metadata schema, such as:

```yaml
---
schema: any-namespace/AnyKind/v1
metadata:
  schema: metadata/Tombstone/v1
  name: name-to-delete
...
```

This endpoint is the only way to add, update, and delete documents. This
triggers Deckhand's internal schema validations for all documents.

If no changes are detected, a new revision should not be created. This allows
services to periodically re-register their schemas without creating
unnecessary revisions.

Sample response:

```yaml
---
created_at: '2017-07-31T14:46:46.119853'
data:
  path:
    to:
      merge:
        into:
          ignored: {data: here}
          parent: {foo: bar}
  substitution: {target: null}
deleted: false
deleted_at: null
id: f99630d9-a89c-4aad-9aaa-7c44462047c1
metadata:
  labels: {genesis: enabled, master: enabled}
  layeringDefinition:
    abstract: false
    actions:
    - {method: merge, path: .path.to.merge.into.parent}
    - {method: delete, path: .path.to.delete}
    layer: region
    parentSelector: {required_key_a: required_label_a, required_key_b: required_label_b}
  name: unique-name-given-schema
  schema: metadata/Document/v1
  storagePolicy: cleartext
  substitutions:
  - dest: {path: .substitution.target}
    src: {name: name-of-source-document, path: .source.path, schema: another-service/SourceType/v1}
name: unique-name-given-schema
revision_id: 0206088a-c9e9-48e1-8725-c9bdac15d6b7
schema: some-service/ResourceType/v1
updated_at: '2017-07-31T14:46:46.119858'
```

GET `/revisions`
~~~~~~~~~~~~~~~~

Lists existing revisions and reports basic details including a summary of
validation status for each `deckhand/ValidationPolicy` that is part of that
revision.

Sample response:

```yaml
---
child_id: null
count: 2
created_at: '2017-07-31T14:36:00.348967'
deleted: false
deleted_at: null
id: d3428d6a-d8c4-4a5b-8006-aba974cc36a2
parent_id: null
results: []
updated_at: '2017-07-31T14:36:00.348973'
```

GET `/revisions/{revision_id}/documents`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns a multi-document YAML response containing all the documents matching
the filters specified via query string parameters. Returned documents will be
as originally posted with no substitutions or layering applied.

Supported query string parameters:

* `schema` - string, optional - The top-level `schema` field to select. This
  may be partially specified by section, e.g., `schema=promenade` would select all
  `kind` and `version` schemas owned by promenade, or `schema=promenade/Node`
  which would select all versions of `promenade/Node` documents. One may not
  partially specify the namespace or kind, so `schema=promenade/No` would not
  select `promenade/Node/v1` documents, and `schema=prom` would not select
  `promenade` documents.
* `metadata.name` - string, optional
* `metadata.layeringDefinition.abstract` - string, optional - Valid values are
  the "true" and "false".
* `metadata.layeringDefinition.layer` - string, optional - Only return documents from
  the specified layer.
* `metadata.label` - string, optional, repeatable - Uses the format
  `metadata.label=key=value`. Repeating this parameter indicates all
  requested labels must apply (AND not OR).

Sample response:

```yaml
created_at: '2017-07-31T14:36:00.352701'
data: {foo: bar}
deleted: false
deleted_at: null
id: ffba233a-326b-4eed-9b21-079ebd2a53f0
metadata:
  labels: {genesis: enabled, master: enabled}
  layeringDefinition:
    abstract: false
    actions:
    - {method: merge, path: .path.to.merge.into.parent}
    - {method: delete, path: .path.to.delete}
    layer: region
    parentSelector: {required_key_a: required_label_a, required_key_b: required_label_b}
  name: foo-name-given-schema
  schema: metadata/Document/v1
  storagePolicy: cleartext
  substitutions:
  - dest: {path: .substitution.target}
    src: {name: name-of-source-document, path: .source.path, schema: another-service/SourceType/v1}
name: foo-name-given-schema
revision_id: d3428d6a-d8c4-4a5b-8006-aba974cc36a2
schema: some-service/ResourceType/v1
updated_at: '2017-07-31T14:36:00.352705'
```

Testing
-------

Document creation can be tested locally using (from root deckhand directory):

.. code-block:: console

    $ curl -i -X POST localhost:9000/api/v1.0/documents \
         -H "Content-Type: application/x-yaml" \
         --data-binary "@deckhand/tests/unit/resources/sample.yaml"

    # revision_id copy/pasted from previous response.
    $ curl -i -X GET localhost:9000/api/v1.0/revisions/0e99c8b9-bab4-4fc7-8405-7dbd22c33a30/documents
