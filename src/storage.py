"""File storage and SQLite storage with the same public model operations."""

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path


TABLE_NAMES = ("participants", "assignments", "results")


def _now() -> int:
    """Return an integer Unix timestamp."""
    return int(time.time())


def _where_matches(record, filters):
    """Check a record against nonempty string query filters."""
    return all(
        str(record.get(key)) == str(value)
        for key, value in filters.items()
        if value is not None and value != ""
    )


class FileStore:
    """Persist three related tables as JSON in the filesystem."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        if not self.path.exists():
            self._save({name: [] for name in TABLE_NAMES})

    def _load(self):
        with self.path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def _save(self, data):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def _add(self, table, values):
        with self.lock:
            data = self._load()
            identifiers = (row["identifier"] for row in data[table])
            item = {"identifier": max(identifiers, default=0) + 1}
            item.update(values)
            data[table].append(item)
            self._save(data)
            return item.copy()

    def _read(self, table, **filters):
        with self.lock:
            records = self._load()[table]
        return [row for row in records if _where_matches(row, filters)]

    def _retrieve(self, table, identifier):
        records = self._read(table, identifier=identifier)
        return records[0] if records else None

    def _update(self, table, identifier, **values):
        with self.lock:
            data = self._load()
            for row in data[table]:
                if row["identifier"] == identifier:
                    row.update(values)
                    self._save(data)
                    return row.copy()
        return None

    def participant_add(self, locale, platform):
        return self._add(
            "participants",
            {"datetime": _now(), "locale": locale, "platform": platform},
        )

    def participant_read(self, **filters):
        return self._read("participants", **filters)

    def participant_retrieve(self, identifier):
        return self._retrieve("participants", identifier)

    def assignment_add(self, participant, input_name, tags):
        return self._add(
            "assignments",
            {"datetime": _now(), "input": input_name,
             "participant": participant, "tags": tags, "stage": "queued"},
        )

    def assignment_read(self, **filters):
        return self._read("assignments", **filters)

    def assignment_retrieve(self, identifier):
        return self._retrieve("assignments", identifier)

    def assignment_stage(self, identifier, stage):
        return self._update("assignments", identifier, stage=stage)

    def result_add(self, assignment, response, stage, exception, cache_hit):
        return self._add(
            "results",
            {"datetime": _now(), "response": response, "stage": stage,
             "exception": exception, "assignment": assignment,
             "cache_hit": cache_hit},
        )

    def result_read(self, **filters):
        return self._read("results", **filters)

    def result_retrieve(self, identifier):
        return self._retrieve("results", identifier)

    def result_update(self, identifier, **values):
        return self._update("results", identifier, **values)

    def report_read(self, seconds=300):
        threshold = _now() - seconds
        participants = self.participant_read()
        assignments = self.assignment_read()
        results = self.result_read()
        rows = []
        for person in participants:
            linked = [
                assignment for assignment in assignments
                if assignment["participant"] == person["identifier"]
            ]
            for assignment in linked:
                recent = [
                    item for item in results
                    if item["assignment"] == assignment["identifier"]
                    and item["datetime"] >= threshold
                ]
                for item in recent or [None]:
                    rows.append({
                        "input": assignment["input"],
                        "platform": person["platform"],
                        "cache_hit": item["cache_hit"] if item else None,
                    })
        return rows


class SQLiteStore:
    """Persist the same entities using explicit SQL statements (no ORM)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS participant (
                    identifier INTEGER PRIMARY KEY AUTOINCREMENT,
                    datetime INTEGER NOT NULL,
                    locale TEXT NOT NULL,
                    platform TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assignment (
                    identifier INTEGER PRIMARY KEY AUTOINCREMENT,
                    datetime INTEGER NOT NULL,
                    input TEXT NOT NULL,
                    participant INTEGER NOT NULL,
                    tags TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    FOREIGN KEY (participant)
                        REFERENCES participant(identifier)
                );
                CREATE TABLE IF NOT EXISTS result (
                    identifier INTEGER PRIMARY KEY AUTOINCREMENT,
                    datetime INTEGER NOT NULL,
                    response TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    exception TEXT NOT NULL,
                    assignment INTEGER NOT NULL,
                    cache_hit INTEGER NOT NULL,
                    FOREIGN KEY (assignment) REFERENCES assignment(identifier)
                );
            """)

    @contextmanager
    def _connect(self):
        """Open, commit or roll back, then close one SQLite connection."""
        db = sqlite3.connect(str(self.path), timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _select(self, table, filters):
        allowed = {
            "participant": {"identifier", "locale", "platform"},
            "assignment": {"identifier", "participant", "stage"},
            "result": {"identifier", "assignment", "stage"},
        }
        clauses = []
        parameters = []
        for key, value in filters.items():
            if key not in allowed[table]:
                raise ValueError(f"Unsupported filter: {key}")
            if value is not None and value != "":
                clauses.append(f"{key} = ?")
                parameters.append(value)
        query = f"SELECT * FROM {table}"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY identifier"
        with self.lock, self._connect() as db:
            return [dict(row) for row in db.execute(query, parameters)]

    def _insert(self, table, values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        with self.lock, self._connect() as db:
            cursor = db.execute(query, tuple(values.values()))
            identifier = cursor.lastrowid
            return dict(db.execute(
                f"SELECT * FROM {table} WHERE identifier = ?",
                (identifier,),
            ).fetchone())

    def _update(self, table, identifier, values):
        columns = ", ".join(f"{name} = ?" for name in values)
        query = f"UPDATE {table} SET {columns} WHERE identifier = ?"
        with self.lock, self._connect() as db:
            db.execute(query, (*values.values(), identifier))
            row = db.execute(
                f"SELECT * FROM {table} WHERE identifier = ?",
                (identifier,),
            ).fetchone()
            return dict(row) if row else None

    def participant_add(self, locale, platform):
        return self._insert(
            "participant",
            {"datetime": _now(), "locale": locale, "platform": platform},
        )

    def participant_read(self, **filters):
        return self._select("participant", filters)

    def participant_retrieve(self, identifier):
        rows = self.participant_read(identifier=identifier)
        return rows[0] if rows else None

    def assignment_add(self, participant, input_name, tags):
        return self._insert(
            "assignment",
            {"datetime": _now(), "input": input_name,
             "participant": participant, "tags": tags, "stage": "queued"},
        )

    def assignment_read(self, **filters):
        return self._select("assignment", filters)

    def assignment_retrieve(self, identifier):
        rows = self.assignment_read(identifier=identifier)
        return rows[0] if rows else None

    def assignment_stage(self, identifier, stage):
        return self._update("assignment", identifier, {"stage": stage})

    def result_add(self, assignment, response, stage, exception, cache_hit):
        return self._insert(
            "result",
            {"datetime": _now(), "response": response, "stage": stage,
             "exception": exception, "assignment": assignment,
             "cache_hit": cache_hit},
        )

    def result_read(self, **filters):
        return self._select("result", filters)

    def result_retrieve(self, identifier):
        rows = self.result_read(identifier=identifier)
        return rows[0] if rows else None

    def result_update(self, identifier, **values):
        return self._update("result", identifier, values)

    def report_read(self, seconds=300):
        query = """
            SELECT a.input, p.platform, r.cache_hit
            FROM participant AS p
            JOIN assignment AS a ON a.participant = p.identifier
            LEFT JOIN result AS r ON r.assignment = a.identifier
                AND r.datetime >= ?
            ORDER BY p.identifier, a.identifier, r.identifier
        """
        with self.lock, self._connect() as db:
            return [
                dict(row) for row in db.execute(query, (_now() - seconds,))
            ]
