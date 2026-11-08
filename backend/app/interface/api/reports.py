import csv
import io
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.application import reports as service
from app.interface.api.deps import DbSession, SysAdmin

router = APIRouter(prefix="/reports", tags=["reports"])

Year = Annotated[int | None, Query(ge=2000, le=2100)]
Quarter = Annotated[int | None, Query(ge=1, le=4)]
OutputFormat = Annotated[Literal["json", "csv"], Query(alias="format")]


class QuarterlyReport(BaseModel):
    year: int
    quarter: int
    period_start: date
    period_end: date
    found: int
    returned: int
    marked_for_disposal: int


def _csv_response(report: dict) -> Response:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(report))
    writer.writeheader()
    writer.writerow(report)
    filename = f"quarterly-{report['year']}-Q{report['quarter']}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/quarterly", response_model=QuarterlyReport)
def quarterly_report(
    user: SysAdmin,
    db: DbSession,
    year: Year = None,
    quarter: Quarter = None,
    fmt: OutputFormat = "json",
):
    if (year is None) != (quarter is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "year and quarter must be given together"
        )
    if year is None or quarter is None:
        year, quarter = service.current_quarter()
    report = service.quarterly_report(db, year, quarter)
    return _csv_response(report) if fmt == "csv" else report
