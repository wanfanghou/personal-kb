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

    _migrate_relationship_types(db)


def _migrate_relationship_types(db: sqlite3.Connection) -> None:
    """Rebuild mentorships when its relationship_type CHECK predates the
    'undergrad' type. The check is dropped entirely; the enum is validated
    in the application layer so new types no longer require a table rebuild.
    """
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'mentorships'"
    ).fetchone()
    if row is None:
        return
    sql = row["sql"] or ""
    has_type_check = "CHECK (relationship_type IN" in sql
    if not has_type_check or "'undergrad'" in sql:
        return
    db.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS mentorships_new;
        CREATE TABLE mentorships_new (
            id TEXT PRIMARY KEY,
            mentor_id TEXT NOT NULL REFERENCES persons(id),
            student_id TEXT NOT NULL REFERENCES persons(id),
            relationship_type TEXT NOT NULL,
            start_year INTEGER,
            end_year INTEGER,
            institution TEXT,
            student_placement TEXT,
            evidence_url TEXT NOT NULL,
            evidence_text TEXT,
            confidence TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (confidence IN ('confirmed', 'probable', 'uncertain')),
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'verified', 'rejected')),
            public INTEGER NOT NULL DEFAULT 0,
            notes_private TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (mentor_id, student_id, relationship_type),
            CHECK (mentor_id <> student_id),
            CHECK (end_year IS NULL OR start_year IS NULL OR end_year >= start_year)
        );
        INSERT INTO mentorships_new
            (id, mentor_id, student_id, relationship_type, start_year, end_year,
             institution, student_placement, evidence_url, evidence_text,
             confidence, status, public, notes_private, created_at, updated_at)
        SELECT
            id, mentor_id, student_id, relationship_type, start_year, end_year,
            institution, student_placement, evidence_url, evidence_text,
            confidence, status, public, notes_private, created_at, updated_at
        FROM mentorships;
        DROP TABLE mentorships;
        ALTER TABLE mentorships_new RENAME TO mentorships;
        CREATE INDEX IF NOT EXISTS idx_mentorships_mentor ON mentorships(mentor_id);
        CREATE INDEX IF NOT EXISTS idx_mentorships_student ON mentorships(student_id);
        PRAGMA foreign_keys = ON;
        """
    )


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
