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

import os
import yaml

from gabbi import driver
from gabbi.driver import test_pytest  # noqa
from gabbi.handlers import jsonhandler

TESTS_DIR = 'gabbits'


# This is quite similar to the existing JSONHandler, so use it as the base
# class instead of `gabbi.handlers.base.ContentHandler`.
class MultidocJsonpaths(jsonhandler.JSONHandler):
    test_key_suffix = 'multidoc_jsonpaths'

    @staticmethod
    def accepts(content_type):
        content_type = content_type.split(';', 1)[0].strip()
        return (content_type.endswith('+yaml') or
                content_type.startswith('application/yaml') or
                content_type.startswith('application/x-yaml'))

    @staticmethod
    def dumps(data, pretty=False, test=None):
        return yaml.safe_dump_all(data)

    @staticmethod
    def loads(string):
        # NOTE: The simple approach to handling dictionary versus list response
        # bodies is to always parse the response body as a list and index into
        # the first element using [0] throughout the tests.
        return list(yaml.safe_load_all(string))


def pytest_generate_tests(metafunc):
    test_dir = os.path.join(os.path.dirname(__file__), TESTS_DIR)
    # NOTE(fmontei): While only `url` or `host` is needed, strangely both
    # are needed because we use `pytest-html` which throws an error without
    # `host`.
    driver.py_test_generator(
        test_dir, url=os.environ['DECKHAND_TEST_URL'], host='localhost',
        # NOTE(fmontei): When there are multiple handlers listed that accept
        # the same content-type, the one that is earliest in the list will be
        # used. Thus, we cannot specify multiple content handlers for handling
        # list/dictionary responses from the server using different handlers.
        content_handlers=[MultidocJsonpaths], metafunc=metafunc)
