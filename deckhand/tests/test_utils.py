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

import random
import uuid


def rand_uuid():
    """Generate a random UUID string

    :return: a random UUID (e.g. '1dc12c7d-60eb-4b61-a7a2-17cf210155b6')
    :rtype: string
    """
    return uuidutils.generate_uuid()


def rand_uuid_hex():
    """Generate a random UUID hex string

    :return: a random UUID (e.g. '0b98cf96d90447bda4b46f31aeb1508c')
    :rtype: string
    """
    return uuid.uuid4().hex


def rand_name(name='', prefix='deckhand'):
    """Generate a random name that includes a random number

    :param str name: The name that you want to include
    :param str prefix: The prefix that you want to include
    :return: a random name. The format is
             '<prefix>-<name>-<random number>'.
             (e.g. 'prefixfoo-namebar-154876201')
    :rtype: string
    """
    randbits = str(random.randint(1, 0x7fffffff))
    rand_name = randbits
    if name:
        rand_name = name + '-' + rand_name
    if prefix:
        rand_name = prefix + '-' + rand_name
    return rand_name


def rand_bool():
    """Generate a random boolean value.

    :return: a random boolean value.
    :rtype: boolean
    """
    return random.choice([True, False])
