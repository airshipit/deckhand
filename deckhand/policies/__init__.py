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

import itertools

from deckhand.policies import base
from deckhand.policies import document
from deckhand.policies import revision
from deckhand.policies import revision_tag


def list_rules():
    return itertools.chain(
        base.list_rules(),
        document.list_rules(),
        revision.list_rules(),
        revision_tag.list_rules()
    )
