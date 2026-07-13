#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import asdict, dataclass
from pathlib import Path
from bs4 import BeautifulSoup
BASE_DIR=Path(__file__).resolve().parents[2] if 'plugins/government' in str(Path(__file__).resolve()) else Path.cwd()
RAW_DIR=BASE_DIR/'data'/'government'/'raw'
NORMALIZED_DIR=BASE_DIR/'data'/'government'/'normalized'
@dataclass
class NormalizedOpportunity:
    source:str; source_id:str; source_url:str; title:str; ministry:str; organization:str
    application_period:str; application_start:str; application_deadline:str; target:str
    support_summary:str; application_method:str; contact:str; content:str; content_hash:str; fetched_at:str

def clean_text(value:str)->str:
    value=(value or '').replace('\xa0',' ')
    value=re.sub(r'[ \t\r\f\v]+',' ',value)
    value=re.sub(r'\n\s*\n+','\n',value)
    return value.strip()

def remove_noise(soup):
    for tag in soup(['script','style','noscript','svg','nav','footer','header','form','button']): tag.decompose()

def extract_meta(soup,*names):
    for name in names:
        tag=soup.find('meta',attrs={'property':name}) or soup.find('meta',attrs={'name':name})
        if tag and tag.get('content'):
            v=clean_text(tag['content'])
            if v:return v
    return ''

def extract_title(soup):
    candidates=[extract_meta(soup,'og:title','twitter:title')]
    for selector in ('h1','.view-title','.board-title','.detail-title','.tit','.title','h2'):
        e=soup.select_one(selector)
        if e:candidates.append(clean_text(e.get_text(' ',strip=True)))
    if soup.title:candidates.append(clean_text(soup.title.get_text(' ',strip=True)))
    for v in candidates:
        if v and len(v)>=5:
            return re.sub(r'\s*[|>-]\s*기업마당.*$','',v)[:300]
    return ''

def extract_bizinfo_fields(soup):
    result={}
    for label in soup.select('span.s_title'):
        key=clean_text(label.get_text(' ',strip=True)); parent=label.find_parent('li')
        if not parent: continue
        value_el=parent.select_one('.txt')
        if not value_el: continue
        value=clean_text(value_el.get_text('\n',strip=True))
        if key and value: result[key]=value
    return result

def table_key_values(soup):
    result={}
    for row in soup.select('tr'):
        cells=row.find_all(['th','td'],recursive=False) or row.find_all(['th','td'])
        if len(cells)>=2:
            for i in range(0,len(cells)-1,2):
                k=clean_text(cells[i].get_text(' ',strip=True)); v=clean_text(cells[i+1].get_text(' ',strip=True))
                if k and v and len(k)<=50: result.setdefault(k,v)
    for group in soup.select('dl'):
        for term,desc in zip(group.find_all('dt'),group.find_all('dd')):
            k=clean_text(term.get_text(' ',strip=True)); v=clean_text(desc.get_text(' ',strip=True))
            if k and v: result.setdefault(k,v)
    return result

def find_value(mapping,keywords):
    for k,v in mapping.items():
        nk=re.sub(r'\s+','',k)
        if any(word in nk for word in keywords): return v
    return ''

def extract_dates(period):
    dates=re.findall(r'(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})',period)
    n=[f'{y}-{int(m):02d}-{int(d):02d}' for y,m,d in dates]
    return (n[0],n[-1]) if len(n)>=2 else ('',n[0]) if len(n)==1 else ('','')

def split_business_overview(overview):
    if not overview:return '',''
    parts=[clean_text(p) for p in re.split(r'(?=☞)',overview) if clean_text(p)]
    arrows=[p for p in parts if p.startswith('☞')]
    target=arrows[0].lstrip('☞').strip() if arrows else ''
    support=' '.join(p.lstrip('☞').strip() for p in arrows[1:]) if len(arrows)>=2 else ''
    return target[:2000],support[:3000]

def extract_main_content(soup):
    e=soup.select_one('.view_cont')
    if e:
        t=clean_text(e.get_text('\n',strip=True))
        if len(t)>=100:return t[:30000]
    return clean_text(soup.get_text('\n',strip=True))[:30000]

def normalize(meta_path):
    md=json.loads(meta_path.read_text(encoding='utf-8'))
    html_path=BASE_DIR/md['html_file']
    raw=html_path.read_bytes()
    try: text=raw.decode('utf-8')
    except UnicodeDecodeError: text=raw.decode('cp949',errors='replace')
    soup=BeautifulSoup(text,'html.parser'); remove_noise(soup)
    mapping={**table_key_values(soup),**extract_bizinfo_fields(soup)}
    overview=find_value(mapping,('사업개요','사업내용'))
    ov_target,ov_support=split_business_overview(overview)
    period=find_value(mapping,('신청기간','접수기간','모집기간','사업기간'))
    start,deadline=extract_dates(period)
    return NormalizedOpportunity(
        source=md.get('source',''),source_id=md.get('source_id',''),source_url=md.get('source_url',''),
        title=extract_title(soup),
        ministry=find_value(mapping,('소관부처·지자체','소관부처','지자체')),
        organization=find_value(mapping,('사업수행기관','수행기관','주관기관','접수기관')),
        application_period=period,application_start=start,application_deadline=deadline,
        target=find_value(mapping,('지원대상','신청대상','사업대상','대상기업')) or ov_target,
        support_summary=find_value(mapping,('지원내용','지원규모','지원금액')) or ov_support,
        application_method=find_value(mapping,('사업신청방법','신청방법','접수방법')),
        contact=find_value(mapping,('문의처','문의','담당부서','연락처')),
        content=extract_main_content(soup),content_hash=md.get('content_hash',''),fetched_at=md.get('fetched_at',''))

def latest_meta():
    files=list(RAW_DIR.glob('*.json'))
    if not files: raise FileNotFoundError(f'수집 메타데이터가 없습니다: {RAW_DIR}')
    return max(files,key=lambda p:p.stat().st_mtime)

def save(o):
    NORMALIZED_DIR.mkdir(parents=True,exist_ok=True)
    p=NORMALIZED_DIR/f'{o.source}_{o.source_id}.json'
    p.write_text(json.dumps(asdict(o),ensure_ascii=False,indent=2),encoding='utf-8')
    return p

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('metadata',nargs='?'); args=ap.parse_args()
    try:
        mp=Path(args.metadata).expanduser().resolve() if args.metadata else latest_meta()
        o=normalize(mp); p=save(o)
        print('✅ 표준화 완료'); print(f'📌 제목: {o.title or "(추출 실패)"}')
        print(f'🏛️ 소관부처·지자체: {o.ministry or "(추출 실패)"}')
        print(f'🏢 수행기관: {o.organization or "(추출 실패)"}')
        print(f'📅 신청기간: {o.application_period or "(추출 실패)"}')
        print(f'🗓️ 마감일: {o.application_deadline or "(추출 실패)"}')
        print(f'🎯 지원대상: {o.target[:120] or "(추출 실패)"}')
        print(f'💡 지원내용: {o.support_summary[:120] or "(추출 실패)"}')
        print(f'📝 신청방법: {o.application_method[:120] or "(추출 실패)"}')
        print(f'☎️ 문의처: {o.contact[:120] or "(추출 실패)"}')
        print(f'📄 본문 길이: {len(o.content)}자'); print(f'💾 저장: {p.relative_to(BASE_DIR)}')
        return 0 if o.title else 2
    except Exception as e:
        print(f'❌ 표준화 중 오류: {e}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
