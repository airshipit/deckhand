# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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
PROXY                      ?= http://proxy.foo.com:8000
USE_PROXY                  ?= false
PUSH_IMAGE                 ?= false
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
	$(HELM) template charts/deckhand

.PHONY: tests
tests:
	tox

# Make targets intended for use by the primary targets above.
.PHONY: build_deckhand
build_deckhand:
ifeq ($(USE_PROXY), true)
	docker build --network host -t $(IMAGE) --label $(LABEL) -f images/deckhand/Dockerfile . --build-arg HTTP_PROXY=$(PROXY) --build-arg HTTPS_PROXY=$(PROXY)
else
	docker build --network host -t $(IMAGE) --label $(LABEL) -f images/deckhand/Dockerfile .
endif
ifeq ($(PUSH_IMAGE), true)
	docker push $(IMAGE)
endif

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
