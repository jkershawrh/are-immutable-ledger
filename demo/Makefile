.PHONY: up down smoke demo verify clean setup-python

COMPOSE := $(shell command -v docker 2>/dev/null && echo "docker compose" || \
	python3 -c "import shutil; print(shutil.which('podman-compose') or 'podman-compose')" 2>/dev/null || echo "podman-compose")

up:
	$(COMPOSE) up -d --build
	@echo "Waiting for ledger to be ready..."
	@until curl -sf http://localhost:18080/readyz > /dev/null 2>&1; do sleep 1; done
	@echo "Ledger ready on gRPC :19092"

down:
	$(COMPOSE) down -v

setup-python:
	pip3 install grpcio protobuf 2>/dev/null || pip install grpcio protobuf

smoke: setup-python
	python3 01-standalone-writer.py
	python3 ../proof-explorer/proof.py verify --all
	python3 ../proof-explorer/proof.py summary

demo: setup-python
	bash run-demo.sh

verify:
	python3 ../proof-explorer/proof.py verify --all

clean: down
	rm -rf ../sdks/python/generated/*.py
