from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference

from api.routers.answering import router as answering_router
from api.routers.evaluation import router as evaluation_router
from api.routers.health import router as health_router
from api.routers.ingestion import router as ingestion_router
from api.routers.retrieval import router as retrieval_router
from api.routers.seeding import router as seeding_router


# 作用：创建并配置 FastAPI 应用，统一注册路由、文档信息和异常处理。
def create_app() -> FastAPI:
    app = FastAPI(
        title="Support Copilot API",
        description="把原有 CLI 能力改造成可通过 Swagger 和 Scalar 调试的 HTTP 接口。",
        version="1.1.0",
    )

    app.include_router(health_router)
    app.include_router(ingestion_router)
    app.include_router(seeding_router)
    app.include_router(retrieval_router)
    app.include_router(answering_router)
    app.include_router(evaluation_router)

    # 这里补一个 Scalar 文档入口，保留 Swagger 的同时提供更现代的调试体验。
    # 这里统一生成 Scalar 页面，并显式关闭缓存，避免浏览器继续展示旧页面。
    def _build_scalar_response() -> HTMLResponse:
        response = get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title="Support Copilot Scalar",
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/scalar", include_in_schema=False)
    async def scalar_docs() -> HTMLResponse:
        return _build_scalar_response()

    # 这里额外提供一个新地址，绕开浏览器对旧 /scalar 页面可能留下的强缓存。
    @app.get("/reference", include_in_schema=False)
    async def scalar_reference() -> HTMLResponse:
        return _build_scalar_response()

    # 这里单独处理参数校验异常，保证文档页调试时返回结构尽量统一。
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "请求参数校验失败。",
                "data": exc.errors(),
            },
        )

    # 这里兜底未处理异常，避免接口直接返回默认 HTML 错误页。
    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "服务内部异常。",
                "data": {"detail": str(exc)},
            },
        )

    return app


app = create_app()
