# Deckhand Design

## Purpose

Deckhand is a document-based configuration storage service built with
auditability and validation in mind.

## Essential Functionality

* layering - helps reduce duplication in configuration while maintaining
  auditability across many sites
* substitution - provides separation between secret data and other
  configuration data, while allowing a simple, file-like interface for
  clients
  * These documents are designed to present consumer services with ready-to-use
    documents which may include secrets.
* revision history - improves auditability and enables services to provide
  functional validation of a well-defined collection of documents that are
  meant to operate together
* validation - allows services to implement and register different kinds of
  validations and report validation errors

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

There are 3 supported kinds of document metadata. Documents with `Document`
metadata are the most common, and are used for normal configuration data.
Documents with `Control` metadata are used to customize the behavior of
Deckhand. Documents with `Tombstone` metadata are used to delete pre-existing
documents with either `Document` or `Control` metadata.

##### schema: metadata/Document/v1

This type of metadata allows the following metadata hierarchy:

* `name` - string, required - Unique within a revision for a given `schema`.
* `storagePolicy` - string, required - Either `cleartext` or `encrypted`. If
  `encyrpted` is specified, then the `data` section of the document will be
  stored in an secure backend (likely via OpenStack Barbican). `metadata` and
  `schema` fields are always stored in cleartext.
* `layeringDefinition` - dict, required - Specifies
  * `abstract` - boolean, required - An abstract document is not expected to
    pass schema validation after layering and substitution are applied.
    Non-abstract (concrete) documents are.
  * `layer` - string, required - References a layer in the `LayeringPolicy`
    control document.
  * `parentSelector` - labels, optional - Used to construct document chains for
    executing merges.  See the Layering section below for details.
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

##### schema: metadata/Tombstone/v1

The only valid key in a `Tombstone` metadata section is `name`.  Additionally,
the top-level `data` section should be omitted.

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

When rendering each layer, the list of `actions` will be applied in order.
Supported actions are:

* `merge` - a "deep" merge that layers new and modified data onto existing data
* `replace` - overwrite data at the specified path and replace it with the data
  given in this document
* `delete` - remove the data at the specified path

After actions are applied for a given layer, substitutions are applied (see
the Substitution section for details).

Selection of document parents is controlled by the `parentSelector` field and
works as follows. A given document, `C`, that specifies a `parentSelector`
will have exactly one parent, `P`. Document `P` will be the highest
precedence (i.e. part of the lowest layer) document that has the labels
indicated by the `parentSelector` (and possibly additional labels) from the
set of all documents of the same `schema` as `C` that are in layers above the
layer `C` is in. For example, consider the following sample documents:

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

Concrete documents can be used as a source of substitution into other
documents. This substitution is layer-independent.

This is primarily designed as a mechanism for inserting secrets into
configuration documents, but works for unencrypted source documents as well.

<!-- TODO: Add example(s) maybe simple + an example with source layering? -->

### Control Documents

Control documents (documents which have `metadata.schema=metadata/Control/v1`),
are special, and are used to control the behavior of Deckhand at runtime.  Only
the following types of control documents are allowed.

#### DataSchema

`DataSchema` documents are used by various services to register new schemas
that Deckhand can use for validation. No `DataSchema` documents with names
beginning with `deckhand/` or `metadata/` are allowed.

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

Deckhand provides validation of all concrete documents given their schema
under the name `deckhand-schema-validation`. Since validations may indicate
interactions with external and changing circumstances, an optional
`expiresAfter` key may be specified for each validation as an ISO8601
duration. If no `expiresAfter` is specified, a successful validation does not
expire.

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

## Revision History

Documents will be ingested in batches which will be given a revision index.
This provides a common language for describing complex validations on sets of
documents.

Revisions can be thought of as commits in a linear git history, thus looking
at a revision includes all content from previous revisions.

## Validation

Services can report success for validation types for a given revision.

## API

This API will only support YAML as a serialization format. Since the IETF
does not provide an official media type for YAML, this API will use
`application/x-yaml`.

### POST `/documents`

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

### GET `/revisions/{revision_id}/documents`

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

### GET `/revisions/{revision_id}/rendered-documents`

Returns a multi-document YAML of fully layered and substituted documents. No
abstract documents will be returned. This is the primary endpoint that
consumers will interact with for their configuration.

Valid query parameters are the same as for
`/revisions/{revision_id}/documents`, minus the paremters in
`metadata.layeringDetinition`, which are not supported.

### GET `/revisions`

Lists existing revisions and reports basic details including a summary of
validation status for each `deckhand/ValidationPolicy` that is part of that
revision.

Sample response:

```yaml
---
count: 7
next: https://deckhand/revisions?limit=2&offset=2
prev: null
results:
  - id: 0
    url: https://deckhand/revisions/0
    createdAt: 2017-07-14T21:23Z
    validationPolicies:
      site-deploy-validation:
        status: failed
  - id: 1
    url: https://deckhand/revisions/1
    createdAt: 2017-07-16T01:15Z
    validationPolicies:
      site-deploy-validation:
        status: succeeded
...
```

### GET `/revisions/{{revision_id}}`

Get a detailed description of a particular revision.

Sample response:

```yaml
---
id: 0
url: https://deckhand/revisions/0
createdAt: 2017-07-14T021:23Z
validationPolicies:
  site-deploy-validation:
    url: https://deckhand/revisions/0/documents?schema=deckhand/ValidationPolicy/v1&name=site-deploy-validation
    status: failed
    validations:
      - name: deckhand-schema-validation
        url: https://deckhand/revisions/0/validations/deckhand-schema-validation/0
        status: success
      - name: drydock-site-validation
        status: missing
      - name: promenade-site-validation
        url: https://deckhand/revisions/0/validations/promenade-site-validation/0
        status: expired
      - name: armada-deployability-validation
        url: https://deckhand/revisions/0/validations/armada-deployability-validation/0
        status: failed
...
```

Validation status is always for the most recent entry for a given validation.
A status of `missing` indicates that no entries have been created. A status
of `expired` indicates that the validation had succeeded, but the
`expiresAfter` limit specified in the `ValidationPolicy` has been exceeded.

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
POST /revisions/3/validations/promenade-site-validation
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

### GET `/revisions/{{revision_id}}/validations`

Gets the list of validations which have reported for this revision.

Sample response:

```yaml
---
count: 2
next: null
prev: null
results:
  - name: deckhand-schema-validation
    url: https://deckhand/revisions/4/validations/deckhand-schema-validation
    status: success
  - name: promenade-site-validation
    url: https://deckhand/revisions/4/validations/promenade-site-validation
    status: failure
...
```

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
    url: https://deckhand/revisions/4/validations/promenade-site-validation/0/entries/0
    status: failure
...
```

### GET `/revisions/{{revision_id}}/validations/{{name}}/entries/{{entry_id}}`

Gets the full details of a particular validation entry, including all posted
error details.

Sample response:

```yaml
---
name: promenade-site-validation
url: https://deckhand/revisions/4/validations/promenade-site-validation/entries/0
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
