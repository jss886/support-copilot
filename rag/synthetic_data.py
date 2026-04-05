import json
from pathlib import Path

from rag.config import RESOURCES_DIR
from rag.embeddings import DashScopeEmbeddingClient
from rag.ingestion import ingest_chunk_records_to_db
from rag.models import ChunkRecord


SYNTHETIC_DATASET_PATH = RESOURCES_DIR / "testdata" / "synthetic_support_docs.json"

SYSTEMS = [
    "order-service",
    "inventory-service",
    "payment-service",
    "promotion-service",
    "user-profile-service",
    "message-service",
    "gateway-service",
    "settlement-service",
    "refund-service",
    "coupon-service",
]

MODULES = [
    "订单创建",
    "库存扣减",
    "优惠计算",
    "支付初始化",
    "消息通知",
    "退款处理",
    "用户画像",
    "风控校验",
    "结算汇总",
    "优惠券核销",
]

SYMPTOMS = [
    "接口超时并伴随 RT 明显抖动",
    "高峰期错误率突然升高",
    "调用链偶发返回 50401",
    "线程池队列持续堆积",
    "用户反馈提交后长时间无响应",
    "接口成功率下降但网关正常",
    "缓存命中率下降后数据库压力升高",
    "日志里频繁出现重试和熔断记录",
]

ROOT_CAUSES = [
    "Redis 热 key 导致热点请求集中",
    "数据库锁等待拉长事务耗时",
    "线程池耗尽导致请求排队",
    "下游服务抖动放大上游超时",
    "消息发送同步阻塞主链路",
    "配置变更导致连接池参数不合理",
    "批量任务抢占资源影响在线流量",
    "缓存失效后回源流量瞬时放大",
]

ACTIONS = [
    "优先检查线程池、Redis 热 key 和数据库锁等待",
    "先确认下游 RT，再看本服务队列长度和连接池状态",
    "必要时先降级非核心逻辑，保护主交易链路",
    "对热点接口增加限流和本地缓存兜底",
    "对慢查询和锁等待做重点排查",
    "通过调用链追踪确认瓶颈是否出在下游",
    "针对高峰期场景预热缓存并扩容线程池",
    "对同步消息改造成异步投递，降低主链路耦合",
]

API_PATHS = [
    "/api/v1/orders",
    "/api/v1/inventory/deduct",
    "/api/v1/payments/init",
    "/api/v1/promotions/calculate",
    "/api/v1/refunds/create",
    "/api/v1/messages/send",
]

ERROR_CODES = ["50401", "50402", "42901", "50031", "50311", "40027"]


def _pick(items: list[str], seed: int, stride: int) -> str:
    return items[(seed * stride + stride) % len(items)]


def _build_doc_chunks(doc_index: int, chunks_per_doc: int) -> list[str]:
    system = _pick(SYSTEMS, doc_index, 3)
    module = _pick(MODULES, doc_index, 5)
    api_path = _pick(API_PATHS, doc_index, 7)
    error_code = _pick(ERROR_CODES, doc_index, 11)

    templates = [
        (
            f"故障概览：{system} 的 {module} 模块在巡检中暴露出问题。"
            f"常见现象是{_pick(SYMPTOMS, doc_index, 2)}。"
            f"该模块核心接口路径为 {api_path}，一旦异常通常会返回错误码 {error_code}。"
        ),
        (
            f"排查建议：当 {system} 的 {module} 触发错误码 {error_code} 时，"
            f"{_pick(ACTIONS, doc_index, 3)}。"
            f"如果问题发生在高峰期，应优先确认网关是否正常，再检查核心下游依赖。"
        ),
        (
            f"根因模式：历史案例显示，{system} 出现 {module} 异常时，"
            f"高概率根因是{_pick(ROOT_CAUSES, doc_index, 2)}。"
            f"如果同时出现 {_pick(SYMPTOMS, doc_index, 4)}，基本可以判定需要重点查看依赖服务状态。"
        ),
        (
            f"接口说明：{module} 对外暴露接口 {api_path}。"
            f"正常情况下返回 code=0；如果依赖链路抖动，可能出现 code={error_code}。"
            f"调用方应避免无限重试，否则会进一步放大 {_pick(ROOT_CAUSES, doc_index, 6)}。"
        ),
        (
            f"可复用经验：遇到 {system} 的 {module} 问题，不要只看应用日志。"
            f"应同时检查 Redis、数据库、线程池和下游 RT。"
            f"如果存在 {_pick(ROOT_CAUSES, doc_index, 8)}，优先做限流、降级和容量回收。"
        ),
        (
            f"依赖说明：{system} 的 {module} 依赖 inventory-service、message-service 和 payment-service。"
            f"当 {_pick(SYMPTOMS, doc_index, 9)} 时，通常意味着下游调用链出现了级联放大，"
            f"可以结合 {_pick(ACTIONS, doc_index, 10)} 来缩小排查范围。"
        ),
        (
            f"监控策略：应对 {module} 的成功率、RT、线程池活跃数、连接池等待数和 Redis 命中率建立监控。"
            f"一旦看到 {_pick(SYMPTOMS, doc_index, 12)} 与 {error_code} 同时出现，"
            f"说明 {system} 可能已经进入退化状态。"
        ),
        (
            f"优化建议：为了降低 {system} 在 {module} 场景下的故障概率，"
            f"建议引入缓存预热、熔断、异步化和热点隔离。"
            f"特别是 {_pick(ROOT_CAUSES, doc_index, 13)} 这类问题，必须在设计阶段预留缓冲手段。"
        ),
    ]
    return templates[:chunks_per_doc]


def seed_synthetic_support_data(
    doc_count: int = 100,
    chunks_per_doc: int = 5,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    embedding_dimensions: int = 1536,
    output_path: Path = SYNTHETIC_DATASET_PATH,
) -> tuple[int, int]:
    if doc_count <= 0 or chunks_per_doc <= 0:
        raise ValueError("doc_count and chunks_per_doc must be positive integers.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = DashScopeEmbeddingClient(dimensions=embedding_dimensions)

    doc_specs: list[dict] = []
    all_chunk_texts: list[str] = []
    for doc_index in range(doc_count):
        title = f"synthetic-support-doc-{doc_index:03d}"
        source = f"synthetic://support-doc/{doc_index:03d}"
        chunks = _build_doc_chunks(doc_index, chunks_per_doc)
        doc_specs.append(
            {
                "title": title,
                "source": source,
                "doc_type": "synthetic_support_doc",
                "tags": {
                    "doc_index": doc_index,
                    "synthetic": True,
                    "domain": "support",
                },
                "chunks": chunks,
            }
        )
        all_chunk_texts.extend(chunks)

    embeddings: list[list[float]] = []
    for index in range(0, len(all_chunk_texts), 10):
        embeddings.extend(client.embed_texts(all_chunk_texts[index : index + 10]))
    embedding_index = 0
    inserted_docs = 0
    inserted_chunks = 0

    for spec in doc_specs:
        records: list[ChunkRecord] = []
        running_start = 0
        for chunk_index, chunk_text in enumerate(spec["chunks"]):
            embedding = embeddings[embedding_index]
            embedding_index += 1
            start = running_start
            end = start + len(chunk_text)
            running_start = end + 1
            records.append(
                ChunkRecord(
                    chunk_id=f"{spec['title']}-chunk-{chunk_index}",
                    source=spec["source"],
                    text=chunk_text,
                    start=start,
                    end=end,
                    embedding=embedding,
                )
            )

        ingest_chunk_records_to_db(
            title=spec["title"],
            source=spec["source"],
            doc_type=spec["doc_type"],
            records=records,
            tags=spec["tags"],
            jdbc_url=jdbc_url,
            db_user=db_user,
            db_password=db_password,
        )
        inserted_docs += 1
        inserted_chunks += len(records)

    output_path.write_text(
        json.dumps(doc_specs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return inserted_docs, inserted_chunks
