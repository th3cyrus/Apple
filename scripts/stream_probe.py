"""Bounded audio probes, playlist traversal and transport diagnostics.

ffprobe receives a bounded byte sample over stdin and cannot open network URLs.
Successful detection proves audio packets exist, not that every listener can play
the stream or that the broadcast is audible, uninterrupted, or the right station.
"""
import json
import re
import shutil
import subprocess
import time
from time import sleep
from urllib.parse import urljoin, urlsplit

from requests.exceptions import ConnectionError, SSLError, Timeout
from urllib3.exceptions import ProtocolError, ReadTimeoutError, SSLError as TransportSSLError
from safety import safe_message, safe_url, valid_url

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 12
MAX_ATTEMPTS = 3
RETRY_DELAYS = (1, 2)
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
PROBE_BUDGET = 45
MAX_REDIRECTS = 5
MAX_PLAYLIST_DEPTH = 3
MAX_PLAYLIST_BYTES = 65536
MAX_SAMPLE_BYTES = 32768


class ProbeError(Exception):
    def __init__(self, kind, message, *, retryable=False, repairable=False):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.repairable = repairable


def check_audio(sample, remaining=5):
    if not sample:
        raise ProbeError('EmptyStream', 'Stream returned no media bytes', repairable=True)
    if not shutil.which('ffprobe'):
        raise ProbeError('MissingProbeTool', 'ffprobe is required to verify audio')
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-protocol_whitelist', 'pipe',
            '-probesize', str(MAX_SAMPLE_BYTES * 4), '-analyzeduration', '2000000',
            '-count_packets', '-show_entries', 'stream=codec_type,codec_name,nb_read_packets',
            '-of', 'json', '-i', 'pipe:0',
        ], input=sample, capture_output=True, timeout=max(0.1, min(5, remaining)), check=False)
        data = json.loads(result.stdout or b'{}')
    except subprocess.TimeoutExpired as exc:
        raise ProbeError('MediaProbeTimeout', 'Audio sample verification timed out') from exc
    except (OSError, ValueError) as exc:
        raise ProbeError('MediaProbeError', safe_message(exc)) from exc
    for stream in data.get('streams', []):
        packets = str(stream.get('nb_read_packets', '0'))
        if stream.get('codec_type') == 'audio' and packets.isdigit() and int(packets) > 0:
            return {'codec': stream.get('codec_name'), 'audio_packets': int(packets)}
    raise ProbeError('UnverifiedMedia', 'No audio packets could be verified in bounded sample')


def _remaining(deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise ProbeError('ProbeDeadline', 'Stream probe exceeded its time budget', retryable=True)
    return left


def _read(response, limit, deadline):
    data = bytearray()
    # read1 returns available bytes instead of waiting for a whole large chunk.
    reader = getattr(response.raw, 'read1', response.raw.read)
    while len(data) < limit:
        _remaining(deadline)
        chunk = reader(min(4096, limit - len(data)))
        if not chunk:
            break
        data.extend(chunk)
    _remaining(deadline)
    return bytes(data)


def _attributes(line):
    return {match[1]: match[2].strip('"') for match in
            re.finditer(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', line.partition(':')[2])}


def _playlist_target(body, base):
    text = body.decode('utf-8-sig', errors='replace')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.startswith('#EXT-X-KEY:') and _attributes(line).get('METHOD') != 'NONE':
            raise ProbeError('EncryptedHLS', 'Encrypted HLS requires manual verification')
    audio = [_attributes(line) for line in lines if line.startswith('#EXT-X-MEDIA:')]
    audio = [item for item in audio if item.get('TYPE') == 'AUDIO' and item.get('URI')]
    if audio:
        audio.sort(key=lambda item: item.get('DEFAULT') != 'YES')
        return urljoin(base, audio[0]['URI']), None
    variants = []
    for index, line in enumerate(lines[:-1]):
        if line.startswith('#EXT-X-STREAM-INF:') and not lines[index + 1].startswith('#'):
            bandwidth = _attributes(line).get('BANDWIDTH', '')
            variants.append((int(bandwidth) if bandwidth.isdigit() else 10**12, lines[index + 1]))
    if variants:
        return urljoin(base, min(variants)[1]), None
    initialization = next((_attributes(line).get('URI') for line in lines
                           if line.startswith('#EXT-X-MAP:')), None)
    targets = [line for line in lines if not line.startswith(('#', '['))]
    if text.lstrip().lower().startswith('[playlist]'):
        targets = [line.partition('=')[2].strip() for line in lines
                   if re.match(r'(?i)^file\d+\s*=', line)]
    if not targets:
        raise ProbeError('EmptyPlaylist', 'Playlist contains no media URL', repairable=True)
    return urljoin(base, targets[0]), urljoin(base, initialization) if initialization else None


def _fetch(session, url, attempt, deadline, visited, depth=0, *, initialization=False):
    if depth > MAX_PLAYLIST_DEPTH:
        raise ProbeError('PlaylistDepth', 'Playlist nesting limit reached')
    if not valid_url(url):
        raise ProbeError('InvalidURL', 'Invalid HTTP or HTTPS media URL', repairable=True)
    if url in visited:
        raise ProbeError('PlaylistLoop', 'Playlist or redirect loop detected')
    visited.add(url)
    response = None
    current = url
    for redirect in range(MAX_REDIRECTS + 1):
        if not valid_url(current):
            raise ProbeError('InvalidURL', 'Unsafe media redirect URL')
        left = _remaining(deadline)
        node = {'url': safe_url(current), 'protocol': urlsplit(current).scheme.upper()}
        attempt['requests'].append(node)
        attempt['http_used'] |= node['protocol'] == 'HTTP'
        response = session.get(current, stream=True, allow_redirects=False,
                               timeout=(min(CONNECT_TIMEOUT, left), min(READ_TIMEOUT, left)),
                               headers={'User-Agent': 'ApplePrimuseRadio/2.0',
                                        'Icy-MetaData': '0', 'Accept-Encoding': 'identity'})
        node['http_status'] = response.status_code
        attempt['http_status'] = response.status_code
        attempt['final_protocol'] = node['protocol']
        attempt['final_url'] = safe_url(current)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location')
            response.close()
            if not location or redirect == MAX_REDIRECTS:
                raise ProbeError('RedirectLimit', 'Invalid or excessive redirects')
            current = urljoin(current, location)
            if current in visited:
                raise ProbeError('PlaylistLoop', 'Playlist or redirect loop detected')
            visited.add(current)
            continue
        break
    try:
        status = response.status_code
        if status not in (200, 206):
            raise ProbeError('HTTPStatus', f'HTTP {status}: {response.reason}',
                             retryable=status in RETRYABLE_STATUSES,
                             repairable=status in (404, 410))
        mime = response.headers.get('Content-Type', '').lower().split(';')[0].strip()
        node['content_type'] = mime
        attempt.setdefault('content_type', mime)
        if mime in ('text/html', 'application/json'):
            raise ProbeError('UnexpectedContentType', f'Expected media, got {mime}')
        content = _read(response, MAX_SAMPLE_BYTES, deadline)
        node['bytes_read'] = len(content)
        attempt['bytes_read'] += len(content)
        if initialization:
            if not content:
                raise ProbeError('EmptyStream', 'Empty HLS initialization segment')
            return content
        stripped = content.lstrip(b'\xef\xbb\xbf\r\n\t ')
        looks_text = all(byte in (9, 10, 13) or 32 <= byte < 127 for byte in stripped[:200])
        playlist_hint = ('mpegurl' in mime or 'scpls' in mime
                         or urlsplit(current).path.lower().endswith(('.m3u', '.m3u8', '.pls')))
        playlist = (stripped.startswith(b'#EXTM3U') or stripped.lower().startswith(b'[playlist]')
                    or stripped.startswith((b'http://', b'https://'))
                    or (playlist_hint and looks_text))
        if playlist:
            if len(content) == MAX_SAMPLE_BYTES:
                extra = _read(response, MAX_PLAYLIST_BYTES - len(content) + 1, deadline)
                content += extra
                node['bytes_read'] += len(extra)
                attempt['bytes_read'] += len(extra)
                if len(content) > MAX_PLAYLIST_BYTES:
                    raise ProbeError('PlaylistTooLarge', 'Playlist exceeds size limit')
            target, init = _playlist_target(content, current)
            prefix = _fetch(session, init, attempt, deadline, visited, depth + 1,
                            initialization=True) if init else b''
        else:
            return content
    finally:
        response.close()
    media = _fetch(session, target, attempt, deadline, visited, depth + 1)
    return prefix + media


def stream_check(session, url):
    started = time.monotonic()
    info = {'ok': False, 'url': safe_url(url), 'attempts': [], 'http_used': False,
            'repairable': False}
    if not valid_url(url):
        info.update(error_type='InvalidURL', error='Stream URL must be a valid HTTP or HTTPS address',
                    elapsed_ms=0, repairable=True)
        return info
    info['protocol'] = urlsplit(url).scheme.upper()
    for number in range(1, MAX_ATTEMPTS + 1):
        attempt = {'attempt': number, 'requests': [], 'bytes_read': 0, 'http_used': False}
        attempt_started = time.monotonic()
        retryable = False
        try:
            sample = _fetch(session, url, attempt, started + PROBE_BUDGET, set())
            attempt.update(check_audio(sample, _remaining(started + PROBE_BUDGET)))
            attempt['ok'] = True
            info['ok'] = True
        except ProbeError as exc:
            attempt.update(error_type=exc.kind, error=safe_message(exc))
            info['repairable'] = exc.repairable
            retryable = exc.retryable
        except (SSLError, TransportSSLError) as exc:
            attempt.update(error_type=type(exc).__name__, error=safe_message(exc))
        except (Timeout, ConnectionError, ReadTimeoutError, ProtocolError) as exc:
            attempt.update(error_type=type(exc).__name__, error=safe_message(exc))
            retryable = True
        except Exception as exc:
            attempt.update(error_type=type(exc).__name__, error=safe_message(exc))
        attempt['elapsed_ms'] = round((time.monotonic() - attempt_started) * 1000)
        info['attempts'].append(attempt)
        info['http_used'] |= attempt['http_used']
        if info['ok'] or not retryable or number == MAX_ATTEMPTS:
            break
        delay = RETRY_DELAYS[number - 1]
        if time.monotonic() + delay >= started + PROBE_BUDGET:
            break
        sleep(delay)
    for field in ('http_status', 'content_type', 'error_type', 'error', 'final_url',
                  'final_protocol', 'bytes_read', 'codec', 'audio_packets'):
        if field in info['attempts'][-1]:
            info[field] = info['attempts'][-1][field]
    if info['http_used']:
        info['security_warning'] = 'unencrypted_http_audio'
    info['elapsed_ms'] = round((time.monotonic() - started) * 1000)
    return info
