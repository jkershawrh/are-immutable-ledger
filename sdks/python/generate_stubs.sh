#!/bin/bash
set -e
cd "$(dirname "$0")"
python -m grpc_tools.protoc \
  -I../../proto \
  --python_out=generated \
  --grpc_python_out=generated \
  ../../proto/immutable_ledger.proto
echo "Stubs generated in sdks/python/generated/"
