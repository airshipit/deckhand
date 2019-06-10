#!/usr/bin/env bash

# Builds documentation and generates documentation diagrams from .uml
# files. Must be run from root project directory.

set -ex

# Generate documentation.
rm -rf doc/build doc/source/contributor/api/ releasenotes/build
sphinx-apidoc -fo doc/api deckhand
sphinx-build -b html doc/source doc/build/html
