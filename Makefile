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

BUILD_DIR          := $(shell mkdir -p build && mktemp -d -p build)
DOCKER_REGISTRY    ?= quay.io
IMAGE_NAME         ?= deckhand
IMAGE_PREFIX       ?= airshipit
IMAGE_TAG          ?= latest
DISTRO_BASE_IMAGE  ?=
HELM               := $(shell realpath $(BUILD_DIR))/helm
PROXY              ?= http://proxy.foo.com:8000
NO_PROXY           ?= localhost,127.0.0.1,.svc.cluster.local
USE_PROXY          ?= false
PUSH_IMAGE         ?= false
# use this variable for image labels added in internal build process
LABEL              ?= org.airshipit.build=community
DISTRO             ?= ubuntu_jammy
DISTRO_ALIAS	   ?= ubuntu_jammy
COMMIT             ?= $(shell git rev-parse HEAD)
IMAGE              := ${DOCKER_REGISTRY}/${IMAGE_PREFIX}/${IMAGE_NAME}:${IMAGE_TAG}-${DISTRO}
IMAGE_ALIAS              := ${DOCKER_REGISTRY}/${IMAGE_PREFIX}/${IMAGE_NAME}:${IMAGE_TAG}-${DISTRO_ALIAS}
export

# Build Deckhand Docker image for this project
.PHONY: images
images: build_deckhand

# Create tgz of the chart
.PHONY: charts
charts: helm-init
	$(HELM) dep up charts/deckhand
	$(HELM) package charts/deckhand


# Install helm binary
.PHONY: helm-install
helm-install:
	tools/helm_install.sh $(HELM)

# Perform linting
.PHONY: lint
lint: pep8 helm_lint

# Dry run templating of chart
.PHONY: dry-run
dry-run: helm-init
	$(HELM) dep up charts/deckhand
	$(HELM) template charts/deckhand

.PHONY: tests
tests:
	tox

_BASE_IMAGE_ARG := $(if $(DISTRO_BASE_IMAGE),--build-arg FROM="${DISTRO_BASE_IMAGE}" ,)

# Make targets intended for use by the primary targets above.
.PHONY: build_deckhand
build_deckhand:
ifeq ($(USE_PROXY), true)
	docker build --network host -t $(IMAGE) --label $(LABEL) \
		--label "org.opencontainers.image.revision=$(COMMIT)" \
		--label "org.opencontainers.image.created=$(shell date --rfc-3339=seconds --utc)" \
		--label "org.opencontainers.image.title=$(IMAGE_NAME)" \
		$(_BASE_IMAGE_ARG) \
		-f images/deckhand/Dockerfile.$(DISTRO) \
		--build-arg http_proxy=$(PROXY) \
		--build-arg https_proxy=$(PROXY) \
		--build-arg HTTP_PROXY=$(PROXY) \
		--build-arg HTTPS_PROXY=$(PROXY) \
		--build-arg no_proxy=$(NO_PROXY) \
		--build-arg NO_PROXY=$(NO_PROXY) .
else
	docker build --network host -t $(IMAGE) --label $(LABEL) \
		--label "org.opencontainers.image.revision=$(COMMIT)" \
		--label "org.opencontainers.image.created=$(shell date --rfc-3339=seconds --utc)" \
		--label "org.opencontainers.image.title=$(IMAGE_NAME)" \
		$(_BASE_IMAGE_ARG) \
		-f images/deckhand/Dockerfile.$(DISTRO) .
endif
ifneq ($(DISTRO), $(DISTRO_ALIAS))
	docker tag $(IMAGE) $(IMAGE_ALIAS)
ifeq ($(DOCKER_REGISTRY), localhost:5000)
	docker push $(IMAGE_ALIAS)
endif
endif
ifeq ($(DOCKER_REGISTRY), localhost:5000)
	docker push $(IMAGE)
endif
ifeq ($(PUSH_IMAGE), true)
	docker push $(IMAGE)
endif

.PHONY: clean
clean:
	rm -rf build
	helm delete helm-template ||:
	rm -rf doc/build
	# Don't remove .placeholder from doc/source/_static/
	rm -rf doc/api doc/source/_static/* doc/source/contributor/api

.PHONY: docs
docs: clean build_docs

.PHONY: build_docs
build_docs:
	tox -e docs

.PHONY: pep8
pep8:
	tox -e pep8

.PHONY: helm_lint
helm_lint: helm-init
	$(HELM) dep up charts/deckhand
	$(HELM) lint charts/deckhand

# Initialize local helm config
helm-init: helm-install
	tools/helm_tk.sh $(HELM)