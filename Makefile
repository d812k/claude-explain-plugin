.PHONY: check fmt lint type test prop test-all layers validate
check: lint type test
fmt: ; uv run ruff format . && uv run ruff check --fix .
lint: ; uv run ruff format --check . && uv run ruff check .
type: ; uv run pyright
test: ; uv run pytest
prop: ; HYPOTHESIS_PROFILE=ci uv run pytest -o addopts="" -q -m prop --timeout=60
test-all: validate ; uv run pytest -o addopts="" -q --timeout=60
layers: ; uv run lint-imports
validate: ; claude plugin validate .
