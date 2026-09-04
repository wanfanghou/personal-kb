"""SQLite connection lifecycle for the lineage app."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = current_app.config["DATABASE"]
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app) -> None:
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate_schema(db)
        db.commit()


def _migrate_schema(db: sqlite3.Connection) -> None:
    """Add columns that were introduced after the initial schema release."""
    person_columns = {row["name"] for row in db.execute("PRAGMA table_info(persons)")}
    person_additions = {
        "title": "TEXT",
        "editorial_roles_json": "TEXT NOT NULL DEFAULT '[]'",
        "honors_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for column, definition in person_additions.items():
        if column not in person_columns:
            db.execute(f"ALTER TABLE persons ADD COLUMN {column} {definition}")

    mentorship_columns = {row["name"] for row in db.execute("PRAGMA table_info(mentorships)")}
    if "student_placement" not in mentorship_columns:
        db.execute("ALTER TABLE mentorships ADD COLUMN student_placement TEXT")

    submission_columns = {row["name"] for row in db.execute("PRAGMA table_info(submissions)")}
    if "review_note" not in submission_columns:
        db.execute("ALTER TABLE submissions ADD COLUMN review_note TEXT")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
