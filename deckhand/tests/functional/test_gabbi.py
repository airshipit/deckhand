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

import gabbi.driver
import gabbi.handlers.jsonhandler
import gabbi.json_parser
import os
import yaml


TESTS_DIR = 'gabbits'


# This is quite similar to the existing JSONHandler, so use it as the base
# class instead of gabbi.handlers.base.ContentHandler
class MultidocJsonpaths(gabbi.handlers.jsonhandler.JSONHandler):
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
        return list(yaml.safe_load_all(string))


def load_tests(loader, tests, pattern):
    test_dir = os.path.join(os.path.dirname(__file__), TESTS_DIR)
    return gabbi.driver.build_tests(test_dir, loader,
            content_handlers=[MultidocJsonpaths],
            verbose=True,
            url=os.environ['DECKHAND_TEST_URL'])
