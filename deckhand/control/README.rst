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


Testing
-------

Document creation can be tested locally using (from root deckhand directory):

.. code-block:: console

    $ curl -i -X POST localhost:9000/api/v1.0/documents \
         -H "Content-Type: application/x-yaml" \
         --data-binary "@deckhand/tests/unit/resources/sample.yaml"

    # revision_id copy/pasted from previous response.
    $ curl -i -X GET localhost:9000/api/v1.0/revisions/0e99c8b9-bab4-4fc7-8405-7dbd22c33a30/documents
