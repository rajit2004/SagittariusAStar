import firebase_admin
from firebase_admin import firestore, credentials
import os
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from google.api_core.exceptions import FailedPrecondition

logger = logging.getLogger(__name__)

from google.cloud.firestore_v1 import DELETE_FIELD

from core.errors import upstream_error

from core.email_identity import normalize_email

class MockNotFound(Exception):
    pass

class MockDocumentReference:
    def __init__(self, doc_id, data, collection):
        self.id = doc_id
        self.data = data
        self.collection = collection
        self.exists = data is not None

    def get(self):
        return self

    def to_dict(self):
        return self.data.copy() if self.data is not None else None

    def update(self, update_data):
        if not self.exists or self.data is None:
            raise MockNotFound(
                f"No document to update: {self.collection.name}/{self.id}"
            )
        merged = dict(self.data)
        for key, value in _copy_document(update_data).items():
            if value is DELETE_FIELD:
                merged.pop(key, None)
            else:
                merged[key] = value
        self.data = merged
        self.collection.store[self.id] = merged

    def set(self, document_data):
        if document_data and any(
            value is DELETE_FIELD for value in document_data.values()
        ):
            raise ValueError(
                "DELETE_FIELD cannot be used in set(); omit the field instead"
            )
        stored = _copy_document(document_data)
        self.collection.store[self.id] = stored
        self.data = stored
        self.exists = True

    def delete(self):
        if self.id in self.collection.store:
            del self.collection.store[self.id]

        self.data = None
        self.exists = False

def _copy_document(data):
    return dict(data) if data is not None else None

def _mock_order_key(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    return value

_MOCK_OPERATORS = {
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
    ">": lambda left, right: left is not None and left > right,
    ">=": lambda left, right: left is not None and left >= right,
    "<": lambda left, right: left is not None and left < right,
    "<=": lambda left, right: left is not None and left <= right,
}

class MockQuery:

    def __init__(self, documents):
        self._documents = documents
        self._order_by_field = None
        self._order_by_direction = None
        self._limit_count = None
        self._offset_count = 0

    def _derive(self, documents=None):
        clone = MockQuery(self._documents if documents is None else documents)
        clone._order_by_field = self._order_by_field
        clone._order_by_direction = self._order_by_direction
        clone._limit_count = self._limit_count
        clone._offset_count = self._offset_count
        return clone

    def limit(self, count):
        clone = self._derive()
        clone._limit_count = count
        return clone

    def offset(self, count):
        clone = self._derive()
        clone._offset_count = count
        return clone

    def order_by(self, field, direction=None):
        clone = self._derive()
        clone._order_by_field = field
        clone._order_by_direction = direction or firestore.Query.ASCENDING
        return clone

    def where(self, field, op, value):
        compare = _MOCK_OPERATORS.get(op)
        if compare is None:
            raise NotImplementedError(f"MockQuery does not support the {op!r} operator")

        filtered = [
            doc for doc in self._documents if compare((doc.data or {}).get(field), value)
        ]
        return self._derive(filtered)

    def count(self):
        class _CountAggregation:
            def __init__(self, count_val):
                self.val = count_val

            def get(self):

                class ResultObj:
                    def __init__(self, v):
                        self.value = v
                return [[ResultObj(self.val)]]
        return _CountAggregation(len(self._documents))

    def stream(self):
        docs = self._documents[:]

        if self._order_by_field:
            reverse = (
                self._order_by_direction
                == firestore.Query.DESCENDING
            )

            docs.sort(
                key=lambda doc: _mock_order_key((doc.data or {}).get(self._order_by_field)),
                reverse=reverse
            )

        if self._offset_count:
            docs = docs[self._offset_count:]

        if self._limit_count is not None:
            docs = docs[:self._limit_count]

        for doc in docs:
            yield doc

class MockCollectionReference:
    def __init__(self, name, db):
        self.name = name
        self.db = db

        if name not in db._collections:
            db._collections[name] = {}

        self.store = db._collections[name]

    def add(self, document_data):
        next_id = self.db._counters.get(self.name, 0) + 1
        self.db._counters[self.name] = next_id

        doc_id = f"mock-doc-id-{next_id}"

        stored = _copy_document(document_data)
        self.store[doc_id] = stored
        return (None, MockDocumentReference(doc_id, stored, self))

    def document(self, doc_id):
        data = self.store.get(doc_id)

        return MockDocumentReference(
            doc_id,
            data,
            self,
        )

    def _all_documents(self):
        return [
            MockDocumentReference(doc_id, data, self)
            for doc_id, data in list(self.store.items())
        ]

    def stream(self):
        yield from self._all_documents()

    def where(self, field, op, value):
        return MockQuery(self._all_documents()).where(field, op, value)

    def count(self):
        return MockQuery(self._all_documents()).count()

    def order_by(self, field, direction=None):
        return MockQuery(self._all_documents()).order_by(field, direction)

    def limit(self, count):
        return MockQuery(self._all_documents()).limit(count)

    def offset(self, count):
        return MockQuery(self._all_documents()).offset(count)

class MockFirestoreClient:
    def __init__(self):
        self._collections = {}
        self._counters = {}

    def collection(self, name):
        return MockCollectionReference(name, self)

db = None

def initialize_firebase():
    global db

    if firebase_admin._apps:
        db = firestore.client()
        return

    cred_json = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON"
    )

    if cred_json:
        cred = credentials.Certificate(
            json.loads(cred_json)
        )
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return

    cred_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH"
    )

    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return

    import sys

    print(
        "WARNING: Firebase credentials not found. "
        "Falling back to an in-memory mock Firestore database.",
        file=sys.stderr,
    )

    db = MockFirestoreClient()

initialize_firebase()

class UserService:

    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> str:
        try:
            now = datetime.now(timezone.utc)
            if user_data.get("email") is not None:
                user_data["email"] = normalize_email(user_data["email"])
            user_data["created_at"] = now
            user_data["updated_at"] = now

            doc_ref = db.collection(
                "users"
            ).add(user_data)

            return doc_ref[1].id

        except Exception as e:
            raise upstream_error("Creating your account", e)

    @staticmethod
    def get_user_by_username(
        username: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            users = (
                db.collection("users")
                .where("username", "==", username)
                .limit(1)
                .stream()
            )

            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data

            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def _first_user_where(field: str, value: Any) -> Optional[Dict[str, Any]]:
        for user in db.collection("users").where(field, "==", value).limit(1).stream():
            data = user.to_dict()
            data["id"] = user.id
            return data
        return None

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        try:
            normalized = normalize_email(email)
            user = UserService._first_user_where("email", normalized)
            if user is not None:
                return user

            raw = (email or "").strip()
            if raw and raw != normalized:
                return UserService._first_user_where("email", raw)
            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def get_user_by_phone(
        phone: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            users = (
                db.collection("users")
                .where("phone", "==", phone)
                .limit(1)
                .stream()
            )

            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data

            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def get_user_by_id(
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            doc = (
                db.collection("users")
                .document(user_id)
                .get()
            )

            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                return data

            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def update_user(user_id: str, update_data: Dict[str, Any]) -> bool:
        try:
            if update_data.get("email") is not None:
                update_data["email"] = normalize_email(update_data["email"])
            update_data["updated_at"] = datetime.now(timezone.utc)
            doc_ref = db.collection("users").document(user_id)
            doc_ref.update(update_data)

            return True

        except Exception as e:
            raise upstream_error("Saving your profile", e)

    @staticmethod
    def delete_user(user_id: str) -> Dict[str, int]:
        try:
            from services.data_privacy_service import purge_user_data

            return purge_user_data(user_id)
        except Exception as e:
            raise upstream_error("Deleting your account", e)

class CycleService:

    @staticmethod
    def create_log(
        user_id: str,
        log_data: Dict[str, Any],
    ) -> str:
        try:
            data = dict(log_data)

            for key, value in list(data.items()):
                if (
                    isinstance(value, date)
                    and not isinstance(value, datetime)
                ):
                    data[key] = datetime.combine(
                        value,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )

            data["user_id"] = user_id
            data["created_at"] = datetime.now(
                timezone.utc
            )

            doc_ref = (
                db.collection("cycle_logs")
                .add(data)
            )

            return doc_ref[1].id

        except Exception as e:
            raise upstream_error("Saving your cycle log", e)

    @staticmethod
    def _as_day_start(value) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    @staticmethod
    def get_logs_page(
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        start_date=None,
        end_date=None,
    ) -> tuple:
        try:
            query = db.collection("cycle_logs").where("user_id", "==", user_id)

            if start_date is not None:
                query = query.where(
                    "start_date", ">=", CycleService._as_day_start(start_date)
                )
            if end_date is not None:
                query = query.where(
                    "start_date", "<=", CycleService._as_day_start(end_date)
                )

            try:

                total_count = query.count().get()[0][0].value
            except AttributeError:

                total_count = len(list(query.stream()))

            query = query.order_by(
                "start_date", direction=firestore.Query.DESCENDING
            )

            fetch_offset = max(0, offset - 1) if offset > 0 else 0
            extra_fetch = 1 if offset > 0 else 0

            if offset:
                query = query.offset(fetch_offset)

            query = query.limit(limit + extra_fetch + 1)

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)

            has_more = len(results) > limit + extra_fetch

            results = results[:limit + extra_fetch]

            for i in range(len(results) - 1, -1, -1):
                if i > 0:
                    curr_date = CycleService._as_day_start(results[i]["start_date"])
                    next_date = CycleService._as_day_start(results[i - 1]["start_date"])
                    results[i]["cycle_length"] = (next_date - curr_date).days
                else:

                    results[i]["cycle_length"] = None

            if extra_fetch and results:

                results.pop(0)

            return results, has_more, total_count
        except FailedPrecondition as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e)
            )
        except HTTPException:
            raise
        except Exception as e:
            raise upstream_error("Loading your cycle history", e)

    @staticmethod
    def get_logs_for_user(user_id: str, limit: int = 10) -> list:
        try:
            query = (
                db.collection("cycle_logs")
                .where("user_id", "==", user_id)
                .order_by(
                    "start_date",
                    direction=firestore.Query.DESCENDING,
                )
                .limit(limit)
            )

            docs = query.stream()
            results = []

            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)

            return results

        except FailedPrecondition as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )

        except Exception as e:

            raise upstream_error("Loading your cycle history", e)

    @staticmethod
    def _log_doc_id(
        user_id: str,
        log_date: date,
    ) -> str:
        return f"{user_id}_{log_date.isoformat()}"

    @staticmethod
    def _prepare_write(fields: Dict[str, Any], *, for_new_document: bool) -> Dict[str, Any]:
        prepared: Dict[str, Any] = {}
        for key, value in fields.items():
            if value is None:
                if not for_new_document:
                    prepared[key] = DELETE_FIELD
                continue
            if isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(
                    value, datetime.min.time(), tzinfo=timezone.utc
                )
            prepared[key] = value
        return prepared

    @staticmethod
    def upsert_log(user_id: str, log_date: date, fields: Dict[str, Any]) -> str:
        try:
            doc_id = CycleService._log_doc_id(
                user_id,
                log_date,
            )

            doc_ref = (
                db.collection("cycle_logs")
                .document(doc_id)
            )

            existing = doc_ref.get()

            day_start = datetime.combine(
                log_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )

            now = datetime.now(timezone.utc)

            if existing.exists:
                update_fields = CycleService._prepare_write(
                    fields, for_new_document=False
                )
                update_fields["updated_at"] = now
                doc_ref.update(update_fields)

                return doc_id

            new_data = {
                **CycleService._prepare_write(fields, for_new_document=True),
                "user_id": user_id,
                "start_date": day_start,
                "created_at": now,
            }
            doc_ref.set(new_data)

            return doc_id

        except Exception as e:
            raise upstream_error("Saving your cycle log", e)

    @staticmethod
    def get_log(user_id: str, log_id: str) -> Dict[str, Any]:
        try:
            doc = db.collection("cycle_logs").document(log_id).get()

            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found"
                )

            data = doc.to_dict() or {}
            if data.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this log"
                )

            data["id"] = doc.id
            return data
        except HTTPException:
            raise
        except Exception as e:
            raise upstream_error("Loading your cycle log", e)

    @staticmethod
    def update_log(user_id: str, log_id: str, fields: Dict[str, Any]) -> str:
        try:
            doc_ref = (
                db.collection("cycle_logs")
                .document(log_id)
            )

            doc = doc_ref.get()

            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found",
                )

            if doc.to_dict().get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Not authorized to update this log"
                    ),
                )

            update_fields = CycleService._prepare_write(
                fields, for_new_document=False
            )
            update_fields["updated_at"] = datetime.now(timezone.utc)
            doc_ref.update(update_fields)

            return log_id

        except HTTPException:
            raise

        except Exception as e:
            raise upstream_error("Updating your cycle log", e)

    @staticmethod
    def delete_log(
        user_id: str,
        log_id: str,
    ) -> None:
        try:
            doc_ref = (
                db.collection("cycle_logs")
                .document(log_id)
            )

            doc = doc_ref.get()

            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found",
                )

            if doc.to_dict().get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Not authorized to delete this log"
                    ),
                )

            doc_ref.delete()

        except HTTPException:
            raise

        except Exception as e:
            raise upstream_error("Deleting your cycle log", e)

MAX_CONVERSATION_MESSAGES = 50

class AssistantConversationService:

    COLLECTION = "conversations"

    @staticmethod
    def get_or_create(user_id: str) -> dict:
        now = datetime.now(timezone.utc)

        doc_ref = (
            db.collection(
                AssistantConversationService.COLLECTION
            )
            .document(user_id)
        )

        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()

        conversation = {
            "user_id": user_id,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }

        doc_ref.set(conversation)

        return conversation

    @staticmethod
    def get_recent_messages(
        user_id: str,
        limit: int = 10,
    ) -> list:
        conversation = (
            AssistantConversationService.get_or_create(
                user_id
            )
        )

        return conversation.get(
            "messages",
            [],
        )[-limit:]

    @staticmethod
    def add_messages(
        user_id: str,
        new_messages: list,
    ) -> None:
        now = datetime.now(timezone.utc)

        doc_ref = (
            db.collection(
                AssistantConversationService.COLLECTION
            )
            .document(user_id)
        )

        doc = doc_ref.get()

        if not doc.exists:
            conversation = {
                "user_id": user_id,
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }

            doc_ref.set(conversation)
            doc = doc_ref.get()

        current = doc.to_dict().get(
            "messages",
            [],
        )

        current.extend(new_messages)

        if len(current) > MAX_CONVERSATION_MESSAGES:
            current = current[
                -MAX_CONVERSATION_MESSAGES:
            ]

        doc_ref.update(
            {
                "messages": current,
                "updated_at": now,
            }
        )
