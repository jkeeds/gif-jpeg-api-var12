"""File storage and SQLite storage with the same public model operations."""

import json
import threading
import time
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
            for assignment in linked or [None]:
                recent = [
                    item for item in results
                    if assignment is not None
                    and item["assignment"] == assignment["identifier"]
                    and item["datetime"] >= threshold
                ]
                for item in recent or [None]:
                    rows.append({
                        "input": assignment["input"] if assignment else None,
                        "platform": person["platform"],
                        "cache_hit": item["cache_hit"] if item else None,
                    })
        return rows

