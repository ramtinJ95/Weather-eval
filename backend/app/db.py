from typing import cast

from google.cloud import firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot

from app.config import settings
from app.schemas import HelloSource


def read_hello_message() -> tuple[str, HelloSource]:
    if not settings.firestore_project_id:
        return settings.default_hello_message, "default"

    try:
        client = firestore.Client(project=settings.firestore_project_id)
        doc_ref = client.collection(settings.firestore_collection).document(
            settings.firestore_document
        )
        doc = cast(DocumentSnapshot, doc_ref.get())

        if not doc.exists:
            return settings.default_hello_message, "default"

        payload = doc.to_dict() or {}
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return settings.default_hello_message, "default"

        return message, "firestore"
    except Exception:
        return settings.default_hello_message, "error"
