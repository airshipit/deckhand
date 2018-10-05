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

.. _api-client-library:

Deckhand API Client Library Documentation
=========================================

The recommended approach to instantiate the Deckhand client is via a Keystone
session:

::

    from keystoneauth1.identity import v3
    from keystoneauth1 import session

    keystone_auth = {
        'project_domain_name': PROJECT_DOMAIN_NAME,
        'project_name': PROJECT_NAME,
        'user_domain_name': USER_DOMAIN_NAME,
        'password': PASSWORD,
        'username': USERNAME,
        'auth_url': AUTH_URL,
    }
    auth = v3.Password(**keystone_auth)
    sess = session.Session(auth=auth)
    deckhandclient = client.Client(session=sess)

You can also instantiate the client via one of Keystone's supported ``auth``
plugins:

::

    from keystoneauth1.identity import v3

    keystone_auth = {
        'auth_url': AUTH_URL,
        'token': TOKEN,
        'project_id': PROJECT_ID,
        'project_domain_name': PROJECT_DOMAIN_NAME
    }
    auth = v3.Token(**keystone_auth)
    deckhandclient = client.Client(auth=auth)

Which will allow you to authenticate using a pre-existing, project-scoped
token.

Alternatively, you can use non-session authentication to instantiate the
client, though this approach has been `deprecated`_.

::

    from deckhand.client import client

    deckhandclient = client.Client(
        username=USERNAME,
        password=PASSWORD,
        project_name=PROECT_NAME,
        project_domain_name=PROJECT_DOMAIN_NAME,
        user_domain_name=USER_DOMAIN_NAME,
        auth_url=AUTH_URL)

.. _deprecated: https://docs.openstack.org/python-keystoneclient/latest/using-api-v3.html#non-session-authentication-deprecated

.. note::

    The Deckhand client by default expects that the service be registered
    under the Keystone service catalog as ``deckhand``. To provide a different
    value pass ``service_type=SERVICE_TYPE`` to the ``Client`` constructor.

After you have instantiated an instance of the Deckhand client, you can invoke
the client managers' functionality:

::

    # Generate a sample document.
    payload = """
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
    """

    # Create a bucket and associate it with the document.
    result = client.buckets.update('mop', payload)

    >>> result
    <Bucket name: mop>

    # Convert the response to a dictionary.
    >>> result.to_dict()
    {'status': {'bucket': 'mop', 'revision': 1},
     'schema': 'deckhand/Certificate/v1', 'data': {...} 'id': 1,
     'metadata': {'layeringDefinition': {'abstract': False},
     'storagePolicy': 'cleartext', 'name': 'application-api',
     'schema': 'metadata/Document/v1'}}

    # Show the revision that was created.
    revision = client.revisions.get(1)

    >>> revision.to_dict()
    {'status': 'success', 'tags': {},
     'url': 'https://deckhand/api/v1.0/revisions/1',
     'buckets': ['mop'], 'validationPolicies': [], 'id': 1,
     'createdAt': '2017-12-09T00:15:04.309071'}

    # List all revisions.
    revisions = client.revisions.list()

    >>> revisions.to_dict()
    {'count': 1, 'results': [{'buckets': ['mop'], 'id': 1,
     'createdAt': '2017-12-09T00:29:34.031460', 'tags': []}]}

    # List raw documents for the created revision.
    raw_documents = client.revisions.documents(1, rendered=False)

    >>> [r.to_dict() for r in raw_documents]
    [{'status': {'bucket': 'foo', 'revision': 1},
      'schema': 'deckhand/Certificate/v1', 'data': {...}, 'id': 1,
      'metadata': {'layeringDefinition': {'abstract': False},
      'storagePolicy': 'cleartext', 'name': 'application-api',
      'schema': 'metadata/Document/v1'}}]

Client Reference
----------------

For more information about how to use the Deckhand client, refer to the
following documentation:

.. autoclass:: deckhand.client.client.SessionClient
    :members:

.. autoclass:: deckhand.client.client.Client
    :members:

Manager Reference
-----------------

For more information about how to use the client managers, refer to the
following documentation:

.. autoclass:: deckhand.client.buckets.Bucket
    :members:

.. autoclass:: deckhand.client.buckets.BucketManager
    :members:
    :undoc-members:

.. autoclass:: deckhand.client.revisions.Revision
    :members:

.. autoclass:: deckhand.client.revisions.RevisionManager
    :members:
    :undoc-members:

.. autoclass:: deckhand.client.tags.RevisionTag
    :members:

.. autoclass:: deckhand.client.tags.RevisionTagManager
    :members:
    :undoc-members:

.. autoclass:: deckhand.client.validations.Validation
    :members:

.. autoclass:: deckhand.client.validations.ValidationManager
    :members:
    :undoc-members:
