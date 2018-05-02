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

"""Test runner for functional and integration tests."""

import atexit
import os
import shutil
import tempfile
import yaml

from gabbi import driver
from gabbi.driver import test_pytest  # noqa
from gabbi.handlers import jsonhandler

TEST_DIR = None


def __create_temp_test_dir():
    """Hack around the fact that gabbi doesn't support loading tests contained
    in subdirectories. This inconvenience leads to poor test directory layout
    in which all the test files are contained in one directory.

    """
    global TEST_DIR

    TEST_DIR = tempfile.mkdtemp(prefix='deckhand')

    root_test_dir = os.getenv('DECKHAND_TESTS_DIR', 'gabbits')
    test_files = []

    for root, dirs, files in os.walk(root_test_dir):
        is_test_file = 'gabbits' in root
        if is_test_file:
            test_files.extend([os.path.abspath(os.path.join(root, f))
                              for f in files])

    resources_dir = os.path.join(TEST_DIR, 'resources')
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)

    for test_file in test_files:
        basename = os.path.basename(test_file)
        if 'resources' in test_file:
            os.symlink(test_file, os.path.join(resources_dir, basename))
        else:
            os.symlink(test_file, os.path.join(TEST_DIR, basename))


__create_temp_test_dir()


@atexit.register
def __remove_temp_test_dir():
    global TEST_DIR

    if TEST_DIR is not None and os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)


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
        return list(yaml.load_all(string))


def pytest_generate_tests(metafunc):
    # NOTE(fmontei): While only `url` or `host` is needed, strangely both
    # are needed because we use `pytest-html` which throws an error without
    # `host`.
    global TEST_DIR

    driver.py_test_generator(
        TEST_DIR, url=os.environ['DECKHAND_TEST_URL'], host='localhost',
        # NOTE(fmontei): When there are multiple handlers listed that accept
        # the same content-type, the one that is earliest in the list will be
        # used. Thus, we cannot specify multiple content handlers for handling
        # list/dictionary responses from the server using different handlers.
        content_handlers=[MultidocJsonpaths], metafunc=metafunc)
