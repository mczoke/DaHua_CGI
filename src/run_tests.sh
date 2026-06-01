#!/usr/bin/env bash
# Run all V9.5 integration tests (Linux compatible)
set -euo pipefail

cd "$(dirname "$0")"

echo "========================================"
echo " DaHua_CGI — Test Suite Runner"
echo "========================================"

export PYTHONPATH="${PYTHONPATH:-}:${PWD}"

echo ""
echo "--- Running async manager test ---"
python tests/test_async_manager.py

echo ""
echo "--- Running mock server full tests ---"
python tests/test_with_mock_server.py

echo ""
echo "--- Running stop behavior test ---"
python tests/test_stop_behavior.py

echo ""
echo "========================================"
echo " All tests completed."
echo "========================================"
