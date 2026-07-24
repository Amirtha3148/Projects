"""
Database module for CopChatbot.
Handles PostgreSQL connectivity, schema initialization, and CRUD operations
for intents and chat history.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    """Return a new psycopg2 connection using .env credentials."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "copchatbot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Schema initialization (idempotent)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS intents (
    id SERIAL PRIMARY KEY,
    tag VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intent_patterns (
    id SERIAL PRIMARY KEY,
    intent_id INTEGER REFERENCES intents(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intent_responses (
    id SERIAL PRIMARY KEY,
    intent_id INTEGER REFERENCES intents(id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL,
    response TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    input_mode VARCHAR(10) DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Intents – read from DB
# ---------------------------------------------------------------------------

def load_intents_from_db():
    """
    Query intents, patterns and responses from PostgreSQL and return them in
    the same dict format that the chatbot originally loaded from intents.json:

        {"intents": [
            {
                "tag": "...",
                "patterns": ["..."],
                "responses": {"en": ["..."], "ta": ["..."]}
            },
            ...
        ]}
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Fetch all intents
            cur.execute("SELECT id, tag FROM intents ORDER BY id")
            intent_rows = cur.fetchall()

            intents_list = []
            for row in intent_rows:
                intent_id = row["id"]
                tag = row["tag"]

                # Patterns
                cur.execute(
                    "SELECT pattern FROM intent_patterns WHERE intent_id = %s",
                    (intent_id,),
                )
                patterns = [r["pattern"] for r in cur.fetchall()]

                # Responses grouped by language
                cur.execute(
                    "SELECT language, response FROM intent_responses WHERE intent_id = %s",
                    (intent_id,),
                )
                responses: dict[str, list[str]] = {}
                for resp_row in cur.fetchall():
                    lang = resp_row["language"]
                    responses.setdefault(lang, []).append(resp_row["response"])

                intents_list.append({
                    "tag": tag,
                    "patterns": patterns,
                    "responses": responses,
                })

        return {"intents": intents_list}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Intents – insert (used by migration script)
# ---------------------------------------------------------------------------

def insert_intent(tag, patterns, responses):
    """
    Insert a single intent with its patterns and responses.

    Parameters
    ----------
    tag : str
    patterns : list[str]
    responses : dict[str, list[str]]   e.g. {"en": [...], "ta": [...]}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO intents (tag) VALUES (%s) ON CONFLICT (tag) DO NOTHING RETURNING id",
                (tag,),
            )
            result = cur.fetchone()
            if result is None:
                # Already exists – fetch its id
                cur.execute("SELECT id FROM intents WHERE tag = %s", (tag,))
                intent_id = cur.fetchone()[0]
            else:
                intent_id = result[0]

            # Patterns
            for pattern in patterns:
                cur.execute(
                    "INSERT INTO intent_patterns (intent_id, pattern) VALUES (%s, %s)",
                    (intent_id, pattern),
                )

            # Responses
            for lang, resp_list in responses.items():
                for resp in resp_list:
                    cur.execute(
                        "INSERT INTO intent_responses (intent_id, language, response) VALUES (%s, %s, %s)",
                        (intent_id, lang, resp),
                    )

        conn.commit()
        return intent_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def get_or_create_session(session_id, language="en"):
    """
    Return the DB primary key for the given session_id.
    Creates a new row if one doesn't exist yet.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM chat_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if row:
                return row[0]

            cur.execute(
                "INSERT INTO chat_sessions (session_id, language) VALUES (%s, %s) RETURNING id",
                (session_id, language),
            )
            conn.commit()
            return cur.fetchone()[0]
    finally:
        conn.close()


def save_chat_message(session_id, role, message, input_mode="text"):
    """
    Persist a single chat message.

    Parameters
    ----------
    session_id : int   – DB primary key from get_or_create_session()
    role       : str   – 'user' or 'bot'
    message    : str
    input_mode : str   – 'text' or 'voice'
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chat_messages (session_id, role, message, input_mode)
                   VALUES (%s, %s, %s, %s)""",
                (session_id, role, message, input_mode),
            )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(session_id):
    """
    Fetch all messages for a DB session id, ordered chronologically.

    Returns a list of dicts: [{"role": ..., "message": ..., "input_mode": ..., "created_at": ...}, ...]
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT role, message, input_mode, created_at
                   FROM chat_messages
                   WHERE session_id = %s
                   ORDER BY created_at ASC""",
                (session_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()
