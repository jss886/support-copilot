from fastapi import APIRouter

from api.common import translate_exception
from api.schemas import (
    IngestionResult,
    IngestionResponse,
    SeedHardNegativesRequest,
    SeedTestDataRequest,
)
from rag.hard_negative_data import seed_hard_negative_docs_to_db
from rag.synthetic_data import seed_synthetic_support_data

router = APIRouter(prefix="/api/v1/seeding", tags=["造数"])


# 作用：生成模拟测试文档并写入数据库，便于本地演示和接口联调。
@router.post("/test-data", response_model=IngestionResponse, summary="生成模拟测试数据")
def seed_test_data(request: SeedTestDataRequest) -> IngestionResponse:
    try:
        document_count, chunk_count = seed_synthetic_support_data(
            doc_count=request.doc_count,
            chunks_per_doc=request.chunks_per_doc,
            jdbc_url=request.jdbc_url,
            db_user=request.db_user,
            db_password=request.db_password,
            embedding_dimensions=request.embedding_dimensions or 1536,
        )
    except Exception as exc:
        raise translate_exception(exc) from exc

    return IngestionResponse(
        data=IngestionResult(
            document_count=document_count,
            chunk_count=chunk_count,
        ),
        message="测试数据生成完成。",
    )


# 作用：生成 hard negative 干扰文档，帮助验证检索和排序在复杂场景下的表现。
@router.post("/hard-negatives", response_model=IngestionResponse, summary="生成 hard negative 数据")
def seed_hard_negatives(request: SeedHardNegativesRequest) -> IngestionResponse:
    try:
        document_count, chunk_count = seed_hard_negative_docs_to_db(
            jdbc_url=request.jdbc_url,
            db_user=request.db_user,
            db_password=request.db_password,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            batch_size=request.batch_size,
            embedding_dimensions=request.embedding_dimensions or 1536,
        )
    except Exception as exc:
        raise translate_exception(exc) from exc

    return IngestionResponse(
        data=IngestionResult(
            document_count=document_count,
            chunk_count=chunk_count,
        ),
        message="hard negative 数据生成完成。",
    )
