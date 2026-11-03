"""Checkpoint each run separately and retain a bounded, sanitized history."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback
import uuid

from safety import atomic_json, atomic_write, safe_message, sanitize

MAX_HEALTH_RUNS = 30


class HealthReporter:
    def __init__(self, current_path, history_path):
        self.current_path = Path(current_path)
        self.history_path = Path(history_path)
        self.report = {
            'schema_version': 2,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'github_run_id': os.environ.get('GITHUB_RUN_ID') or 'local-' + uuid.uuid4().hex,
            'github_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
            'commit_sha': os.environ.get('GITHUB_SHA'),
            'status': 'running', 'expected_total': None, 'stations': [],
        }
        self.checkpoint()

    def checkpoint(self):
        stations = self.report['stations']
        self.report['summary'] = {
            'total': self.report['expected_total'],
            'checked': sum(item.get('status') != 'checking' for item in stations),
            'healthy': sum(item.get('status') == 'ok' for item in stations),
            'needs_review': sum(item.get('status') == 'needs_review' for item in stations),
            'repaired': sum(item.get('status') == 'repaired' for item in stations),
            'station_errors': sum('unexpected_error' in item for item in stations),
            'http_streams': sum(bool(item.get('http_in_use')) for item in stations),
            'http_used_in_checks': sum(bool(item.get('stream_check', {}).get('http_used'))
                                       or any(check.get('check', {}).get('http_used', False)
                                              for check in item.get('candidate_checks', []))
                                       for item in stations),
        }
        atomic_json(self.current_path, sanitize(self.report))

    def finish(self, error=None):
        if error is not None:
            self.report.update(status='failed', fatal_error={
                'error_type': type(error).__name__, 'error': safe_message(error),
                'traceback': safe_message(''.join(traceback.format_exception(error))),
            })
        else:
            self.report['status'] = ('complete_with_errors' if any(
                'unexpected_error' in item for item in self.report['stations']) else 'complete')
        self.report['finished_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.checkpoint()
        previous = []
        if self.history_path.exists():
            for line in self.history_path.read_text(encoding='utf-8').splitlines():
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        previous.append(value)
                except ValueError:
                    continue
        key = (self.report['github_run_id'], self.report['github_run_attempt'])
        previous = [item for item in previous
                    if (item.get('github_run_id'), item.get('github_run_attempt')) != key]
        previous.append(self.report)
        atomic_write(self.history_path, ''.join(
            json.dumps(sanitize(item), ensure_ascii=False, separators=(',', ':')) + '\n'
            for item in previous[-MAX_HEALTH_RUNS:]))
