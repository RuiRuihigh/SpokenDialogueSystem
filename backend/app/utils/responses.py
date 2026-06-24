from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any = None, *, status_code: int = 200, message: str = "success") -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": status_code, "message": message, "data": data})


def error_response(status_code: int, message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": status_code, "message": message, "data": data})
