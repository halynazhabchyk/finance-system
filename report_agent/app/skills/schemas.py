"""Arguments of report-agent skills (validated before any API or A2A call)."""

from __future__ import annotations

from shared.ai_tools.tools.schemas import Month, ToolArguments, Year


class MonthArgs(ToolArguments):
    year: Year
    month: Month
    explain: bool = True

    @property
    def period(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


class MonthRef(ToolArguments):
    year: Year
    month: Month


class ComparePeriodsArgs(ToolArguments):
    first: MonthRef
    second: MonthRef
    explain: bool = True
