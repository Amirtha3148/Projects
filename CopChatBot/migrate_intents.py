"""
migrate_intents.py
------------------
One-time migration script to seed the PostgreSQL database from intents.json.

Usage:
    python migrate_intents.py
"""

import json
import db


def main():
    print("[*] Initializing database schema...")
    db.init_db()
    print("[OK] Schema ready.\n")

    # Load intents from JSON
    with open("intents.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    intent_count = 0
    pattern_count = 0
    response_count = 0

    for intent in data["intents"]:
        tag = intent["tag"]
        patterns = intent["patterns"]
        responses = intent["responses"]

        db.insert_intent(tag, patterns, responses)

        intent_count += 1
        pattern_count += len(patterns)
        for lang_responses in responses.values():
            response_count += len(lang_responses)

        print(f"  [OK] Migrated intent: {tag} "
              f"({len(patterns)} patterns, "
              f"{sum(len(v) for v in responses.values())} responses)")

    print(f"\n[OK] Migration complete!")
    print(f"   Intents:   {intent_count}")
    print(f"   Patterns:  {pattern_count}")
    print(f"   Responses: {response_count}")


if __name__ == "__main__":
    main()
