import time
from collections.abc import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from tqdm import tqdm

from ingestion.law_ingestion.law import Law
from ingestion.law_vector.article_chunk import ArticleChunk

_BATCH_SIZE = 100
_COLLECTION_NAME = "chunks"


def _collect(laws: list[Law]) -> list[ArticleChunk]:
    """從 laws 收集 ArticleType='A' 的條文，轉為 ArticleChunk 清單。

    Args:
        laws (list[Law]): 已載入的法律清單。

    Returns:
        list[ArticleChunk]: 所有可 embed 的條文。
    """
    chunks: list[ArticleChunk] = []
    for law in laws:
        for article in law.articles:
            if article.article_type != "A":
                continue
            chunks.append(
                ArticleChunk.from_article(article, law.law_modified_date)
            )
    return chunks


def _filter_new(
    b_chunks: list[ArticleChunk],
    existing: set[str],
) -> list[ArticleChunk]:
    """回傳 ID 尚未存在於 Chroma 的 ArticleChunk。

    Args:
        b_chunks (list[ArticleChunk]): 本批次的條文清單。
        existing (set[str]): 已存在於 Chroma 的 ID 集合。

    Returns:
        list[ArticleChunk]: 需要新增的條文。
    """
    # 僅用於第一次建立，未處理同 ID 但 law_modified_date 較新的情況
    return [c for c in b_chunks if c.to_node_id() not in existing]


class ChunkBuilder:
    """建立並查詢 Chroma 的 chunks collection。"""

    def __init__(
        self, persist_directory: str, embeddings: Embeddings
    ) -> None:
        """指定 Chroma persist 路徑與 embedding 函式。

        Args:
            persist_directory (str): Chroma collection 的本地
                儲存路徑。
            embeddings (Embeddings): 用於 embed 條文與查詢的模型。
        """
        self._persist_dir = persist_directory
        self._embeddings = embeddings
        self._col = self._make_col()

    def _make_col(self) -> Chroma:
        """建立並綁定 Chroma collection 到 persist_directory。

        Returns:
            Chroma: 綁定完成的 Chroma collection。
        """
        # 一個 persist_directory 對應一個 Chroma Client
        return Chroma(
            collection_name=_COLLECTION_NAME,
            persist_directory=self._persist_dir,
            embedding_function=self._embeddings,
        )

    def count(self) -> int:
        """回傳 collection 中的條文總數。

        Returns:
            int: 已 embed 的條文數量。
        """
        return self._col._collection.count()

    def is_populated(self) -> bool:
        """回傳 collection 是否已有至少一筆資料。

        Returns:
            bool: 有資料為 True，空 collection 為 False。
        """
        return self.count() > 0

    def build(self, laws: list[Law], batch_sleep: float = 0.0) -> int:
        """將法律條文 embed 並存入 Chroma，跳過已存在的 ID。

        Args:
            laws (list[Law]): 要建立索引的法律清單。
            batch_sleep (float): 每批次後的等待秒數，避免 API 限流。

        Returns:
            int: 本次新增的條文數量。
        """
        chunks = _collect(laws)
        total = len(chunks)
        added = 0
        with tqdm(total=total, unit="chunk") as pbar:
            for i in range(0, total, _BATCH_SIZE):
                b_chunks = chunks[i : i + _BATCH_SIZE]
                b_ids = [c.to_node_id() for c in b_chunks]

                # Chroma.get(ids=b_ids) 查詢哪些 ID 已存在
                existing: set[str] = set(
                    self._col.get(ids=b_ids)["ids"] or []
                )
                new_chunks = _filter_new(b_chunks, existing)
                if new_chunks:
                    self._col.add_texts(
                        texts=[c.to_document() for c in new_chunks],
                        ids=[c.to_node_id() for c in new_chunks],
                        metadatas=[c.to_metadata() for c in new_chunks],
                    )
                    added += len(new_chunks)
                    time.sleep(batch_sleep)
                pbar.update(len(b_chunks))
        return added

    def clear(self) -> None:
        """刪除並重建 collection，清除所有已 embed 的資料。"""
        self._col.delete_collection()
        self._col = self._make_col()

    def _to_chunks(
        self,
        docs_with_scores: Sequence[tuple[Document, float | None]],
    ) -> list[ArticleChunk]:
        """將 Chroma Document 清單轉換為 ArticleChunk 清單。

        peek_chunks 與 search_chunks 共用的轉換邏輯。

        Args:
            docs_with_scores (list[tuple[Document, float | None]]):
                Document 與相似度分數的配對清單，peek 時分數為 None。

        Returns:
            list[ArticleChunk]: 對應的 ArticleChunk 清單。
        """
        return [
            ArticleChunk.from_chroma(doc, score=score)
            for doc, score in docs_with_scores
        ]

    def peek_chunks(self, n: int = 3) -> list[ArticleChunk]:
        """不觸發 embedding，直接取出 n 筆樣本條文。

        Args:
            n (int): 要取出的條文數量，預設為 3。

        Returns:
            list[ArticleChunk]: 樣本條文清單，score 為 None。
        """
        raw = self._col.get(limit=n, include=["documents", "metadatas"])
        raw_docs: list[str] = raw["documents"] or []
        raw_metas: list[dict[str, str]] = raw["metadatas"] or []
        pairs: list[tuple[Document, float | None]] = [
            (Document(page_content=doc, metadata=raw_metas[i]), None)
            for i, doc in enumerate(raw_docs)
        ]
        return self._to_chunks(pairs)

    def search_chunks(
        self, query: str, k: int = 5
    ) -> list[ArticleChunk]:
        """Embed query 並回傳相似度最高的前 k 筆條文。

        Args:
            query (str): 自然語言查詢字串。
            k (int): 回傳結果數量，預設為 5。

        Returns:
            list[ArticleChunk]: 依相似度排序的條文清單，含 score。
        """
        results = self._col.similarity_search_with_score(query, k=k)
        return self._to_chunks(results)
