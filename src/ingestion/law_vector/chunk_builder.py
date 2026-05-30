import time

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from tqdm import tqdm

from ingestion.law_ingestion.law import Law

_BATCH_SIZE = 100
_COLLECTION_NAME = "chunks"


def _collect(
    laws: list[Law],
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    """Collect ArticleType='A' articles as parallel lists for add_texts()."""
    docs: list[str] = []
    ids: list[str] = []
    metas: list[dict[str, str]] = []
    for law in laws:
        for article in law.articles:
            if article.article_type != "A":
                continue
            node_id = f"{article.pcode}#{article.article_no}"
            docs.append(
                f"{article.law_name} {article.article_no}\n"
                f"{article.artical_content}"
            )
            ids.append(node_id)
            metas.append(
                {
                    "pcode": article.pcode,
                    "article_no": article.article_no,
                    "law_name": article.law_name,
                    "law_modified_date": law.law_modified_date,
                }
            )
    return docs, ids, metas


def _filter_new(
    b_docs: list[str],
    b_ids: list[str],
    b_metas: list[dict[str, str]],
    existing: set[str],
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    """Return only the items whose IDs are not yet in Chroma."""

    # 僅用於第一次建立, 這邊沒有處理同 ID 但 law_modified_date 比較新的狀況
    new_docs: list[str] = []
    new_ids: list[str] = []
    new_metas: list[dict[str, str]] = []
    for d, id_, m in zip(b_docs, b_ids, b_metas):
        if id_ not in existing:
            new_docs.append(d)
            new_ids.append(id_)
            new_metas.append(m)
    return new_docs, new_ids, new_metas


class ChunkBuilder:
    """Builds and queries the Chroma 'chunks' collection."""

    def __init__(self, persist_directory: str, embeddings: Embeddings) -> None:
        self._persist_dir = persist_directory
        self._embeddings = embeddings
        self._col = self._make_col()

    def _make_col(self) -> Chroma:
        """Bind a new Chroma collection to this persist_directory."""
        # 一個 Chroma Client 就只有一個 Client
        return Chroma(
            collection_name=_COLLECTION_NAME,
            persist_directory=self._persist_dir,
            embedding_function=self._embeddings,
        )

    def count(self) -> int:
        """Access _collection.count(); LangChain wrapper doesn't expose it."""
        return self._col._collection.count()

    def is_populated(self) -> bool:
        """Return True if the collection has at least one embedded chunk."""
        return self.count() > 0

    def build(self, laws: list[Law], batch_sleep: float = 0.0) -> int:
        """Embed laws into Chroma, skipping IDs that already exist.

        Returns the number of newly added chunks.
        """
        docs, ids, metas = _collect(laws)
        total = len(docs)
        added = 0
        with tqdm(total=total, unit="chunk") as pbar:
            for i in range(0, total, _BATCH_SIZE):
                b_docs = docs[i:i + _BATCH_SIZE]
                b_ids = ids[i:i + _BATCH_SIZE]
                b_metas = metas[i:i + _BATCH_SIZE]

                # Chroma.get(ids=b_ids) 會去 ChromaDB 查詢有存在哪些 id了
                # A dict with the keys `"ids"`, `"embeddings"`, `"metadatas"`,
                # `"documents"`.
                existing: set[str] = set(self._col.get(ids=b_ids)["ids"] or [])
                n_docs, n_ids, n_metas = _filter_new(
                    b_docs, b_ids, b_metas, existing
                )
                if n_ids:
                    self._col.add_texts(
                        texts=n_docs,
                        ids=n_ids,
                        metadatas=n_metas,
                    )
                    added += len(n_ids)
                    time.sleep(batch_sleep)
                pbar.update(len(b_docs))
        return added

    def clear(self) -> None:
        """Delete and recreate the collection, wiping all embedded data."""
        self._col.delete_collection()
        self._col = self._make_col()

    def peek(self, n: int = 3) -> list[dict[str, object]]:
        """Return n sample entries without triggering embedding."""
        raw = self._col.get(limit=n, include=["documents", "metadatas"])
        raw_ids: list[str] = raw["ids"] or []
        raw_docs: list[str] = raw["documents"] or []
        raw_metas: list[dict[str, str]] = raw["metadatas"] or []
        out: list[dict[str, object]] = []
        for i, doc in enumerate(raw_docs):
            meta: dict[str, str] = raw_metas[i] if i < len(raw_metas) else {}
            out.append(
                {
                    "id": raw_ids[i] if i < len(raw_ids) else "",
                    "document": doc,
                    "metadata": meta,
                }
            )
        return out

    def search(self, query: str, k: int = 5) -> list[dict[str, object]]:
        """Embed query and return top-k articles ranked by similarity score."""
        results = self._col.similarity_search_with_score(query, k=k)
        return [
            {
                "node_id": (
                    f"{doc.metadata['pcode']}" f"#{doc.metadata['article_no']}"
                ),
                "law_name": doc.metadata["law_name"],
                "article_no": doc.metadata["article_no"],
                "content": doc.page_content,
                "score": score,
            }
            for doc, score in results
        ]
