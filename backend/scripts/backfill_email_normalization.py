
import argparse
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.email_identity import normalize_email

def _users_collection():
    from services.firestore_service import db

    return db.collection("users")

def _all_user_docs() -> List[Any]:
    collection = _users_collection()

    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            return list(stream())
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return []
    return [collection.document(doc_id) for doc_id in list(store.keys())]

def plan() -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    rewrites: List[Dict[str, str]] = []
    by_canonical: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for doc in _all_user_docs():
        data = doc.to_dict() or {}
        stored = data.get("email")
        if not stored:
            continue

        canonical = normalize_email(stored)
        by_canonical[canonical].append({"id": doc.id, "email": stored})
        if stored != canonical:
            rewrites.append({"id": doc.id, "from": stored, "to": canonical})

    collisions = [
        {"email": canonical, "documents": docs}
        for canonical, docs in sorted(by_canonical.items())
        if len(docs) > 1
    ]

    colliding_ids = {
        entry["id"] for collision in collisions for entry in collision["documents"]
    }
    rewrites = [row for row in rewrites if row["id"] not in colliding_ids]

    return rewrites, collisions

def apply(rewrites: List[Dict[str, str]]) -> int:
    collection = _users_collection()
    written = 0
    for row in rewrites:
        try:
            collection.document(row["id"]).update({"email": row["to"]})
            written += 1
        except Exception as exc:
            print(f"  ! {row['id']}: {exc}", file=sys.stderr)
    return written

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write. Without it this is a dry run.",
    )
    args = parser.parse_args(argv)

    rewrites, collisions = plan()

    if collisions:
        print(f"{len(collisions)} address(es) held by more than one account:")
        for collision in collisions:
            ids = ", ".join(
                f"{entry['id']} ({entry['email']})" for entry in collision["documents"]
            )
            print(f"  {collision['email']}: {ids}")
        print(
            "\nThese are separate accounts with separate cycle histories. "
            "Merging them is a decision about someone's health data, not a "
            "migration step — resolve them by hand, then re-run.\n"
        )

    if not rewrites:
        print("Nothing to rewrite." if not collisions else "No safe rewrites.")
        return 1 if collisions else 0

    print(f"{len(rewrites)} document(s) to canonicalise:")
    for row in rewrites:
        print(f"  {row['id']}: {row['from']} -> {row['to']}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 1 if collisions else 0

    written = apply(rewrites)
    print(f"\nRewrote {written}/{len(rewrites)}.")
    return 1 if (collisions or written != len(rewrites)) else 0

if __name__ == "__main__":
    raise SystemExit(main())
