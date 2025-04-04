# schema.py
import sqlite3

from utils.io import import_from_legacy_json


def init_db(db_path="AIEditor.sqlite3"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    is_new = not tables

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # Core tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY,
        book_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        order_idx REAL NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY,
        part_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        title_translations TEXT DEFAULT '{}',
        order_idx REAL NOT NULL,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        id INTEGER PRIMARY KEY,
        chapter_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        content_translations TEXT DEFAULT '{}',
        revision_status TEXT DEFAULT 'unreviewed',
        last_edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        order_idx REAL NOT NULL,
        FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_feedback (
        id INTEGER PRIMARY KEY,
        scene_id INTEGER NOT NULL,
        feedback_type TEXT NOT NULL,
        feedback_text TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_pending BOOLEAN DEFAULT 0,
        FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
    )""")

    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_order ON scenes(chapter_id, order_idx)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_status ON scenes(revision_status)")

    conn.commit()

    if is_new:
        from pathlib import Path
        json_path = Path.home() / "Documents" / "Jona" / "wordpress" / 'Cronache_della_Nuova_Terra.json'
        if not json_path.exists():
            raise FileNotFoundError(f"Required file not found at: {json_path}")
        import_from_legacy_json(conn, str(json_path))

    return conn