.PHONY: up down smoke demo verify clean setup-python

COMPOSE := $(shell command -v docker 2>/dev/null && echo "docker compose" || echo "podman compose")

up:
	$(COMPOSE) up -d --build
	@echo "Waiting for ledger to be ready..."
	@until curl -sf http://localhost:8080/readyz > /dev/null 2>&1; do sleep 1; done
	@echo "Ledger ready on gRPC :19092"

down:
	$(COMPOSE) down -v

setup-python:
	cd ../sdks/python && pip install -r requirements.txt
	cd ../sdks/python && python -m grpc_tools.protoc \
		-I../../proto \
		--python_out=generated \
		--grpc_python_out=generated \
		../../proto/immutable_ledger.proto

smoke: setup-python
	python 01-standalone-writer.py
	python ../proof-explorer/proof.py verify --all
	python ../proof-explorer/proof.py summary

demo: setup-python
	bash run-demo.sh

verify:
	python ../proof-explorer/proof.py verify --all

clean: down
	rm -rf ../sdks/python/generated/*.py
