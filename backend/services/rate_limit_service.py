
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, List, Optional

from services.firestore_service import db
from utils.logger import logger

LEGACY_MAX_WINDOW_SECONDS = 3600

class RateLimitService:
    COLLECTION = "rate_limits"

    @staticmethod
    def _document(key: str):
        return db.collection(RateLimitService.COLLECTION).document(key)

    @staticmethod
    def _collection():
        return db.collection(RateLimitService.COLLECTION)

    @staticmethod
    def _stream() -> Iterator[Any]:
        collection = RateLimitService._collection()
        stream = getattr(collection, "stream", None)
        if callable(stream):
            try:
                yield from stream()
                return
            except (AttributeError, NotImplementedError, TypeError):
                pass

        store = getattr(collection, "store", None)
        if store is None:
            return
        for doc_id in list(store.keys()):
            yield collection.document(doc_id)

    @staticmethod
    def _as_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    @staticmethod
    def _timestamps_from(data: Any) -> List[datetime]:
        raw = (data or {}).get("timestamps", [])
        if not isinstance(raw, list):
            return []

        parsed = [RateLimitService._as_datetime(entry) for entry in raw]
        return sorted(entry for entry in parsed if entry is not None)

    @staticmethod
    def is_rate_limited(
        key: str,
        limit: int = 5,
        window_seconds: int = 300,
    ) -> Optional[int]:
        now = datetime.now(timezone.utc)
        doc_ref = RateLimitService._document(key)
        doc = doc_ref.get()

        data = (doc.to_dict() or {}) if getattr(doc, "exists", False) else {}
        timestamps = [
            entry
            for entry in RateLimitService._timestamps_from(data)
            if now - entry < timedelta(seconds=window_seconds)
        ]

        if len(timestamps) >= limit:
            oldest = timestamps[0]
            remaining = int(
                (oldest + timedelta(seconds=window_seconds) - now).total_seconds()
            )
            RateLimitService._write(doc_ref, timestamps, window_seconds)
            return max(remaining, 1)

        timestamps.append(now)
        RateLimitService._write(doc_ref, timestamps, window_seconds)
        return None

    @staticmethod
    def _write(doc_ref, timestamps: List[datetime], window_seconds: int) -> None:
        newest = max(timestamps) if timestamps else datetime.now(timezone.utc)
        expires_at = newest + timedelta(seconds=max(int(window_seconds), 1))

        doc_ref.set(
            {
                "timestamps": [entry.isoformat() for entry in timestamps],
                "expires_at": expires_at.isoformat(),
                "window_seconds": int(window_seconds),
            }
        )

    @staticmethod
    def reset(key: str) -> None:
        try:
            doc_ref = RateLimitService._document(key)
            doc_ref.delete()
        except Exception:
            pass

    @staticmethod
    def purge_expired() -> int:
        now = datetime.now(timezone.utc)
        removed = 0

        for doc in list(RateLimitService._stream()):
            data = doc.to_dict() or {}

            expires_at = RateLimitService._as_datetime(data.get("expires_at"))
            if expires_at is None:
                timestamps = RateLimitService._timestamps_from(data)
                if timestamps:
                    expires_at = timestamps[-1] + timedelta(
                        seconds=LEGACY_MAX_WINDOW_SECONDS
                    )

            if expires_at is not None and expires_at > now:
                continue

            try:
                RateLimitService._collection().document(doc.id).delete()
                removed += 1
            except Exception:
                pass

        if removed:
            logger.bind(removed=removed).info("Swept expired rate-limit buckets")
        return removed

    @staticmethod
    def clear_all():
        try:
            if hasattr(db, "_collections"):
                db._collections.pop(RateLimitService.COLLECTION, None)
        except Exception:
            pass
