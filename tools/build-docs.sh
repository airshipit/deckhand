#!/usr/bin/env bash

# Builds documentation and generates documentation diagrams from .uml
# files. Must be run from root project directory.

set -ex

# Generate architectural diagrams.
mkdir -p doc/source/images
python -m plantuml doc/source/diagrams/*.uml
mv doc/source/diagrams/*.png doc/source/images

# Generate documentation.
rm -rf doc/build doc/source/contributor/api/ releasenotes/build
sphinx-apidoc -o doc/api deckhand
sphinx-build -W -b html doc/source doc/build/html
