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

DOCKER_REGISTRY            ?= quay.io
IMAGE_NAME                 ?= deckhand
IMAGE_PREFIX               ?= attcomdev
IMAGE_TAG                  ?= latest
HELM                       ?= helm
LABEL                      ?= commit-id

IMAGE := ${DOCKER_REGISTRY}/${IMAGE_PREFIX}/${IMAGE_NAME}:${IMAGE_TAG}

# Build Deckhand Docker image for this project
.PHONY: images
images: build_deckhand

# Create tgz of the chart
.PHONY: charts
charts: clean
	$(HELM) dep up charts/deckhand
	$(HELM) package charts/deckhand

# Perform linting
.PHONY: lint
lint: pep8 helm_lint

# Dry run templating of chart
.PHONY: dry-run
dry-run: clean
	tools/helm_tk.sh $(HELM)

# Make targets intended for use by the primary targets above.
.PHONY: build_deckhand
build_deckhand:
	docker build -t $(IMAGE) --label $(LABEL) .

.PHONY: clean
clean:
	rm -rf build
	helm delete helm-template ||:

.PHONY: pep8
pep8:
	tox -e pep8

.PHONY: helm_lint
helm_lint: clean
	tools/helm_tk.sh $(HELM)
	$(HELM) lint charts/deckhand
