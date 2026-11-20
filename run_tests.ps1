$ErrorActionPreference = "Stop"

# Each suite runs in its own pytest process.
$suites = @(
    ".\services\user_service\tests",
    ".\services\budget_service\tests",
    ".\services\report_service\tests",
    ".\services\scheduler\tests",
    ".\libs\shared\tests",
    ".\libs\ai_tools\tests",
    ".\services\ai_assistant\tests",
    ".\services\mcp_server\tests",
    ".\services\budget_agent\tests",
    ".\services\report_agent\tests",
    ".\tools\a2a_chat\tests"
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
