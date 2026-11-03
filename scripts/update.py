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

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'stations.json'
LOGOS = ROOT / 'logos'
M3U = ROOT / 'radio.m3u'
HEALTH_LOG = ROOT / 'logs' / 'stream-health.jsonl'
MAX_HEALTH_RUNS = 30
DEFAULT_REPO = 'th3cyrus/Apple'
RADIO_BROWSER = [
    'https://de1.api.radio-browser.info',
    'https://nl1.api.radio-browser.info',
    'https://at1.api.radio-browser.info',
]
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
    except ValueError: return ''

def site_match(a,b):
    a,b=hostname(a),hostname(b)
    return bool(a and b and (a==b or a.endswith('.'+b) or b.endswith('.'+a)))

def simplify(s):
    return re.sub(r'[^a-z0-9]','',s.lower())

def candidate_score(station,c):
    if c.get('countrycode') not in (None,'US'): return -1
    if not c.get('lastcheckok',True): return -1
    key=simplify(station['search'].split()[0])
    name=simplify(c.get('name',''))
    if len(key)<3 or key not in name: return -1
    score=55 if name.startswith(key) else 40
    if site_match(station['homepage'],c.get('homepage','')): score+=45
    score += min(10,max(0,int(c.get('votes',0) or 0))//20)
    return score

def safe_message(exc):
    """Retain diagnostic exception text but strip URL query parameters."""
    return re.sub(r'(https?://[^\s?]+)\?[^\s)]+', r'\1?[redacted]', str(exc))[:500]

def safe_url(url):
    try:
        parts = urlsplit(url)
        return parts._replace(query='[redacted]' if parts.query else '', fragment='').geturl()
    except ValueError:
        return '[invalid URL]'

def search_station(session,station):
    """Try the configured Radio Browser mirrors and record every attempt."""
    attempts=[]
    for base in RADIO_BROWSER:
        attempt={'server':base}
        start=time.monotonic()
        try:
            res=session.get(base+'/json/stations/search',params={
                'name':station['search'].split()[0], 'countrycode':'US',
                'hidebroken':'true','limit':35,'order':'votes','reverse':'true',
            },timeout=9,headers={'User-Agent':'PrimusePersonalRadioList/1.0'})
            attempt['http_status']=res.status_code
            res.raise_for_status()
            records=res.json()
            if not isinstance(records,list):
                attempt.update(error_type='UnexpectedResponse',error='Non-list JSON returned')
                continue
            attempt['results']=len(records)
            candidates=sorted(((candidate_score(station,x),x) for x in records),
                              key=lambda x:x[0],reverse=True)
            score=candidates[0][0] if candidates else 0
            attempt['candidate_score']=score
            if score>=55:
                return score,candidates[0][1],attempts
            return 0,None,attempts
        except Exception as exc:
            attempt.update(error_type=type(exc).__name__,error=safe_message(exc))
        finally:
            attempt['elapsed_ms']=round((time.monotonic()-start)*1000)
            attempts.append(attempt)
    return 0,None,attempts

def stream_check(session,url):
    """Record exact HTTP, MIME, timeout or connection failure diagnostics."""
    info={'ok':False,'url':safe_url(url)}
    started=time.monotonic()
    try:
        if not url.startswith('https://'):
            info.update(error_type='InvalidURL',error='Stream URL must use HTTPS')
            return info
        with session.get(url,stream=True,timeout=(5,8),headers={
            'User-Agent':'PrimusePersonalRadioList/1.0',
            'Icy-MetaData':'0',
        },allow_redirects=True) as res:
            info['http_status']=res.status_code
            mime=res.headers.get('Content-Type','').lower()
            info['content_type']=mime
            if res.status_code not in (200,206):
                info.update(error_type='HTTPStatus',error=f'HTTP {res.status_code}: {res.reason}')
            elif 'text/html' in mime or 'application/json' in mime:
                info.update(error_type='UnexpectedContentType',error=f'Expected audio, got {mime}')
            elif any(x in mime for x in ('audio','mpegurl','octet-stream','application/vnd.apple')) or urlsplit(url).path.endswith('.m3u8'):
                info['ok']=True
            else:
                info.update(error_type='UnexpectedContentType',error=f'Unrecognized Content-Type: {mime or "missing"}')
    except Exception as exc:
        info.update(error_type=type(exc).__name__,error=safe_message(exc))
    finally:
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
        score,candidate,attempts=search_station(session,s)
        record['radio_browser']={'candidate_score':score,'attempts':attempts}
        check=stream_check(session,s['stream'])
        record['stream_check']=check
        good=check['ok']
        repaired=False
        if good:
            s['fail_count']=0
        else:
            s['fail_count']=min(20,int(s.get('fail_count',0))+1)
            candidate_url=(candidate or {}).get('url_resolved','')
            eligible=(s['fail_count']>=3 and not s.get('manual_lock') and
                score>=90 and candidate is not None and
                site_match(s['homepage'],candidate.get('homepage','')) and
                candidate_url and candidate_url!=s['stream'])
            if eligible:
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
        print(s['name'],record['status'],'candidate-score',score,
              'error',check.get('error_type',''),check.get('error',''))
    if args.refresh:
        CATALOG.write_text(json.dumps(stations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    generate(stations,repo)
    if args.refresh:
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
