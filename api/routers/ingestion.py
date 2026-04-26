from pathlib import Path

from fastapi import APIRouter

from api.common import translate_exception
from api.schemas import (
    DirectoryIngestionRequest,
    FeishuDocIngestionRequest,
    FeishuWikiSubtreeIngestionRequest,
    FileIngestionRequest,
    IngestionResult,
    IngestionResponse,
)
from rag.ingestion import (
    ingest_directory_to_db,
    ingest_feishu_doc_to_db,
    ingest_feishu_wiki_subtree_to_db,
    ingest_file_to_db,
)

router = APIRouter(prefix="/api/v1/ingestion", tags=["入库"])


# 作用：把单个本地文件导入知识库，并返回文档和切片写入结果。
@router.post("/file", response_model=IngestionResponse, summary="导入单个本地文件")
def ingest_file(request: FileIngestionRequest) -> IngestionResponse:
    try:
        document_id, chunk_count = ingest_file_to_db(
            source_path=Path(request.source),
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
            document_id=document_id,
            document_count=1,
            chunk_count=chunk_count,
        ),
        message="文件入库完成。",
    )


# 作用：批量导入目录下的 Markdown 文件，并汇总返回处理结果。
@router.post("/directory", response_model=IngestionResponse, summary="批量导入目录文档")
def ingest_directory(request: DirectoryIngestionRequest) -> IngestionResponse:
    try:
        document_count, chunk_count = ingest_directory_to_db(
            source_dir=Path(request.source_dir),
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
        message="目录入库完成。",
    )


# 作用：导入单篇飞书文档，并返回本次写入的结果摘要。
@router.post("/feishu/doc", response_model=IngestionResponse, summary="导入单篇飞书文档")
def ingest_feishu_doc(request: FeishuDocIngestionRequest) -> IngestionResponse:
    try:
        document_id, chunk_count = ingest_feishu_doc_to_db(
            doc_id=request.doc_id,
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
            document_id=document_id,
            document_count=1,
            chunk_count=chunk_count,
        ),
        message="飞书文档入库完成。",
    )


# 作用：递归导入飞书知识库节点下的全部文档，适合批量同步飞书内容。
@router.post(
    "/feishu/wiki-subtree",
    response_model=IngestionResponse,
    summary="递归导入飞书知识库节点",
)
def ingest_feishu_wiki_subtree(request: FeishuWikiSubtreeIngestionRequest) -> IngestionResponse:
    try:
        document_count, chunk_count = ingest_feishu_wiki_subtree_to_db(
            space_id=request.space_id,
            parent_node_token=request.parent_node_token,
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
        message="飞书知识库批量入库完成。",
    )
