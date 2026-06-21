"""
src/storage/mongodb_writer.py
================================
Optional MongoDB storage backend.
Gracefully degrades if ``pymongo`` is not installed or the connection fails.
"""

from __future__ import annotations

from typing import Iterable, Optional

from src.schemas.article_schema import Article
from src.utils.logger import get_logger

logger = get_logger("storage.mongodb")

try:
    import pymongo
    from pymongo import MongoClient, UpdateOne
    from pymongo.errors import BulkWriteError, ConnectionFailure, PyMongoError
    _HAS_PYMONGO = True
except ImportError:
    _HAS_PYMONGO = False
    logger.warning("pymongo not installed — MongoDB storage disabled.")


class MongoDBWriter:
    """
    Upserts articles into a MongoDB collection.

    The ``article_id`` (SHA-256 URL hash) is used as the unique ``_id``
    so re-scraping the same URL updates the existing document.

    Parameters
    ----------
    uri:
        MongoDB connection string.
    db_name:
        Target database name.
    collection_name:
        Target collection name.
    """

    def __init__(
        self,
        uri: str,
        db_name: str,
        collection_name: str,
    ) -> None:
        if not _HAS_PYMONGO:
            raise RuntimeError("pymongo is required for MongoDB storage.")
        self._client: "MongoClient" = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._collection = self._client[db_name][collection_name]
        self._ensure_indexes()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, article: Article) -> bool:
        """
        Upsert a single article document.

        Returns
        -------
        bool
            ``True`` on success.
        """
        doc = self._to_doc(article)
        try:
            self._collection.update_one(
                {"_id": article.article_id},
                {"$set": doc},
                upsert=True,
            )
            logger.debug("Upserted article %s", article.article_id[:12])
            return True
        except PyMongoError as exc:
            logger.error("MongoDB write error: %s", exc)
            return False

    def write_many(self, articles: Iterable[Article]) -> int:
        """
        Bulk-upsert multiple articles.

        Returns
        -------
        int
            Number of articles successfully written.
        """
        ops: list["UpdateOne"] = [
            UpdateOne(
                {"_id": a.article_id},
                {"$set": self._to_doc(a)},
                upsert=True,
            )
            for a in articles
        ]
        if not ops:
            return 0
        try:
            result = self._collection.bulk_write(ops, ordered=False)
            written = result.upserted_count + result.modified_count
            logger.info("MongoDB bulk write | %d ops | written=%d", len(ops), written)
            return written
        except BulkWriteError as exc:
            logger.error("MongoDB bulk write partial failure: %s", exc.details)
            return exc.details.get("nUpserted", 0) + exc.details.get("nModified", 0)

    def find_by_id(self, article_id: str) -> Optional[dict]:
        """Retrieve a document by its article_id."""
        return self._collection.find_one({"_id": article_id})

    def count(self) -> int:
        """Return total document count in the collection."""
        return self._collection.count_documents({})

    def close(self) -> None:
        """Close the MongoDB client connection."""
        self._client.close()

    def __enter__(self) -> "MongoDBWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _to_doc(self, article: Article) -> dict:
        data = article.model_dump()
        data["_id"] = data.pop("article_id")
        # Convert nested Pydantic objects to plain dicts
        return data

    def _ensure_indexes(self) -> None:
        try:
            self._collection.create_index("url", unique=False)
            self._collection.create_index("published_at")
            self._collection.create_index("source")
            self._collection.create_index("status")
            logger.debug("MongoDB indexes ensured.")
        except PyMongoError as exc:
            logger.warning("Could not create MongoDB indexes: %s", exc)
