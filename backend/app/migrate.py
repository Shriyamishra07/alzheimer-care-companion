"""Small, idempotent schema migration run at every start.

create_all() makes missing tables but never adds columns to tables that already
exist (for example the Neon database deployed for Review II). This adds the new
columns when they are missing, then makes sure every patient with family links
has one primary caregiver. Safe to run any number of times.
"""
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .models import CareLink

NEW_COLUMNS = {
    "users": [("ai_media_consent", "BOOL_FALSE")],
    "care_links": [("role", "VARCHAR(12) DEFAULT 'secondary' NOT NULL"), ("permissions", "JSON"),
                   ("relation", "VARCHAR(60) DEFAULT ''"), ("invited_by", "INTEGER")],
    "link_codes": [("issued_by", "INTEGER"), ("link_role", "VARCHAR(12) DEFAULT ''"), ("permissions", "JSON"),
                   ("label", "VARCHAR(60) DEFAULT ''")],
    "reminders": [("kind", "VARCHAR(20) DEFAULT 'other'"), ("note", "VARCHAR(300) DEFAULT ''"),
                  ("repeat_mode", "VARCHAR(10) DEFAULT 'daily'"), ("on_date", "VARCHAR(10)"), ("speak", "BOOL_TRUE"),
                  ("voice_data", "BLOB"), ("voice_mime", "VARCHAR(80) DEFAULT ''")],
    "query_logs": [("ai_payload", "JSON")],
}


def _ddl(kind: str, dialect: str) -> str:
    pg = dialect == "postgresql"
    return {"BOOL_FALSE": "BOOLEAN DEFAULT " + ("FALSE" if pg else "0"),
            "BOOL_TRUE": "BOOLEAN DEFAULT " + ("TRUE" if pg else "1"),
            "BLOB": "BYTEA" if pg else "BLOB"}.get(kind, kind)


def migrate(engine) -> list[str]:
    added = []
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if table not in tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, kind in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {_ddl(kind, engine.dialect.name)}"))
                    added.append(f"{table}.{name}")
    if "care_links.role" not in added:
        return added
    # First upgrade only: links made before roles existed. The earliest caregiver per patient becomes primary.
    # (Later on, a primary is never promoted automatically: the person or the primary chooses who it is.)
    with Session(engine) as db:
        active = db.query(CareLink).filter(CareLink.revoked_at.is_(None)).order_by(CareLink.created_at).all()
        by_patient = {}
        for link in active:
            by_patient.setdefault(link.patient_id, []).append(link)
        for links in by_patient.values():
            if not any(l.role == "primary" for l in links):
                links[0].role = "primary"
        db.commit()
    return added
