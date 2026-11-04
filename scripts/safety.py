"""Shared validation, redaction and atomic file writes."""
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qsl, urlsplit

SIGNED_PARAMETERS = {
    'token', 'zt', 'signature', 'policy', 'expires', 'key', 'sig',
    'access_token', 'auth_token', 'hdnts', 'hdnea', 'key-pair-id', 'awsaccesskeyid',
}


def valid_url(value):
    if not isinstance(value, str) or not value or re.search(r'[\s\x00-\x1f\x7f"<>\\]', value):
        return False
    try:
        parts = urlsplit(value)
        return bool(parts.scheme in ('http', 'https') and parts.hostname
                    and not parts.username and not parts.password
                    and (parts.port is None or 0 < parts.port < 65536))
    except (ValueError, TypeError, AttributeError):
        return False


def has_expiring_query(value):
    """Reject signed/temporary links, including parameters with empty values."""
    return any(key.lower() in SIGNED_PARAMETERS
               or key.lower().startswith(('x-amz-', 'x-goog-'))
               for key, _ in parse_qsl(urlsplit(value).query, keep_blank_values=True))


def unsupported_stream_suffix(value):
    """Reject audio/playlist double-extensions such as .mp3.m3u."""
    if not valid_url(value):
        return False
    path = urlsplit(value).path.lower()
    return bool(re.search(r'\.(?:mp3|aac|m4a|ogg|opus|flac|wav)\.(?:m3u|m3u8|pls)$', path))


def safe_url(value):
    if not valid_url(value):
        return '[invalid URL]'
    parts = urlsplit(value)
    return parts._replace(query='[redacted]' if parts.query else '', fragment='').geturl()


def safe_message(value):
    text = str(value)
    text = re.sub(r'https?://[^\s<>\x22\x27)]+', lambda m: safe_url(m[0]), text)
    # Requests/urllib3 often include only a relative request target in exceptions.
    text = re.sub(r'\?[^\s<>\x22\x27)]+', '?[redacted]', text)
    text = re.sub(r'(?i)\b(authorization|password|passwd|token|api[_-]?key|secret)'
                  r'([=:]\s*)[^\s,;\x22\x27)]+', r'\1\2[redacted]', text)
    return text[:8000]


def sanitize(value):
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return safe_message(value)
    return value


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
