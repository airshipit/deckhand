# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

DOCUMENT_SECRET_TYPES = (
    CERTIFICATE_AUTHORITY_SCHEMA,
    CERTIFICATE_KEY_AUTHORITY_SCHEMA,
    CERTIFICATE_KEY_SCHEMA,
    CERTIFICATE_SCHEMA,
    PRIVATE_KEY_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    PASSPHRASE_SCHEMA
) = (
    'deckhand/CertificateAuthority',
    'deckhand/CertificateAuthorityKey',
    'deckhand/Certificate',
    'deckhand/CertificateKey',
    'deckhand/Passphrase',
    'deckhand/PrivateKey',
    'deckhand/PublicKey',
)


DOCUMENT_SCHEMA_TYPES = (
    DATA_SCHEMA_SCHEMA,
    LAYERING_POLICY_SCHEMA,
    VALIDATION_POLICY_SCHEMA,
) = (
    'deckhand/DataSchema',
    'deckhand/LayeringPolicy',
    'deckhand/ValidationPolicy',
)


DOCUMENT_SCHEMA_TYPES += DOCUMENT_SECRET_TYPES


DECKHAND_VALIDATION_TYPES = (
    DECKHAND_SCHEMA_VALIDATION,
) = (
    'deckhand-schema-validation',
)


ENCRYPTION_TYPES = (
    CLEARTEXT,
    ENCRYPTED
) = (
    'cleartext',
    'encrypted',
)


METADATA_SCHEMA_TYPES = (
    CONTROL,
    DOCUMENT
) = (
    'metadata/Control',
    'metadata/Document'
)
