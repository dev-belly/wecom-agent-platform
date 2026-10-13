"""Single-process index publication and reader-safe vector collection cleanup."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4

from loguru import logger

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection
    from FlagEmbedding import FlagReranker
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer


@dataclass
class IndexSnapshot:
    """Payload is built privately and never changed after publication.

    Reader/retirement counters belong to the store's lock, not to callers.
    Collections are unique to one generation, so preparing a replacement cannot
    overwrite the vector records of a reader on the previous generation.
    """

    revision: str = field(default_factory=lambda: uuid4().hex)
    bm25: BM25Okapi | None = None
    bm25_docs: tuple[str, ...] = ()
    bm25_metadatas: tuple[dict, ...] = ()
    structured_rows: tuple[dict, ...] = ()
    encoder: SentenceTransformer | None = None
    chroma_client: object | None = None
    collection: Collection | None = None
    collection_name: str | None = None
    reranker: FlagReranker | None = None
    readers: int = 0
    retired: bool = False


class IndexSnapshotStore:
    def __init__(self):
        self._lock = RLock()
        self._active: IndexSnapshot | None = None
        self._closed = False
        # Failed deletions retain only the client/name, not obsolete model data.
        self._pending_cleanup: dict[str, object] = {}

    @property
    def active(self) -> IndexSnapshot | None:
        """For readiness/diagnostics only; queries must use capture()."""
        with self._lock:
            return self._active

    @property
    def cleanup_pending(self) -> int:
        with self._lock:
            return len(self._pending_cleanup)

    @contextmanager
    def capture(self):
        with self._lock:
            snapshot = self._active
            if snapshot is not None:
                snapshot.readers += 1
        try:
            yield snapshot
        finally:
            if snapshot is not None:
                with self._lock:
                    snapshot.readers -= 1
                    can_clean = snapshot.retired and snapshot.readers == 0
                if can_clean:
                    self.discard(snapshot)

    def publish(self, snapshot: IndexSnapshot) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("检索服务已关闭")
            previous = self._active
            self._active = snapshot
            if previous is not None:
                previous.retired = True
            can_clean = previous is not None and previous.readers == 0
        if can_clean:
            self.discard(previous)

    def discard(self, snapshot: IndexSnapshot) -> None:
        """Delete only the exact collection owned by this generation."""
        with self._lock:
            name, client = snapshot.collection_name, snapshot.chroma_client
            snapshot.collection_name = None  # Claim cleanup once.
            if name is not None and client is not None:
                self._pending_cleanup[name] = client
        if name is not None and client is not None:
            self._delete_collection(name, client)

    def _delete_collection(self, name: str, client: object) -> None:
        try:
            client.delete_collection(name=name)
        except Exception as exc:
            logger.warning(f"旧索引向量集合清理失败，下一次重建会重试: {name}: {exc}")
        else:
            with self._lock:
                self._pending_cleanup.pop(name, None)

    def retry_cleanup(self) -> None:
        with self._lock:
            pending = list(self._pending_cleanup.items())
        for name, client in pending:
            self._delete_collection(name, client)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            previous, self._active = self._active, None
            if previous is not None:
                previous.retired = True
            can_clean = previous is not None and previous.readers == 0
        if can_clean:
            self.discard(previous)
        self.retry_cleanup()
