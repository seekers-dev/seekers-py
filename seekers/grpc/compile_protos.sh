#!/bin/zsh

git submodule update --init --recursive

rm -rf stubs
mkdir stubs

python -m grpc_tools.protoc \
  --python_out=stubs \
  --grpc_python_out=stubs \
  --proto_path=proto/src/main/proto \
  --mypy_out=stubs \
  proto/src/main/proto/**/*.proto

# invoke proletariat to fix broken imports

protol \
  --create-package \
  --in-place \
  --python-out stubs \
  protoc --proto-path=proto/src/main/proto proto/src/main/proto/**/*.proto
