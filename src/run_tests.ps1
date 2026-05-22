# Run all V9.5 integration tests (PowerShell)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here

Write-Host "Running async manager test..."
python .\tests\test_async_manager.py

Write-Host "Running mock server full tests..."
python .\tests\test_with_mock_server.py

Write-Host "Running stop behavior test..."
python .\tests\test_stop_behavior.py

Pop-Location
Write-Host "All tests completed."