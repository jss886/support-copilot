from pathlib import Path

from fastapi import HTTPException


# 作用：把来源过滤条件统一成内部使用的标准格式，远程来源保持原样，本地来源转成路径字符串。
def normalize_source_filter(source: str | None) -> str | None:
    if not source:
        return None
    if "://" in source:
        return source
    return str(Path(source))


# 作用：把业务层抛出的普通异常转换成 HTTP 异常，避免直接把内部堆栈暴露给接口调用方。
def translate_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ConnectionError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))
