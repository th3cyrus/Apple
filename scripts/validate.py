"""Shared offline catalog, artwork, playlist and current-run validation."""
import argparse
import json
import os
from pathlib import Path

from PIL import Image
from catalog import validate_catalog

ROOT = Path(__file__).resolve().parents[1]


def validate_outputs(root=ROOT, minimum=35):
    root = Path(root)
    stations = validate_catalog(json.loads((root / 'stations.json').read_text(encoding='utf-8')))
    if len(stations) < minimum:
        raise ValueError('Station catalog is incomplete')
    lines = (root / 'radio.m3u').read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != '#EXTM3U' or len(lines) != 1 + 2 * len(stations):
        raise ValueError('Invalid playlist structure')
    for index, station in enumerate(stations):
        if not lines[1 + 2 * index].startswith('#EXTINF:') or lines[2 + 2 * index] != station['stream']:
            raise ValueError('Playlist order or URL differs from catalog')
        with Image.open(root / station['logo']) as image:
            image.verify()
    return stations


def validate_report(path, run_id=None, allow_partial=False, expected_total=None):
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(report, dict) or report.get('schema_version') != 2:
        raise ValueError('Invalid current-run report schema')
    if run_id and report.get('github_run_id') != str(run_id):
        raise ValueError('Diagnostics belong to a different workflow run')
    if not allow_partial and report.get('status') not in ('complete', 'complete_with_errors'):
        raise ValueError('Diagnostics report is incomplete or failed')
    stations = report.get('stations', [])
    summary = report.get('summary', {})
    if not isinstance(stations, list) or not isinstance(summary, dict):
        raise ValueError('Invalid diagnostics station results')
    if not allow_partial:
        total = expected_total if expected_total is not None else report.get('expected_total')
        ids = [item['id'] for item in stations]
        if (len(ids) != total or len(set(ids)) != total or summary.get('checked') != total
                or any(item.get('status') not in ('ok', 'needs_review', 'repaired') for item in stations)):
            raise ValueError('Diagnostics missing complete, unique station results')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    parser.add_argument('--report-only', action='store_true')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    stations = None if args.report_only else validate_outputs()
    if args.report:
        validate_report(args.report, os.environ.get('GITHUB_RUN_ID'), args.allow_partial,
                        len(stations) if stations is not None else None)
    print('Validated', len(stations) if stations else 'current-run', 'stations/report')


if __name__ == '__main__':
    main()
