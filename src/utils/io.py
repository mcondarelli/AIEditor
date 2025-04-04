# io_utils.py
import json
import sqlite3

from utils.logging_config import LoggingConfig

log = LoggingConfig.get_logger('_DB_', _default=4)

def import_from_legacy_json(db_conn: sqlite3.Connection, json_path:str) -> None:
    """Migrate from old nested JSON to SQLite."""
    with open(json_path) as f:
        old_data = json.load(f)

    cursor = db_conn.cursor()

    # Insert books/parts/chapters with order_idx gaps
    order = 1000
    for book_title, parts in old_data.items():
        cursor.execute(
            "INSERT INTO books (title) VALUES (?) RETURNING id",
            (book_title,)
        )
        book_id = cursor.fetchone()[0]
        log.debug(f'Book{book_id:05d}: {cursor.lastrowid}')

        for part_title, chapters in parts.items():
            cursor.execute(
                "INSERT INTO parts (book_id, title, order_idx) VALUES (?, ?, ?) RETURNING id",
                (book_id, part_title, order)
            )
            part_id = cursor.fetchone()[0]
            log.debug(f'    Part{part_id:05d}: {cursor.lastrowid}')
            order += 1000

            for chapter_title, scenes in chapters.items():
                cursor.execute(
                    "INSERT INTO chapters (part_id, title, order_idx) VALUES (?, ?, ?) RETURNING id",
                    (part_id, chapter_title, order)
                )
                chapter_id = cursor.fetchone()[0]
                log.debug(f'        Chapter{chapter_id:05d}: {cursor.lastrowid}')
                order += 1000

                for scene_title, lines in scenes.items():
                    cursor.execute(
                        "INSERT INTO scenes (chapter_id, title, order_idx, content) VALUES (?, ?, ?, ?) RETURNING id",
                        (chapter_id, scene_title, order, '\n'.join(lines))
                    )
                    scene_id = cursor.fetchone()[0]
                    log.debug(f'            Scene{scene_id:05d}: {cursor.lastrowid}')
                    order += 1000
    db_conn.commit()

def export_to_legacy_json(db_conn, output_path):
    """Generate old JSON format for compatibility."""
    cursor = db_conn.cursor()
    result = {}

    cursor.execute("SELECT id, title FROM books")
    for book_id, book_title in cursor.fetchall():
        result[book_title] = {}

        cursor.execute("""
            SELECT id, title FROM parts 
            WHERE book_id = ? ORDER BY order_idx
        """, (book_id,))
        # ... nested reconstruction ...
        raise NotImplemented()

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
