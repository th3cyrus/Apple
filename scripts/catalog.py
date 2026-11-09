"""Validate maintained station data before network requests or file changes."""
from datetime import datetime
import re

from safety import public_media_url, unsupported_stream_suffix, valid_url


def validate_catalog(stations):
    if not isinstance(stations, list) or not stations:
        raise ValueError('Station catalog must be a nonempty array')
    seen = set()
    for index, station in enumerate(stations):
        if not isinstance(station, dict):
            raise ValueError(f'Station {index} must be an object')
        sid = station.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', sid):
            raise ValueError(f'Invalid station ID at index {index}')
        if sid in seen:
            raise ValueError(f'Duplicate station ID: {sid}')
        seen.add(sid)
        for key in ('name', 'group', 'search'):
            value = station.get(key)
            if not isinstance(value, str) or not value.strip() or re.search(r'[\r\n\x00]', value):
                raise ValueError(f'Invalid {key} for {sid}')
        for key in ('stream', 'homepage'):
            if not valid_url(station.get(key)):
                raise ValueError(f'Invalid {key} URL for {sid}')
        if not public_media_url(station['stream']):
            raise ValueError(f'Nonpublic stream destination for {sid}')
        if unsupported_stream_suffix(station['stream']):
            raise ValueError(f'Misleading audio/playlist double extension for {sid}')
        if station.get('logo') != f'Covers/{sid}.jpg':
            raise ValueError(f'Invalid custom artwork path for {sid}')
        if not isinstance(station.get('manual_lock', False), bool):
            raise ValueError(f'Invalid manual_lock for {sid}')
        failures = station.get('fail_count', 0)
        if type(failures) is not int or not 0 <= failures <= 20:
            raise ValueError(f'Invalid fail_count for {sid}')
        checked = station.get('last_failure_counted_at')
        if checked is not None:
            try:
                if datetime.fromisoformat(checked.replace('Z', '+00:00')).tzinfo is None:
                    raise ValueError('Missing timezone')
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f'Invalid failure timestamp for {sid}') from exc
        identity = station.get('identity')
        if identity is not None:
            if not isinstance(identity, dict):
                raise ValueError(f'Invalid identity for {sid}')
            for field in ('aliases', 'callsigns', 'verified_stationuuids'):
                values = identity.get(field, [])
                if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise ValueError(f'Invalid identity {field} for {sid}')
            if identity.get('band', 'FM') not in ('FM', 'AM', 'internet'):
                raise ValueError(f'Invalid identity band for {sid}')
            if not isinstance(identity.get('channel', 'main'), str):
                raise ValueError(f'Invalid identity channel for {sid}')
    return stations
