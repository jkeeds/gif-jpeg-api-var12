"""Manage asynchronous tasks and bridge HTTP API to the CLI converter."""

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


MAX_CONVERSION_SECONDS = 60


class ConversionService:
    """Store assignments immediately and process real jobs in a thread pool."""

    def __init__(self, store, upload_dir, output_dir, test_mode=False):
        self.store = store
        self.upload_dir = Path(upload_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.test_mode = test_mode
        self.executor = ThreadPoolExecutor(max_workers=2)

    def add_assignment(self, participant, input_name, tags=""):
        """Create a queued assignment and launch its worker if requested."""
        if not self.store.participant_retrieve(participant):
            raise ValueError("Participant does not exist")
        if not input_name or Path(input_name).name != input_name:
            raise ValueError("Input must be a simple GIF filename")
        if Path(input_name).suffix.lower() != ".gif":
            raise ValueError("Input filename must end with .gif")
        if not self.test_mode and not (self.upload_dir / input_name).is_file():
            raise ValueError("Input GIF not found in uploads directory")
        assignment = self.store.assignment_add(participant, input_name, tags)
        result = self.store.result_add(
            assignment["identifier"], "", "queued", "", 0,
        )
        if self.test_mode:
            self._finish(assignment["identifier"], result["identifier"],
                         "test", "skipped (test mode)", "")
        else:
            self.executor.submit(
                self._convert, assignment["identifier"],
                result["identifier"], input_name,
            )
        return self.store.assignment_retrieve(assignment["identifier"])

    def _finish(self, assignment_id, result_id, stage, response, error):
        """Commit matching statuses to both tables."""
        self.store.assignment_stage(assignment_id, stage)
        self.store.result_update(
            result_id, stage=stage, response=response,
            exception=error, datetime=int(time.time()),
        )

    def _convert(self, assignment_id, result_id, input_name):
        """Execute the standalone converter in a subprocess."""
        self.store.assignment_stage(assignment_id, "running")
        self.store.result_update(result_id, stage="running")
        output_name = f"{assignment_id}_{Path(input_name).stem}.jpg"
        output_file = self.output_dir / output_name
        command = [
            sys.executable, "-m", "src.converter",
            str(self.upload_dir / input_name), str(output_file),
        ]
        try:
            subprocess.run(
                command, check=True, capture_output=True, text=True,
                timeout=MAX_CONVERSION_SECONDS,
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            self._finish(assignment_id, result_id, "done", output_name, "")
        except (OSError, subprocess.SubprocessError) as error:
            self._finish(assignment_id, result_id, "error", "", str(error))

    def close(self):
        """Stop accepting jobs and wait for already submitted jobs."""
        self.executor.shutdown(wait=True)
