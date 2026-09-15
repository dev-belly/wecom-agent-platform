"""混合检索系统 — BM25 + Dense Vector + Rerank"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np
from loguru import logger
from rank_bm25 import BM25Okapi

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection
    from FlagEmbedding import FlagReranker
    from sentence_transformers import SentenceTransformer

from src.config.settings import get_settings
from src.parsers.pdf_parser import ParsedDocument


class HybridRetriever:
    """
    混合检索管线

    Pipeline:
      1. BM25 关键词召回 (top_k=50)
      2. Dense Vector 语义召回 (top_k=20)
      3. 结果融合 + Rerank 重排序 (top_k=10)
      4. 最终截断返回 (top_k=3)
    """

    def __init__(self):
        self.settings = get_settings()

        # ── BM25 ──
        self.bm25: Optional[BM25Okapi] = None
        self.bm25_docs: list[str] = []       # 原始文档文本（对应 bm25 index）
        self.bm25_metadatas: list[dict] = []  # 对应元数据

        # ── Embedding ──
        self.encoder: Optional["SentenceTransformer"] = None

        # ── Vector DB ──
        self.chroma_client: Optional[object] = None
        self.collection: Optional["Collection"] = None

        # ── Reranker ──
        self.reranker: Optional["FlagReranker"] = None

        self._initialized = False

    # ── 构建 Index ────────────────────────────────────

    def build_index_from_parsed(self, parsed_docs: list[ParsedDocument]) -> None:
        """从已解析的 PDF 文档构建全部索引"""
        logger.info("开始构建混合检索索引...")

        # 收集所有文本块
        all_chunks: list[str] = []
        all_metadatas: list[dict] = []

        for doc in parsed_docs:
            # 表格数据转为文本块
            for table in doc.tables:
                for row in table.rows:
                    chunk = " | ".join(f"{k}:{v}" for k, v in row.items() if v is not None)
                    if chunk.strip():
                        all_chunks.append(chunk)
                        all_metadatas.append({
                            "source": doc.source_file,
                            "type": "table_row",
                            "page": table.page_num,
                        })

            # 全文按段落切分（BM25 用）
            paragraphs = [p.strip() for p in doc.raw_text.split("\n") if len(p.strip()) > 20]
            for p in paragraphs:
                all_chunks.append(p)
                all_metadatas.append({
                    "source": doc.source_file,
                    "type": "text_paragraph",
                })

        logger.info(f"共 {len(all_chunks)} 个文本块，开始建索引...")

        if not all_chunks:
            raise ValueError("解析结果中没有可用于检索的文本内容")

        # 1. BM25 索引
        self._build_bm25(all_chunks, all_metadatas)

        # 2. 向量索引
        self._build_vector_index(all_chunks, all_metadatas)

        # 3. 加载 Reranker
        self._load_reranker()

        self._initialized = True
        logger.info("✅ 混合检索索引构建完成")

    def _build_bm25(self, chunks: list[str], metadatas: list[dict]) -> None:
        """构建 BM25 索引"""
        if not chunks:
            self.bm25 = None
            self.bm25_docs = []
            self.bm25_metadatas = []
            logger.warning("没有可用于 BM25 索引的文本块")
            return
        tokenized = [self._tokenize_zh(c) for c in chunks]
        self.bm25 = BM25Okapi(tokenized)
        self.bm25_docs = chunks
        self.bm25_metadatas = metadatas
        logger.info("BM25 索引就绪")

    def _build_vector_index(self, chunks: list[str], metadatas: list[dict]) -> None:
        """构建向量索引"""
        if not chunks:
            self.encoder = None
            self.collection = None
            return
        try:
            from chromadb import Client, Settings
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self.encoder = None
            self.collection = None
            logger.warning('未安装可选向量检索依赖，继续使用 BM25；可执行 pip install -e ".[retrieval]" 启用')
            return
        self.encoder = SentenceTransformer(self.settings.embedding_model, device=self.settings.embedding_device)

        persist_dir = Path(self.settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.chroma_client = Client(Settings(persist_directory=str(persist_dir), is_persistent=True))
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # 批量编码入库
        batch_size = 64
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            embeddings = self.encoder.encode(batch, normalize_embeddings=True).tolist()
            ids = [f"doc_{j}" for j in range(i, i + len(batch))]
            self.collection.upsert(ids=ids, embeddings=embeddings, documents=batch, metadatas=batch_meta)

        logger.info(f"向量索引就绪: {self.collection.count()} 条记录")

    def _load_reranker(self) -> None:
        """加载 Reranker 模型"""
        try:
            from FlagEmbedding import FlagReranker
        except ImportError:
            self.reranker = None
            logger.warning('未安装可选重排依赖，继续使用融合排序；可执行 pip install -e ".[retrieval]" 启用')
            return
        self.reranker = FlagReranker(self.settings.reranker_model, use_fp16=True)
        logger.info("Reranker 模型加载完成")

    # ── 检索 ──────────────────────────────────────────

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """
        执行混合检索

        Returns:
            排序后的结果列表，每项包含 {text, score, metadata, source}
        """
        if not self._initialized:
            raise RuntimeError("索引未初始化，请先调用 build_index_from_parsed()")

        final_k = top_k or self.settings.final_top_k
        bm25_k = self.settings.bm25_top_k
        vec_k = self.settings.vector_top_k
        rerank_k = self.settings.rerank_top_k

        # 1. BM25 召回
        bm25_results = self._bm25_search(query, top_k=bm25_k)

        # 2. 向量召回
        vec_results = self._vector_search(query, top_k=vec_k)

        # 3. 融合去重（RRF — Reciprocal Rank Fusion）
        fused = self._rrf_fusion(bm25_results, vec_results)

        # 4. Rerank 重排
        candidates = fused[: rerank_k * 2]  # 多取一些给 reranker
        reranked = self._rerank(query, candidates, top_k=rerank_k)

        return reranked[:final_k]

    def _bm25_search(self, query: str, top_k: int) -> list[dict]:
        """BM25 关键词搜索"""
        if self.bm25 is None:
            return []
        tokenized_query = self._tokenize_zh(query)
        scores = self.bm25.get_scores(tokenized_query)
        # Okapi scores can be zero/negative when terms occur in most documents,
        # including a one-document index. Token overlap determines eligibility.
        top_indices = [
            i for i in np.argsort(scores)[::-1]
            if any(token in self.bm25.doc_freqs[i] for token in tokenized_query)
        ][:top_k]

        return [
            {
                "text": self.bm25_docs[i],
                "score": float(scores[i]),
                "metadata": self.bm25_metadatas[i],
                "source": "bm25",
            }
            for i in top_indices
        ]

    def _vector_search(self, query: str, top_k: int) -> list[dict]:
        """Dense Vector 语义搜索"""
        if self.encoder is None or self.collection is None:
            return []
        query_embedding = self.encoder.encode([query], normalize_embeddings=True).tolist()[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        items = []
        for i in range(len(results["ids"][0])):
            items.append({
                "text": results["documents"][0][i],
                "score": 1.0 - results["distances"][0][i],  # cosine → similarity
                "metadata": results["metadatas"][0][i],
                "source": "vector",
            })
        return items

    def _rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """Rerank 重排序"""
        if not candidates:
            return []

        if self.reranker is None:
            return [
                {**candidate, "rerank_score": float(candidate.get("rrf_score", 0.0))}
                for candidate in candidates[:top_k]
            ]

        pairs = [[query, c["text"]] for c in candidates]
        scores = self.reranker.compute_score(pairs)
        if np.isscalar(scores):
            scores = [scores]

        scored = [(c, s) for c, s in zip(candidates, scores)]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            {**c, "rerank_score": float(s)}
            for c, s in scored[:top_k]
        ]

    # ── 辅助方法 ──────────────────────────────────────

    @staticmethod
    def _tokenize_zh(text: str) -> list[str]:
        """中文简单分词（按字符 n-gram + 词边界）"""
        # 简单实现：按字符 + 常见词切分
        text = text.lower().strip()
        tokens = []
        # bigram
        for i in range(len(text) - 1):
            tokens.append(text[i : i + 2])
        # unigram
        tokens.extend(list(text))
        return tokens

    @staticmethod
    def _rrf_fusion(results_a: list[dict], results_b: list[dict], k: int = 60) -> list[dict]:
        """
        Reciprocal Rank Fusion

        RRF(score) = Σ 1/(k + rank_i)
        """
        scores: dict[str, float] = {}
        item_map: dict[str, dict] = {}

        for results in [results_a, results_b]:
            for rank, item in enumerate(results):
                # BM25 与向量召回会创建不同的 dict 对象；对象 id 无法去重。
                # 文本和元数据共同构成稳定键，避免相同正文来自不同文档时误合并。
                item_id = json.dumps(
                    [item.get("text", ""), item.get("metadata", {})],
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if item_id not in scores:
                    scores[item_id] = 0.0
                    item_map[item_id] = item
                scores[item_id] += 1.0 / (k + rank + 1)

        ranked_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [{**item_map[i], "rrf_score": scores[i]} for i in ranked_ids]


# ── 评估工具 ────────────────────────────────────────────
class RetrievalEvaluator:
    """检索评估器 — 计算 Recall@K 和 Precision@K"""

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever

    def evaluate(
        self,
        eval_data: list[dict],  # [{"query": "...", "relevant_texts": ["..."]}]
        recall_k: Optional[list[int]] = None,
        precision_k: Optional[list[int]] = None,
    ) -> dict:
        """
        在测试集上评估检索质量

        Returns:
            {"recall@10": 0.91, "precision@3": 0.87, ...}
        """
        recall_k = recall_k or [10]
        precision_k = precision_k or [3]
        if not eval_data:
            raise ValueError("评估数据不能为空")
        if any(k <= 0 for k in [*recall_k, *precision_k]):
            raise ValueError("评估截断值必须为正整数")

        metrics = {f"recall@{k}": [] for k in recall_k}
        metrics.update({f"precision@{k}": [] for k in precision_k})

        for sample in eval_data:
            query = sample["query"]
            labels = sample.get("relevant_texts")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("评估问题必须是非空文本")
            if not isinstance(labels, list) or not labels or any(
                not isinstance(label, str) or not label.strip() for label in labels
            ):
                raise ValueError("评估样本必须包含非空 relevant_texts 字符串数组")
            relevant = set(labels)

            results = self.retriever.retrieve(query, top_k=max(max(recall_k), max(precision_k)))
            retrieved_texts = [r["text"] for r in results]

            for k in recall_k:
                found = sum(any(rel in rt for rt in retrieved_texts[:k]) for rel in relevant)
                metrics[f"recall@{k}"].append(found / len(relevant))

            for k in precision_k:
                hits = sum(1 for rt in retrieved_texts[:k] if any(rel in rt for rel in relevant))
                metrics[f"precision@{k}"].append(hits / k)

        # 汇总
        summary = {key: round(sum(vals) / len(vals), 4) for key, vals in metrics.items()}
        summary["num_samples"] = len(eval_data)
        logger.info(f"评估结果: {summary}")
        return summary
