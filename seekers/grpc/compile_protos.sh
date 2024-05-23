#!/bin/bash

git submodule update --init --recursive

rm -rf stubs
mkdir stubs

mapfile -d '' proto_src_files < <(find proto/src/main/proto -name '*.proto' -print0)

python -m grpc_tools.protoc \
  --python_out=stubs \
  --grpc_python_out=stubs \
  --proto_path=proto/src/main/proto \
  --mypy_out=stubs \
  --experimental_allow_proto3_optional \
  "${proto_src_files[@]}"

# invoke proletariat to fix broken imports

protol \
  --create-package \
  --in-place \
  --python-out stubs \
  protoc --proto-path=proto/src/main/proto "${proto_src_files[@]}" --experimental_allow_proto3_optional
