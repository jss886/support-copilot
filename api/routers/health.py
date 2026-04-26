from fastapi import APIRouter

from api.schemas import HealthInfo, HealthResponse, RootInfo, RootResponse

router = APIRouter(tags=["基础"])


# 作用：提供最基础的服务健康检查，方便确认接口服务是否已经启动。
@router.get("/", response_model=RootResponse, summary="服务说明")
def root() -> RootResponse:
    return RootResponse(
        data=RootInfo(
            name="support-copilot-api",
            docs="/docs",
            openapi="/openapi.json",
        ),
        message="服务已启动。",
    )


# 作用：提供健康检查接口，便于部署系统或网关做存活探测。
@router.get("/health", response_model=HealthResponse, summary="健康检查")
def health() -> HealthResponse:
    return HealthResponse(data=HealthInfo(status="ok"), message="服务健康。")
