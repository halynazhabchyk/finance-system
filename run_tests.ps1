$ErrorActionPreference = "Stop"

# Each suite runs in its own pytest process.
$suites = @(
    ".\user_service\tests",
    ".\budget_service\tests",
    ".\report_service\tests",
    ".\shared\security\tests",
    ".\shared\ai_tools\tests",
    ".\ai_assistant\tests",
    ".\mcp_server\tests",
    ".\budget_agent\tests",
    ".\report_agent\tests",
    ".\a2a_chat\tests"
)

$failed = @()
foreach ($suite in $suites) {
    Write-Host "`n=== $suite ===" -ForegroundColor Cyan
    & .\.venv\Scripts\pytest.exe $suite -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { $failed += $suite }
}

if ($failed.Count -gt 0) {
    Write-Host "`nFailed: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "`nAll test suites passed." -ForegroundColor Green
