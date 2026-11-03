#!/usr/bin/env python3
"""Regenerate Primuse radio playlists and self-hosted artwork.

Local mode produces an immediately importable M3U with external artwork URLs.
Publish mode uses your GitHub repository URL for artwork, and may refresh
artwork / cautiously repair stale stream links using Radio Browser data.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'stations.json'
LOGOS = ROOT / 'logos'
M3U = ROOT / 'radio.m3u'
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

def search_station(session,station):
    # Radio Browser is community-maintained; results are hints, never definitive.
    for base in RADIO_BROWSER:
        try:
            r=session.get(base+'/json/stations/search',params={
                'name':station['search'].split()[0], 'countrycode':'US',
                'hidebroken':'true','limit':35,'order':'votes','reverse':'true',
            },timeout=9,headers={'User-Agent':'PrimusePersonalRadioList/1.0'})
            r.raise_for_status()
            records=r.json()
            if not isinstance(records,list): continue
            candidates=sorted(((candidate_score(station,x),x) for x in records),
                              key=lambda x:x[0],reverse=True)
            if candidates and candidates[0][0]>=55:
                return candidates[0]
            return (0,None)
        except Exception:
            continue
    return (0,None)

def fetch_logo_url(session,url):
    if not url.startswith('https://'): return None
    try:
        r=session.get(url,timeout=12,headers={'User-Agent':'Mozilla/5.0'},stream=True)
        r.raise_for_status()
        data=b''
        for chunk in r.iter_content(32768):
            data+=chunk
            if len(data)>2_000_000: return None
        im=Image.open(io.BytesIO(data))
        if im.width < 64 or im.height < 64: return None
        im=ImageOps.exif_transpose(im).convert('RGBA')
        im.thumbnail((480,480),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(512,512),'white')
        canvas.alpha_composite(im,((512-im.width)//2,(512-im.height)//2))
        return canvas.convert('RGB')
    except Exception:
        return None

def stream_works(session,url):
    if not url.startswith('https://'): return False
    try:
        with session.get(url,stream=True,timeout=(5,8),headers={
            'User-Agent':'PrimusePersonalRadioList/1.0',
            'Icy-MetaData':'0',
        },allow_redirects=True) as res:
            if res.status_code not in (200,206): return False
            mime=res.headers.get('Content-Type','').lower()
            # A server that returns a website instead of audio is not a working radio.
            if 'text/html' in mime or 'application/json' in mime: return False
            return any(x in mime for x in ('audio','mpegurl','octet-stream','application/vnd.apple')) or url.endswith('.m3u8')
    except Exception:
        return False

def escape_attr(s):
    return str(s).replace('"','').replace('\n',' ').replace('\r',' ')

def generate(stations,repo):
    result=['#EXTM3U']
    for s in stations:
        if repo:
            logo=f'https://raw.githubusercontent.com/{repo}/main/logos/{s["id"]}.png'
        else:
            # This immediate-use copy has externally hosted cover URLs only where known.
            logo=s.get('logo_source') or ''
            if s['id']=='kexp-90-3':
                logo='https://thumb.wikimedia.org/wikipedia/commons/thumb/d/dd/KEXP_logo_%28black_on_orange%29.svg/500px-KEXP_logo_%28black_on_orange%29.svg.png'
            if not logo:
                logo='https://www.google.com/s2/favicons?domain='+hostname(s['homepage'])+'&sz=256'
        title=escape_attr(s['name'])
        group=escape_attr(s['group'])
        result.append(f'#EXTINF:-1 tvg-logo="{escape_attr(logo)}" logo="{escape_attr(logo)}" group-title="{group}",{title}')
        result.append(s['stream'])
    M3U.write_text('\n'.join(result)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--publish',action='store_true',help='Build absolute self-hosted artwork URLs using GITHUB_REPOSITORY')
    parser.add_argument('--refresh',action='store_true',help='Look up station art and carefully repair links')
    args=parser.parse_args()
    repo=os.environ.get('GITHUB_REPOSITORY','') if args.publish else ''
    if args.publish and (not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+',repo)):
        parser.error('GITHUB_REPOSITORY must be present, e.g. username/primuse-radio-list')
    stations=json.loads(CATALOG.read_text(encoding='utf-8'))
    LOGOS.mkdir(exist_ok=True)
    if args.refresh:
        import requests
        session=requests.Session()
    for s in stations:
        path=LOGOS/(s['id']+'.png')
        if not path.exists():
            artwork_placeholder(s).save(path,'PNG',optimize=True)
        if not args.refresh: continue
        score,candidate=search_station(session,s)
        url = s.get('logo_source') if s.get('manual_lock') else ''
        if not url and candidate and score>=55:
            url=candidate.get('favicon','')
        img = None  # Preserve custom artwork
        if img is not None:
            buf=io.BytesIO(); img.save(buf,'PNG',optimize=True)
            if path.read_bytes()!=buf.getvalue(): path.write_bytes(buf.getvalue())
        # Only switch link on repeated failure and a strongly verified directory
        # candidate with a matching official website and a working replacement.
        good=stream_works(session,s['stream'])
        if good:
            s['fail_count']=0
        else:
            s['fail_count']=min(20,int(s.get('fail_count',0))+1)
            candidate_url=(candidate or {}).get('url_resolved','')
            if (s['fail_count']>=3 and not s.get('manual_lock') and
                score>=90 and site_match(s['homepage'],candidate.get('homepage','')) and
                candidate_url and candidate_url!=s['stream'] and
                stream_works(session,candidate_url)):
                print('Repairing stream for',s['name'])
                s['stream']=candidate_url
                s['fail_count']=0
        print(s['name'],'ok' if good else 'needs review', 'candidate-score',score)
    if args.refresh:
        CATALOG.write_text(json.dumps(stations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    generate(stations,repo)
    count=sum(1 for line in M3U.read_text().splitlines() if line.startswith('#EXTINF:'))
    print('Wrote',M3U,'stations:',count,'artwork:',len(list(LOGOS.glob('*.png'))),'github repo:',repo or 'none')

if __name__=='__main__': main()
