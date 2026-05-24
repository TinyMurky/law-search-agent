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
            metas.append({
                "pcode": article.pcode,
                "article_no": article.article_no,
                "law_name": article.law_name,
                "law_modified_date": law.law_modified_date,
            })
    return docs, ids, metas


class ChunkBuilder:
    """Builds and queries the Chroma 'chunks' collection."""

    def __init__(
        self, persist_directory: str, embeddings: Embeddings
    ) -> None:
        self._persist_dir = persist_directory
        self._embeddings = embeddings
        self._col = self._make_col()

    def _make_col(self) -> Chroma:
        return Chroma(
            collection_name=_COLLECTION_NAME,
            persist_directory=self._persist_dir,
            embedding_function=self._embeddings,
        )

    def count(self) -> int:
        return self._col._collection.count()

    def is_populated(self) -> bool:
        return self.count() > 0

    def build(
        self, laws: list[Law], batch_sleep: float = 0.0
    ) -> int:
        docs, ids, metas = _collect(laws)
        total = len(docs)
        with tqdm(total=total, unit="chunk") as pbar:
            for i in range(0, total, _BATCH_SIZE):
                batch = docs[i:i + _BATCH_SIZE]
                self._col.add_texts(
                    texts=batch,
                    ids=ids[i:i + _BATCH_SIZE],
                    metadatas=metas[i:i + _BATCH_SIZE],
                )
                pbar.update(len(batch))
                time.sleep(batch_sleep)
        return total

    def clear(self) -> None:
        self._col.delete_collection()
        self._col = self._make_col()

    def peek(self, n: int = 3) -> list[dict[str, object]]:
        raw = self._col.get(
            limit=n, include=["documents", "metadatas"]
        )
        raw_ids: list[str] = raw["ids"] or []
        raw_docs: list[str] = raw["documents"] or []
        raw_metas: list[dict[str, str]] = raw["metadatas"] or []
        out: list[dict[str, object]] = []
        for i, doc in enumerate(raw_docs):
            meta: dict[str, str] = (
                raw_metas[i] if i < len(raw_metas) else {}
            )
            out.append({
                "id": raw_ids[i] if i < len(raw_ids) else "",
                "document": doc,
                "metadata": meta,
            })
        return out

    def search(
        self, query: str, k: int = 5
    ) -> list[dict[str, object]]:
        results = self._col.similarity_search_with_score(
            query, k=k
        )
        return [
            {
                "node_id": (
                    f"{doc.metadata['pcode']}"
                    f"#{doc.metadata['article_no']}"
                ),
                "law_name": doc.metadata["law_name"],
                "article_no": doc.metadata["article_no"],
                "content": doc.page_content,
                "score": score,
            }
            for doc, score in results
        ]
