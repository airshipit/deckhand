# Deckhand Design

## Purpose

Deckhand is a document-based configuration storage service built with
auditability and validation in mind.

## Essential Functionality

* layering - helps reduce duplication in configuration while maintaining
  auditability across many sites
* substitution - provides separation between secret data and other
  configuration data, while allowing a simple interface for clients
* revision history - improves auditability and enables services to provide
  functional validation of a well-defined collection of documents that are
  meant to operate together
* validation - allows services to implement and register different kinds of
  validations and report errors

## Documents

All configuration data is stored entirely as structured documents, for which
schemas must be registered.

### Document Format

The document format is modeled loosely after Kubernetes practices. The top
level of each document is a dictionary with 3 keys: `schema`, `metadata`, and
`data`.

* `schema` - Defines the name of the JSON schema to be used for validation.
  Must have the form: `<namespace>/<kind>/<version>`, where the meaning of
  each component is:
  * `namespace` - Identifies the owner of this type of document. The
    values `deckhand` and `metadata` are reserved for internal use.
  * `kind` - Identifies a type of configuration resource in the namespace.
  * `version` - Describe the version of this resource, e.g. "v1".
* `metadata` - Defines details that Deckhand will inspect and understand. There
  are multiple schemas for this section as discussed below. All the various
  types of metadata include a `name` field which must be unique for each
  document `schema`.
* `data` - Data to be validated by the schema described by the `schema`
  field. Deckhand only interacts with content here as instructed to do so by
  the `metadata` section. The form of this section is considered to be
  completely owned by the `namespace` in the `schema`.

#### Document Metadata

There are 2 supported kinds of document metadata. Documents with `Document`
metadata are the most common, and are used for normal configuration data.
Documents with `Control` metadata are used to customize the behavior of
Deckhand.

##### schema: metadata/Document/v1

This type of metadata allows the following metadata hierarchy:

* `name` - string, required - Unique within a revision for a given `schema`.
* `storagePolicy` - string, required - Either `cleartext` or `encrypted`. If
  `encyrpted` is specified, then the `data` section of the document will be
  stored in an secure backend (likely via OpenStack Barbican). `metadata` and
  `schema` fields are always stored in cleartext.
* `layeringDefinition` - dict, required - Specifies layering details. See the
  Layering section below for details.
  * `abstract` - boolean, required - An abstract document is not expected to
    pass schema validation after layering and substitution are applied.
    Non-abstract (concrete) documents are.
  * `layer` - string, required - References a layer in the `LayeringPolicy`
    control document.
  * `parentSelector` - labels, optional - Used to construct document chains for
    executing merges.
  * `actions` - list, optional - A sequence of actions to apply this documents
    data during the merge process.
    * `method` - string, required - How to layer this content.
    * `path` - string, required - What content in this document to layer onto
      parent content.
* `substitutions` - list, optional - A sequence of substitutions to apply. See
  the Substitutions section for additional details.
  * `dest` - dict, required - A description of the inserted content destination.
    * `path` - string, required - The JSON path where the data will be placed
      into the `data` section of this document.
    * `pattern` - string, optional - A regex to search for in the string
      specified at `path` in this document and replace with the source data.
  * `src` - dict, required - A description of the inserted content source.
    * `schema` - string, required - The `schema` of the source document.
    * `name` - string, required - The `metadata.name` of the source document.
    * `path` - string, required - The JSON path from which to extract data in
      the source document relative to its `data` section.

Here is a fictitious example of a complete document which illustrates all the
valid fields in the `metadata` section.

```yaml
---
schema: some-service/ResourceType/v1
metadata:
  schema: metadata/Document/v1
  name: unique-name-given-schema
  storagePolicy: cleartext
  labels:
    genesis: enabled
    master: enabled
  layeringDefinition:
    abstract: true
    layer: region
    parentSelector:
      required_key_a: required_label_a
      required_key_b: required_label_b
    actions:
      - method: merge
        path: .path.to.merge.into.parent
      - method: delete
        path: .path.to.delete
  substitutions:
    - dest:
        path: .substitution.target
      src:
        schema: another-service/SourceType/v1
        name: name-of-source-document
        path: .source.path
data:
  path:
    to:
      merge:
        into:
          parent:
            foo: bar
          ignored:  # Will not be part of the resultant document after layering.
            data: here
  substitution:
    target: null  # Paths do not need to exist to be specified as substitution destinations.
...
```

##### schema: metadata/Control/v1

This schema is the same as the `Document` schema, except it omits the
`storagePolicy`, `layeringDefinition`, and `substitutions` keys, as these
actions are not supported on `Control` documents.

The complete list of valid `Control` document kinds is specified below along
with descriptions of each document kind.

### Layering

Layering provides a restricted data inheritance model intended to help reduce
duplication in configuration. Documents with different `schema`s are never
layered together (see the Substitution section if you need to combine data
from multiple types of documents).

Layering is controlled in two places:

1. The `LayeringPolicy` control document (described below), which defines the
   valid layers and their order of precedence.
2. In the `metadata.layeringDefinition` section of normal
   (`metadata.schema=metadata/Document/v1`) documents.

When rendering a particular document, you resolve the chain of parents upward
through the layers, and begin working back down each layer rendering at each
document in the chain.

When rendering each layer, the parent document is used as the starting point,
so the entire contents of the parent are brought forward.  Then the list of
`actions` will be applied in order.  Supported actions are:

* `merge` - "deep" merge child data at the specified path into the existing data
* `replace` - overwrite existing data with child data at the specified path
* `delete` - remove the existing data at the specified path

After actions are applied for a given layer, substitutions are applied (see
the Substitution section for details).

Selection of document parents is controlled by the `parentSelector` field and
works as follows. A given document, `C`, that specifies a `parentSelector`
will have exactly one parent, `P`. Document `P` will be the highest
precedence (i.e. part of the lowest layer defined in the `layerOrder` list
from the `LayeringPolicy`) document that has the labels indicated by the
`parentSelector` (and possibly additional labels) from the set of all
documents of the same `schema` as `C` that are in layers above the layer `C`
is in. For example, consider the following sample documents:

```yaml
---
schema: deckhand/LayeringPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: layering-policy
data:
  layerOrder:
    - global
    - region
    - site
---
schema: example/Kind/v1
metadata:
  schema: metadata/Document/v1
  name: global-1234
  labels:
    key1: value1
  layeringDefinition:
    abstract: true
    layer: global
data:
  a:
    x: 1
    y: 2
---
schema: example/Kind/v1
metadata:
  schema: metadata/Document/v1
  name: region-1234
  labels:
    key1: value1
  layeringDefinition:
    abstract: true
    layer: region
    parentSelector:
      key1: value1
    actions:
      - method: replace
        path: .a
data:
  a:
    z: 3
---
schema: example/Kind/v1
metadata:
  schema: metadata/Document/v1
  name: site-1234
  layeringDefinition:
    layer: site
    parentSelector:
      key1: value1
    actions:
      - method: merge
        path: .
data:
  b: 4
...
```

When rendering, the parent chosen for `site-1234` will be `region-1234`,
since it is the highest precedence document that matches the label selector
defined by `parentSelector`, and the parent chosen for `region-1234` will be
`global-1234` for the same reason. The rendered result for `site-1234` would
be:

```yaml
---
schema: example/Kind/v1
metadata:
  name: site-1234
data:
  a:
    z: 3
  b: 4
...
```

If `region-1234` were later removed, then the parent chosen for `site-1234`
would become `global-1234`, and the rendered result would become:

```yaml
---
schema: example/Kind/v1
metadata:
  name: site-1234
data:
  a:
    x: 1
    y: 2
  b: 4
...
```

<!-- TODO: Add figures for this example, with region present, have site point
with dotted line at global and indicate in caption (or something) that it's
selected for but ignored, because there's a higher-precedence layer to select
-->

### Substitution

Substitution is primarily designed as a mechanism for inserting secrets into
configuration documents, but works for unencrypted source documents as well.
Substitution is applied at each layer after all merge actions occur.

Concrete (non-abstract) documents can be used as a source of substitution
into other documents. This substitution is layer-independent, so given the 3
layer example above, which includes `global`, `region` and `site` layers, a
document in the `region` layer could insert data from a document in the
`site` layer.

Here is a sample set of documents demonstrating subistution:

```yaml
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
```

The rendered document will look like:

```yaml
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
```

### Control Documents

Control documents (documents which have `metadata.schema=metadata/Control/v1`),
are special, and are used to control the behavior of Deckhand at runtime.  Only
the following types of control documents are allowed.

#### DataSchema

`DataSchema` documents are used by various services to register new schemas
that Deckhand can use for validation. No `DataSchema` documents with names
beginning with `deckhand/` or `metadata/` are allowed.  Tme `metadata.name`
field of each `DataSchema` document specifies the top level `schema` that it
is used to validate.

The contents of its `data` key are expected to be the json schema definition
for the target document type from the target's top level `data` key down.

<!-- TODO: give valid, tiny schema as example -->

```yaml
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
```

#### LayeringPolicy

Only one `LayeringPolicy` document can exist within the system at any time.
It is an error to attempt to insert a new `LayeringPolicy` document if it has
a different `metadata.name` than the existing document. If the names match,
it is treated as an update to the existing document.

This document defines the strict order in which documents are merged together
from their component parts. It should result in a validation error if a
document refers to a layer not specified in the `LayeringPolicy`.

```yaml
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
```

#### ValidationPolicy

Unlike `LayeringPolicy`, many `ValidationPolicy` documents are allowed. This
allows services to check whether a particular revision (described below) of
documents meets a configurable set of validations without having to know up
front the complete list of validations.

Each validation `name` specified here is a reference to data that is postable
by other services. Names beginning with `deckhand` are reserved for internal
use. See the Validation section below for more details.

Since validations may indicate interactions with external and changing
circumstances, an optional `expiresAfter` key may be specified for each
validation as an ISO8601 duration. If no `expiresAfter` is specified, a
successful validation does not expire. Note that expirations are specific to
the combination of `ValidationPolicy` and validation, not to each validation
by itself.

```yaml
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
```

### Provided Utility Document Kinds

These are documents that use the `Document` metadata schema, but live in the
`deckhand` namespace.

#### Certificate

```yaml
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
```

#### CertificateKey

```yaml
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
```

#### Passphrase

```yaml
---
schema: deckhand/Passphrase/v1
metadata:
  schema: metadata/Document/v1
  name: application-admin-password
  storagePolicy: encrypted
data: some-password
...
```

## Buckets

Collections of documents, called buckets, are managed together.  All documents
belong to a bucket and all documents that are part of a bucket must be fully
specified together.

To create or update a new document in, e.g. bucket `mop`, one must PUT the
entire set of documents already in `mop` along with the new or modified
document.  Any documents not included in that PUT will be automatically
deleted in the created revision.

This feature allows the separation of concerns when delivering different
categories of documents, while making the delivered payload more declarative.

## Revision History

Documents will be ingested in batches which will be given a revision index.
This provides a common language for describing complex validations on sets of
documents.

Revisions can be thought of as commits in a linear git history, thus looking
at a revision includes all content from previous revisions.

## Validation

The validation system provides a unified approach to complex validations that
require coordination of multiple documents and business logic that resides in
consumer services.

Services can report success or failure of named validations for a given
revision. Those validations can then be referenced by many `ValidationPolicy`
control documents. The intended purpose use is to allow a simple mapping that
enables consuming services to be able to quickly check whether the
configuration in Deckhand is in a valid state for performing a specific
action.

### Deckhand-Provided Validations

In addition to allowing 3rd party services to report configurable validation
statuses, Deckhand provides a few internal validations which are made
available immediately upon document ingestion.

Here is a list of internal validations:

* `deckhand-document-schema-validation` - All concrete documents in the
  revision successfully pass their JSON schema validations. Will cause
  this to report an error.
* `deckhand-policy-validation` - All required policy documents are in-place,
  and existing documents conform to those policies.  E.g. if a 3rd party
  document specifies a `layer` that is not present in the layering policy,
  that will cause this validation to report an error.

## Access Control

Deckhand will use standard OpenStack Role Based Access Control using the
following actions:

- `purge_database` - Remove all documents and revisions from the database.
- `read_cleartext_document` - Read unencrypted documents.
- `read_encrypted_document` - Read (including substitution and layering)
  encrypted documents.
- `read_revision` - Read details about revisions.
- `read_validation` - Read validation policy status, and validation results,
  including error messages.
- `write_cleartext_document` - Create, update or delete unencrypted documents.
- `write_encrypted_document` - Create, update or delete encrypted documents.
- `write_validation` - Write validation results.

## API

This API will only support YAML as a serialization format. Since the IETF
does not provide an official media type for YAML, this API will use
`application/x-yaml`.

This is a description of the `v1.0` API. Documented paths are considered
relative to `/api/v1.0`.

### PUT `/bucket/{bucket_name}/documents`

Accepts a multi-document YAML body and creates a new revision that updates the
contents of the `bucket_name` bucket.  Documents from the specified bucket that
exist in previous revisions, but are absent from the request are removed from
that revision (though still accessible via older revisions).

Documents in other buckets are not changed and will be included in queries for
documents of the newly created revision.

Updates are detected based on exact match to an existing document of `schema` +
`metadata.name`.  It is an error that responds with `409 Conflict` to attempt
to PUT a document with the same `schema` + `metadata.name` as an existing
document from a different bucket in the most-recent revision.

This endpoint is the only way to add, update, and delete documents. This
triggers Deckhand's internal schema validations for all documents.

If no changes are detected, a new revision should not be created. This allows
services to periodically re-register their schemas without creating
unnecessary revisions.

This endpoint uses the `write_cleartext_document` and
`write_encrypted_document` actions.

### GET `/revisions/{revision_id}/documents`

Returns a multi-document YAML response containing all the documents matching
the filters specified via query string parameters. Returned documents will be
as originally added with no substitutions or layering applied.

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
* `sort` - string, optional, repeatable - Defines the sort order for returning
  results.  Default is `metadata.name`.  Repeating this parameter indicates use
  of multi-column sort with the most significant sorting column applied first.
* `status.bucket` - string, optional, repeatable - Used to select documents
  only from a particular bucket.  Repeating this parameter indicates documents
  from any of the specified buckets should be returned.

This endpoint uses the `read_cleartext_document` and
`read_encrypted_document` actions.

### GET `/revisions/{revision_id}/rendered-documents`

Returns a multi-document YAML of fully layered and substituted documents. No
abstract documents will be returned. This is the primary endpoint that
consumers will interact with for their configuration.

Valid query parameters are the same as for
`/revisions/{revision_id}/documents`, minus the paremters in
`metadata.layeringDetinition`, which are not supported.

This endpoint uses the `read_cleartext_document` and
`read_encrypted_document` actions.

### GET `/revisions`

Lists existing revisions and reports basic details including a summary of
validation status for each `deckhand/ValidationPolicy` that is part of that
revision.

Sample response:

```yaml
---
count: 7
next: https://deckhand/api/v1.0/revisions?limit=2&offset=2
prev: null
results:
  - id: 0
    url: https://deckhand/api/v1.0/revisions/0
    createdAt: 2017-07-14T21:23Z
    validationPolicies:
      site-deploy-validation:
        status: failed
  - id: 1
    url: https://deckhand/api/v1.0/revisions/1
    createdAt: 2017-07-16T01:15Z
    validationPolicies:
      site-deploy-validation:
        status: succeeded
...
```

This endpoint uses the `read_revision` action.

### DELETE `/revisions`

Permanently delete all documents.  This removes all revisions and resets the
data store.

This endpoint uses the `purge_database` action.

### GET `/revisions/{{revision_id}}`

Get a detailed description of a particular revision. The status of each
`ValidationPolicy` belonging to the revision is also included. Valid values
for the status of each validation policy are:

* `succeded` - All validations associated with the policy are `success`.
* `failed` - Any validation associated with the policy has status `failed`,
  `expired` or `missing`.

Sample response:

```yaml
---
id: 0
url: https://deckhand/api/v1.0/revisions/0
createdAt: 2017-07-14T021:23Z
validationPolicies:
  site-deploy-validation:
    url: https://deckhand/api/v1.0/revisions/0/documents?schema=deckhand/ValidationPolicy/v1&name=site-deploy-validation
    status: failed
    validations:
      - name: deckhand-schema-validation
        url: https://deckhand/api/v1.0/revisions/0/validations/deckhand-schema-validation/0
        status: success
      - name: drydock-site-validation
        status: missing
      - name: promenade-site-validation
        url: https://deckhand/api/v1.0/revisions/0/validations/promenade-site-validation/0
        status: expired
      - name: armada-deployability-validation
        url: https://deckhand/api/v1.0/revisions/0/validations/armada-deployability-validation/0
        status: failed
...
```

Validation status is always for the most recent entry for a given validation.
A status of `missing` indicates that no entries have been created. A status
of `expired` indicates that the validation had succeeded, but the
`expiresAfter` limit specified in the `ValidationPolicy` has been exceeded.

This endpoint uses the `read_revision` action.

### GET `/revisions/{{revision_id}}/diff/{{comparison_revision_id}}`

This endpoint provides a basic comparison of revisions in terms of how the
buckets involved have changed.  Only buckets with existing documents in either
of the two revisions in question will be reported; buckets with documents that
are only present in revisions between the two being compared are omitted from
this report.

The response will contain a status of `created`, `deleted`, `modified`, or
`unmodified` for each bucket.

The ordering of the two revision ids is not important.

For the purposes of diffing, the `revision_id` "0" is treated as a revision
with no documents, so queries comparing revision "0" to any other revision will
report "created" for each bucket in the compared revision.

Diffing a revision against itself will respond with the each of the buckets in
the revision as `unmodified`.

Diffing revision "0" against itself results in an empty dictionary as the response.

#### Examples
A response for a typical case, `GET /api/v1.0/revisions/6/diff/3` (or
equivalently `GET /api/v1.0/revisions/3/diff/6`).

```yaml
---
bucket_a: created
bucket_b: deleted
bucket_c: modified
bucket_d: unmodified
...
```

A response for diffing against an empty revision, `GET /api/v1.0/revisions/0/diff/6`:

```yaml
---
bucket_a: created
bucket_c: created
bucket_d: created
...
```

A response for diffing a revision against itself, `GET /api/v1.0/revisions/6/diff/6`:

```yaml
---
bucket_a: unmodified
bucket_c: unmodified
bucket_d: unmodified
...
```

Diffing two revisions that contain the same documents, `GET /api/v1.0/revisions/8/diff/11`:

```yaml
---
bucket_e: unmodified
bucket_f: unmodified
bucket_d: unmodified
...
```

Diffing revision zero with itself, `GET /api/v1.0/revisions/0/diff/0`:

```yaml
---
{}
...
```

### POST `/revisions/{{revision_id}}/validations/{{name}}`

Add the results of a validation for a particular revision.

An example `POST` request body indicating validation success:

```yaml
---
status: succeeded
validator:
  name: promenade
  version: 1.1.2
...
```

An example `POST` request indicating validation failure:

```http
POST /api/v1.0/revisions/3/validations/promenade-site-validation
Content-Type: application/x-yaml

---
status: failed
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
...
```

This endpoint uses the `write_validation` action.

### GET `/revisions/{{revision_id}}/validations`

Gets the list of validations which have been reported for this revision.

Sample response:

```yaml
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
...
```

This endpoint uses the `read_validation` action.

### GET `/revisions/{{revision_id}}/validations/{{name}}`

Gets the list of validation entry summaries that have been posted.

Sample response:

```yaml
---
count: 1
next: null
prev: null
results:
  - id: 0
    url: https://deckhand/api/v1.0/revisions/4/validations/promenade-site-validation/0/entries/0
    status: failure
...
```

This endpoint uses the `read_validation` action.

### GET `/revisions/{{revision_id}}/validations/{{name}}/entries/{{entry_id}}`

Gets the full details of a particular validation entry, including all posted
error details.

Sample response:

```yaml
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
...
```

This endpoint uses the `read_validation` action.

### POST `/revisions/{{revision_id}}/tags/{{tag}}`

Associate the revision with a collection of metadata, if provided, by way of
a tag. The tag itself can be used to label the revision.

Sample request with body:

```http
POST `/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar`
Content-Type: application/x-yaml

---
metadata:
  - name: foo
    thing: bar
...
```

Sample response:

```http
Content-Type: application/x-yaml
HTTP/1.1 201 Created
Location: https://deckhand/api/v1.0/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar

---
tag: foobar
metadata:
  - name: foo
    thing: bar
...
```

Sample request without body:

```http
POST `/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar`
Content-Type: application/x-yaml
```

Sample response:


```http
Content-Type: application/x-yaml
HTTP/1.1 201 Created
Location: https://deckhand/api/v1.0/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foobar

---
tag: foobar
...
```

This endpoint uses the `write_tag` action.

### GET `/revisions/{{revision_id}}/tags`

List the tags associated with a revision.

Sample request with body:

```http
GET `/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags`
```

Sample response:

```http
Content-Type: application/x-yaml
HTTP/1.1 200 OK

---
- metadata:
  name: foo
  thing: bar
- metadata:
  name: baz
  thing: qux
...
```

This endpoint uses the `read_tag` action.

### GET `/revisions/{{revision_id}}/tags/{{tag}}`

Show tag details for tag associated with a revision.

Sample request with body:

```http
GET `/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foo`
```

Sample response:

```http
Content-Type: application/x-yaml
HTTP/1.1 200 OK

---
metadata:
  - name: foo
    thing: bar
...
```

This endpoint uses the `read_tag` action.

### DELETE `/revisions/{{revision_id}}/tags/{{tag}}`

Delete tag associated with a revision.

Sample request with body:

```http
GET `/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags/foo`
```

Sample response:

```http
Content-Type: application/x-yaml
HTTP/1.1 204 No Content
```

This endpoint uses the `delete_tag` action.

### DELETE `/revisions/{{revision_id}}/tags`

Delete all tags associated with a revision.

Sample request with body:

```http
GET `/revisions/0615b731-7f3e-478d-8ba8-a223eab4757e/tags`
```

Sample response:

```http
Content-Type: application/x-yaml
HTTP/1.1 204 No Content
```

This endpoint uses the `delete_tag` action.

### POST `/rollback/{target_revision_id}`

Creates a new revision that contains exactly the same set of documents as the
revision specified by `target_revision_id`.

This endpoint uses the `write_cleartext_document` and
`write_encrypted_document` actions.
