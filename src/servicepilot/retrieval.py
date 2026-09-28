"""Local policy RAG with deterministic embeddings and version-aware filtering."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from servicepilot.paths import POLICY_DIR


@dataclass(frozen=True, slots=True)
class Evidence:
    document_id: str
    title: str
    version: str
    source: str
    snippet: str
    score: float
    effective_date: str

    def as_dict(self) -> dict[str, str | float]:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "version": self.version,
            "source": self.source,
            "snippet": self.snippet,
            "score": round(self.score, 4),
            "effective_date": self.effective_date,
        }


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    latin = re.findall(r"[a-z0-9_-]+", normalized)
    chinese = re.findall(r"[\u4e00-\u9fff]", normalized)
    grams = chinese + ["".join(chinese[index : index + 2]) for index in range(max(0, len(chinese) - 1))]
    return latin + grams


class LocalHashEmbeddings(Embeddings):
    """Dependency-free embeddings for the offline demo; replaceable by provider embeddings."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self.dimensions
            vector[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def parse_policy(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"政策文档缺少 front matter：{path}")
    _, metadata_text, content = raw.split("---", 2)
    metadata: dict[str, str] = {}
    for line in metadata_text.strip().splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip()
    required = {"id", "title", "version", "effective_date", "status", "region"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise ValueError(f"政策元数据缺少 {missing}：{path}")
    metadata["source"] = path.name
    searchable = f"{metadata.get('title', '')}\n{metadata.get('tags', '')}\n{content.strip()}"
    return Document(page_content=searchable, metadata=metadata, id=metadata["id"])


def load_policies(policy_dir: str | Path = POLICY_DIR) -> list[Document]:
    paths = sorted(Path(policy_dir).glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"未找到政策文档：{policy_dir}")
    return [parse_policy(path) for path in paths]


def is_current(document: Document, *, on_date: date | None = None, region: str = "ALL") -> bool:
    target_date = on_date or date.today()
    metadata = document.metadata
    applies_to_region = metadata.get("region") in {"ALL", region}
    return (
        metadata.get("status") == "active"
        and date.fromisoformat(str(metadata["effective_date"])) <= target_date
        and applies_to_region
    )


class PolicyRetriever:
    def __init__(self, documents: Iterable[Document] | None = None) -> None:
        self.documents = list(documents or load_policies())
        self.vectorstore = InMemoryVectorStore(LocalHashEmbeddings())
        self.vectorstore.add_documents(self.documents, ids=[str(doc.id) for doc in self.documents])

    def search(self, query: str, *, k: int = 3, region: str = "ALL") -> list[Evidence]:
        candidates = self.vectorstore.similarity_search_with_score(query, k=len(self.documents))
        current = [(doc, score) for doc, score in candidates if is_current(doc, region=region)]
        evidence = []
        for document, score in current[: max(1, k)]:
            metadata = document.metadata
            clean_content = re.sub(r"\s+", " ", document.page_content).strip()
            evidence.append(
                Evidence(
                    document_id=str(metadata["id"]),
                    title=str(metadata["title"]),
                    version=str(metadata["version"]),
                    source=str(metadata["source"]),
                    snippet=clean_content[:320],
                    score=float(score),
                    effective_date=str(metadata["effective_date"]),
                )
            )
        return evidence
