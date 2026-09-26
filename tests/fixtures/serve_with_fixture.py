"""Browser-verification launcher: the normal app plus the CONTROLLED SPIR FIXTURE adapter.

For verification only — never the way to run the product. Usage:

    set MTL_DATA_DIR=<scratch dir>
    .venv\\Scripts\\python -m tests.fixtures.serve_with_fixture [port]
"""

import sys

import uvicorn

from backend.extraction import registry
from backend.main import create_app
from tests.fixtures.second_source import FIXTURE_SPIR_ADAPTER

if __name__ == "__main__":
    registry.ADAPTERS[FIXTURE_SPIR_ADAPTER.source_type] = FIXTURE_SPIR_ADAPTER
    uvicorn.run(create_app(), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8300)
