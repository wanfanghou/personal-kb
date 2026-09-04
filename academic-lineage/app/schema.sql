CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    institution TEXT,
    field TEXT,
    title TEXT,
    editorial_roles_json TEXT NOT NULL DEFAULT '[]',
    honors_json TEXT NOT NULL DEFAULT '[]',
    homepage_url TEXT NOT NULL UNIQUE,
    homepage_title TEXT,
    public INTEGER NOT NULL DEFAULT 0,
    notes_private TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mentorships (
    id TEXT PRIMARY KEY,
    mentor_id TEXT NOT NULL REFERENCES persons(id),
    student_id TEXT NOT NULL REFERENCES persons(id),
    relationship_type TEXT NOT NULL
        CHECK (relationship_type IN ('phd', 'master', 'postdoc', 'informal', 'other')),
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

CREATE TABLE IF NOT EXISTS source_snapshots (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL REFERENCES persons(id),
    url TEXT NOT NULL,
    title TEXT,
    description TEXT,
    fetched_at TEXT NOT NULL,
    http_status INTEGER
);

CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_institution ON persons(institution);
CREATE INDEX IF NOT EXISTS idx_mentorships_mentor ON mentorships(mentor_id);
CREATE INDEX IF NOT EXISTS idx_mentorships_student ON mentorships(student_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_person ON source_snapshots(person_id);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    submitter_note TEXT,
    review_note TEXT,
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
