$ErrorActionPreference = "Stop"

& .\.venv\Scripts\pytest.exe .\user_service\tests -q
& .\.venv\Scripts\pytest.exe .\budget_service\tests -q
& .\.venv\Scripts\pytest.exe .\report_service\tests -q
