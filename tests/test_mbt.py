"""Hypothesis MBT for the nine API routes and both backends."""

import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from hypothesis import settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from src.api import create_app
from src.client import ApiClient
from src.service import ConversionService
from src.storage import FileStore, SQLiteStore


USERNAME = "test-user"
PASSWORD = "test-password"
ONE_RESULT = 1
HTTP_UNAUTHORIZED = 401


class QuietHandler(WSGIRequestHandler):
    """Suppress noisy request logging during property-based tests."""

    def log_message(self, format_string, *args):
        pass


class ApiMachine(RuleBasedStateMachine):
    """Compare API transitions with an independently held model of IDs."""

    backend = "file"

    def __init__(self):
        super().__init__()
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        if self.backend == "sqlite":
            store = SQLiteStore(root / "records.sqlite3")
        else:
            store = FileStore(root / "records.json")
        self.service = ConversionService(
            store, root / "uploads", root / "outputs", test_mode=True,
        )
        app = create_app(self.service, USERNAME, PASSWORD)
        self.server = make_server(
            "127.0.0.1", 0, app, handler_class=QuietHandler,
        )
        self.worker = threading.Thread(
            target=self.server.serve_forever, daemon=True,
        )
        self.worker.start()
        address = f"http://127.0.0.1:{self.server.server_port}"
        self.client = ApiClient(address, USERNAME, PASSWORD)
        self.base_url = address
        self.participants = []
        self.assignments = []

    def teardown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)
        self.service.close()
        self.folder.cleanup()

    @initialize()
    def initial_workflow(self):
        """Force all nine routes into every generated state-machine run."""
        api = self.client
        participant = api.core_api_stable_add_participant("ru", "desktop")
        person_id = int(participant["identifier"])
        self.participants.append(person_id)
        retrieved = api.core_api_stable_retrieve_participant(person_id)
        assert retrieved == participant
        assert participant in api.core_api_stable_read_participant()

        assignment = api.core_api_stable_add_assignment(
            person_id, "first.gif", "demo",
        )
        assignment_id = int(assignment["identifier"])
        self.assignments.append((assignment_id, person_id))
        assert assignment["stage"] == "test"
        assert assignment == api.core_api_stable_retrieve_assignment(
            assignment_id
        )
        assert assignment in api.core_api_stable_read_assignment(person_id)

        results = api.core_api_stable_read_result(assignment_id)
        assert len(results) == ONE_RESULT
        assert results[0]["stage"] == "test"
        result_id = int(results[0]["identifier"])
        assert api.core_api_stable_retrieve_result(result_id) == results[0]
        report = api.core_api_stable_read_report()
        assert any(row["input"] == "first.gif" for row in report)
        self.check_unassigned_participant()

    def check_unassigned_participant(self):
        """Right outer join excludes participants without assignments."""
        item = self.client.core_api_stable_add_participant(
            "ru", "unassigned-participant",
        )
        self.participants.append(int(item["identifier"]))
        report = self.client.core_api_stable_read_report()
        assert all(
            row["platform"] != "unassigned-participant"
            for row in report
        )

    @rule()
    def unauthenticated_is_rejected(self):
        """An HTTP request without Basic credentials must receive 401."""
        url = self.base_url + "/core/api/stable/read-report"
        with unittest.TestCase().assertRaises(
            urllib.error.HTTPError
        ) as caught:
            urllib.request.urlopen(url, timeout=10)
        assert caught.exception.code == HTTP_UNAUTHORIZED

    @rule(platform=st.sampled_from(["desktop", "mobile", "web"]),
          locale=st.sampled_from(["ru", "en", "de"]))
    def new_participant(self, platform, locale):
        """Adding a participant must make it retrievable by its ID."""
        item = self.client.core_api_stable_add_participant(locale, platform)
        identifier = int(item["identifier"])
        assert identifier not in self.participants
        self.participants.append(identifier)
        retrieved = self.client.core_api_stable_retrieve_participant(
            identifier
        )
        assert retrieved == item
        assert item in self.client.core_api_stable_read_participant(
            platform=platform, locale=locale,
        )

    @rule(choice=st.integers(min_value=0, max_value=100),
          name=st.sampled_from(["a.gif", "b.gif", "animation.gif"]))
    def new_assignment(self, choice, name):
        """Assignment creation changes the model and creates a result row."""
        participant = self.participants[choice % len(self.participants)]
        item = self.client.core_api_stable_add_assignment(
            participant, name, "hypothesis",
        )
        identifier = int(item["identifier"])
        assert identifier not in [row[0] for row in self.assignments]
        self.assignments.append((identifier, participant))
        assert item["stage"] == "test"
        results = self.client.core_api_stable_read_result(identifier)
        assert len(results) == ONE_RESULT
        assert results[0]["assignment"] == str(identifier)

    @rule(choice=st.integers(min_value=0, max_value=100))
    def inspect_assignment(self, choice):
        """Reading by participant must include its corresponding assignment."""
        identifier, participant = self.assignments[
            choice % len(self.assignments)
        ]
        assignments = self.client.core_api_stable_read_assignment(participant)
        assert str(identifier) in [row["identifier"] for row in assignments]
        one = self.client.core_api_stable_retrieve_assignment(identifier)
        assert one["participant"] == str(participant)

    @invariant()
    def read_model_matches(self):
        """Every known participant persists and report keeps known inputs."""
        api = self.client
        participants = api.core_api_stable_read_participant()
        assert {int(row["identifier"]) for row in participants} == set(
            self.participants
        )
        report = api.core_api_stable_read_report()
        assert len(report) >= len(self.assignments)


class FileApiMachine(ApiMachine):
    """Exercise the filesystem backend."""

    backend = "file"


class SQLiteApiMachine(ApiMachine):
    """Repeat the same model tests using SQL storage."""

    backend = "sqlite"


TestFileApi = FileApiMachine.TestCase
TestSQLiteApi = SQLiteApiMachine.TestCase
TestFileApi.settings = settings(
    max_examples=12, stateful_step_count=10, deadline=None,
)
TestSQLiteApi.settings = settings(
    max_examples=12, stateful_step_count=10, deadline=None,
)
