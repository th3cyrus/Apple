#!/usr/bin/env python3
"""Regenerate Primuse radio playlists using custom, self-hosted artwork.

Both local and published playlists reference the custom covers in logos/.
Refresh mode may repair radio streams but never replaces custom artwork.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    SSLError as RequestsSSLError,
    Timeout as RequestsTimeout,
)
from radio_browser import RadioBrowserClient

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'stations.json'
LOGOS = ROOT / 'logos'
M3U = ROOT / 'radio.m3u'
HEALTH_LOG = ROOT / 'logs' / 'stream-health.jsonl'
MAX_HEALTH_RUNS = 30
STREAM_CONNECT_TIMEOUT = 5
STREAM_READ_TIMEOUT = 12
STREAM_MAX_ATTEMPTS = 3
STREAM_RETRY_DELAYS = (1, 2)
RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}
DEFAULT_REPO = 'th3cyrus/Apple'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()

def artwork_placeholder(station):
    """Own artwork tile: clearly a station-title placeholder, not an official logo."""
    seed = int(hashlib.sha256(station['id'].encode()).hexdigest()[:8],16)
    hues = [(27,44,79),(35,65,81),(54,46,78),(57,63,72),(39,68,60),(72,47,54)]
    bg = hues[seed % len(hues)]
    image = Image.new('RGB', (512,512), bg)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((26,25,486,487),radius=64,outline=(130,149,159),width=4)
    draw.rounded_rectangle((46,42,466,112),radius=22,fill=(234,232,218))
    draw.text((256,77),'USA  /  LIVE RADIO',font=font(23),fill=(30,45,61),anchor='mm')
    title = station['name']
    size = 76 if len(title)<9 else 59 if len(title)<14 else 47
    while size>26 and draw.textbbox((0,0),title,font=font(size))[2]>424:
        size-=2
    draw.text((256,256),title,font=font(size),fill='white',anchor='mm')
    desc = station.get('description','')[:28]
    while draw.textbbox((0,0),desc,font=font(21))[2]>425: desc=desc[:-1]
    draw.text((256,388),desc,font=font(21),fill=(214,224,232),anchor='mm')
    return image

def hostname(url):
    try: return (urlsplit(url).hostname or '').lower().removeprefix('www.')
    except (ValueError, TypeError, AttributeError): return ''

def site_match(a,b):
    a,b=hostname(a),hostname(b)
    return bool(a and b and (a==b or a.endswith('.'+b) or b.endswith('.'+a)))

def simplify(s):
    return re.sub(r'[^a-z0-9]','',s.lower())

def candidate_score(station,c):
    """Find the correct broadcaster, not merely a similarly named station."""
    if c.get('countrycode') != 'US': return -1
    if c.get('lastcheckok') not in (1, True, '1'): return -1
    words = re.findall(r'[a-z0-9]+', station['search'].lower())
    meaningful = [w for w in words if w not in ('the','radio','fm')]
    if not meaningful: return -1
    key = meaningful[0]
    name = simplify(str(c.get('name','')))
    if len(key)<3 or key not in name: return -1
    # A different channel (jazz/classical) is NOT a replacement for this one.
    variant = [v for v in ('jazz','classical') if v in station['name'].lower()]
    if variant and not all(v in name for v in variant): return -1
    score=55 if name.startswith(key) else 40
    if site_match(station['homepage'],c.get('homepage','')): score+=45
    try:
        votes=max(0,int(c.get('votes',0) or 0))
    except (TypeError,ValueError):
        votes=0
    score+=min(10,votes//20)
    return score


def candidate_rejection_reasons(station, candidate, score):
    """Strong guardrails before changing the maintained playlist."""
    issues=[]
    if not candidate or score < 90:
        return ['no_high_confidence_candidate']
    if not site_match(station['homepage'],candidate.get('homepage','')):
        issues.append('homepage_mismatch')
    if candidate.get('countrycode') != 'US':
        issues.append('wrong_country')
    if candidate.get('lastcheckok') not in (1,True,'1'):
        issues.append('not_recently_working')
    if candidate.get('ssl_error') not in (0,False,'0'):
        issues.append('directory_ssl_error')
    url=candidate.get('url_resolved','')
    try:
        parts=urlsplit(url)
        if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:
            issues.append('unsafe_or_non_https_url')
    except (TypeError,ValueError):
        issues.append('invalid_candidate_url')
    checked=candidate.get('lastchecktime_iso8601')
    try:
        check_time=datetime.fromisoformat(checked.replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-check_time).total_seconds()
        if age<0 or age>14*86400:
            issues.append('stale_directory_health_check')
    except (AttributeError,TypeError,ValueError):
        issues.append('missing_directory_check_date')
    return issues

def safe_message(exc):
    """Retain diagnostic exception text but strip URL query parameters."""
    return re.sub(r'(https?://[^\s?]+)\?[^\s)]+', r'\1?[redacted]', str(exc))[:500]

def safe_url(url):
    try:
        parts = urlsplit(url)
        return parts._replace(query='[redacted]' if parts.query else '', fragment='').geturl()
    except ValueError:
        return '[invalid URL]'



def stream_check(session,url):
    """Probe a stream with bounded retries for temporary network failures.

    A probe is a single station health-check even if the network is retried.
    Detailed per-attempt results are persisted to the stream-health JSONL log.
    """
    info={'ok':False,'url':safe_url(url),'attempts':[]}
    started=time.monotonic()
    if not isinstance(url,str) or not url.startswith('https://'):
        info.update(error_type='InvalidURL',
                    error='Stream URL must use HTTPS',
                    elapsed_ms=round((time.monotonic()-started)*1000))
        return info

    for number in range(1,STREAM_MAX_ATTEMPTS+1):
        attempt={'attempt':number}
        attempt_started=time.monotonic()
        retryable=False
        try:
            with session.get(url,stream=True,
                timeout=(STREAM_CONNECT_TIMEOUT,STREAM_READ_TIMEOUT),
                headers={
                    'User-Agent':'PrimusePersonalRadioList/1.0',
                    'Icy-MetaData':'0',
                },allow_redirects=True) as response:
                attempt['http_status']=response.status_code
                mime=response.headers.get('Content-Type','').lower()
                attempt['content_type']=mime
                if response.status_code not in (200,206):
                    attempt.update(error_type='HTTPStatus',
                        error=f'HTTP {response.status_code}: {response.reason}')
                    retryable=response.status_code in RETRYABLE_HTTP_STATUSES
                elif 'text/html' in mime or 'application/json' in mime:
                    attempt.update(error_type='UnexpectedContentType',
                        error=f'Expected audio, got {mime}')
                elif any(x in mime for x in (
                    'audio','mpegurl','octet-stream','application/vnd.apple',
                )) or urlsplit(url).path.endswith('.m3u8'):
                    attempt['ok']=True
                else:
                    attempt.update(error_type='UnexpectedContentType',
                        error=f'Unrecognized Content-Type: {mime or "missing"}')
        except RequestsSSLError as exc:
            # Certificate verification failures need investigation, not retries.
            attempt.update(error_type=type(exc).__name__,
                           error=safe_message(exc))
        except (RequestsTimeout,RequestsConnectionError) as exc:
            attempt.update(error_type=type(exc).__name__,
                           error=safe_message(exc))
            retryable=True
        except Exception as exc:
            attempt.update(error_type=type(exc).__name__,
                           error=safe_message(exc))
        finally:
            attempt['elapsed_ms']=round((time.monotonic()-attempt_started)*1000)
            info['attempts'].append(attempt)

        if attempt.get('ok'):
            info['ok']=True
            break
        if not retryable or number==STREAM_MAX_ATTEMPTS:
            break
        time.sleep(STREAM_RETRY_DELAYS[number-1])

    # Final result remains backward-compatible for summary/report consumers.
    last=info['attempts'][-1]
    for field in ('http_status','content_type','error_type','error'):
        if field in last:
            info[field]=last[field]
    info['elapsed_ms']=round((time.monotonic()-started)*1000)
    return info

def save_health_report(report):
    HEALTH_LOG.parent.mkdir(parents=True,exist_ok=True)
    previous=HEALTH_LOG.read_text(encoding='utf-8').splitlines() if HEALTH_LOG.exists() else []
    previous=[line for line in previous if line.strip()][-(MAX_HEALTH_RUNS-1):]
    previous.append(json.dumps(report,ensure_ascii=False,separators=(',',':')))
    HEALTH_LOG.write_text('\n'.join(previous)+'\n',encoding='utf-8')

def escape_attr(s):
    return str(s).replace('"','').replace('\n',' ').replace('\r',' ')

def generate(stations,repo):
    # Always use the project's custom station art, never broadcaster logos.
    artwork_repo = repo or DEFAULT_REPO
    result=['#EXTM3U']
    for s in stations:
        artwork=f'logos/{s["id"]}.png'
        if s.get('logo') != artwork:
            raise ValueError(f'Invalid custom artwork path for {s["id"]}')
        if not (ROOT / artwork).is_file():
            raise FileNotFoundError(f'Missing custom artwork: {artwork}')
        logo=f'https://raw.githubusercontent.com/{artwork_repo}/main/{artwork}'
        title=escape_attr(s['name'])
        group=escape_attr(s['group'])
        result.append(f'#EXTINF:-1 tvg-logo="{escape_attr(logo)}" logo="{escape_attr(logo)}" group-title="{group}",{title}')
        result.append(s['stream'])
    M3U.write_text('\n'.join(result)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--publish',action='store_true',help='Build absolute self-hosted artwork URLs using GITHUB_REPOSITORY')
    parser.add_argument('--refresh',action='store_true',help='Check streams and cautiously repair stale links')
    args=parser.parse_args()
    repo=os.environ.get('GITHUB_REPOSITORY','') if args.publish else ''
    if args.publish and (not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+',repo)):
        parser.error('GITHUB_REPOSITORY must be present, e.g. username/primuse-radio-list')
    stations=json.loads(CATALOG.read_text(encoding='utf-8'))
    LOGOS.mkdir(exist_ok=True)
    if args.refresh:
        import requests
        session=requests.Session()
    if args.refresh:
        report={
            'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'github_run_id':os.environ.get('GITHUB_RUN_ID'),
            'github_run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),
            'stations':[],
        }
        browser=None   # Discover the directory only when a stream is broken.
    for s in stations:
        path=LOGOS/(s['id']+'.png')
        if not path.exists():
            artwork_placeholder(s).save(path,'PNG',optimize=True)
        if not args.refresh: continue
        record={
            'id':s['id'],'name':s['name'],
            'original_stream':safe_url(s['stream']),
            'fail_count_before':int(s.get('fail_count',0)),
        }
        check=stream_check(session,s['stream'])
        record['stream_check']=check
        good=check['ok']
        repaired=False
        if good:
            s['fail_count']=0
            record['radio_browser']={'skipped':'stream_is_healthy'}
        else:
            s['fail_count']=min(20,int(s.get('fail_count',0))+1)
            if browser is None:
                browser=RadioBrowserClient(session)
            score,candidate,attempts=browser.search(s,candidate_score)
            record['radio_browser']={
                'candidate_score':score,
                'attempts':attempts,
            }
            if candidate:
                record['radio_browser']['candidate']={
                    'name':candidate.get('name'),
                    'stationuuid':candidate.get('stationuuid'),
                    'homepage':candidate.get('homepage'),
                    'lastchecktime':candidate.get('lastchecktime_iso8601'),
                }
            reasons=candidate_rejection_reasons(s,candidate,score)
            if s['fail_count']<3:
                reasons.append('waiting_for_three_consecutive_failures')
            if s.get('manual_lock'):
                reasons.append('manual_lock_enabled')
            candidate_url=(candidate or {}).get('url_resolved','')
            if candidate_url==s['stream']:
                reasons.append('candidate_same_as_current')
            if reasons:
                record['radio_browser']['replacement_blocked_by']=reasons
            else:
                replacement_check=stream_check(session,candidate_url)
                record['replacement_check']=replacement_check
                if replacement_check['ok']:
                    print('Repairing stream for',s['name'])
                    s['stream']=candidate_url
                    s['fail_count']=0
                    repaired=True
        record['status']='repaired' if repaired else ('ok' if good else 'needs_review')
        record['fail_count_after']=s['fail_count']
        record['current_stream']=safe_url(s['stream'])
        report['stations'].append(record)
        print(s['name'],record['status'],
              'error',check.get('error_type',''),check.get('error',''))
    if args.refresh:
        CATALOG.write_text(json.dumps(stations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    generate(stations,repo)
    if args.refresh:
        report['radio_browser']={
            'discovery':browser.discovery if browser else [],
            'servers':browser.servers if browser else [],
            'failed_servers':sorted(browser.failed_servers) if browser else [],
            'skipped':browser is None,
        }
        report['summary']={
            'total':len(report['stations']),
            'healthy':sum(x['status']=='ok' for x in report['stations']),
            'needs_review':sum(x['status']=='needs_review' for x in report['stations']),
            'repaired':sum(x['status']=='repaired' for x in report['stations']),
        }
        save_health_report(report)
        session.close()
        print('Health report:',HEALTH_LOG,'summary:',report['summary'])



    count=sum(1 for line in M3U.read_text().splitlines() if line.startswith('#EXTINF:'))
    print('Wrote',M3U,'stations:',count,'artwork:',len(list(LOGOS.glob('*.png'))),'github repo:',repo or DEFAULT_REPO)

if __name__=='__main__': main()
