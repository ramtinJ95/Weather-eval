from google.cloud import firestore

from app.config import settings


def main() -> None:
    if not settings.firestore_project_id:
        raise RuntimeError("Set WEATHER_EVAL_FIRESTORE_PROJECT_ID before seeding Firestore.")

    client = firestore.Client(project=settings.firestore_project_id)
    doc_ref = client.collection(settings.firestore_collection).document(settings.firestore_document)

    doc_ref.set({"message": "Hello from Firestore 🎉"})
    print(
        f"Seeded {settings.firestore_collection}/{settings.firestore_document} in "
        f"project {settings.firestore_project_id}"
    )


if __name__ == "__main__":
    main()
