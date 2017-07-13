Control
=======

This is the external-facing API service to operate on and query
Deckhand-managed data.

v1.0 Endpoints
--------------

/api/v1.0/documents
~~~~~~~~~~~~~~~~~~~

POST - Create a new YAML document and return a revision number. If the YAML
document already exists, then the document will be replaced and a new
revision number will be returned.

