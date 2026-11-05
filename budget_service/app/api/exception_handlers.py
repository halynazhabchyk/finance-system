from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


async def handle_database_error(_: Request, __: SQLAlchemyError) -> JSONResponse:
    """Hide database details from clients when the database is unavailable."""
    return JSONResponse(
        status_code=503,
        content={"detail": "The budget database is temporarily unavailable."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(SQLAlchemyError, handle_database_error)
