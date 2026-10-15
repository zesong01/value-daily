"""Twice-daily primary-source collection. No fabricated analysis or rolling dates.

Editorial research dates are immutable until an actual research revision. New
quotes and filings are evidence, not automatic changes to an investment thesis.
"""
import concurrent.futures as futures
import csv
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'public' / 'reports'
TZ = ZoneInfo('Asia/Shanghai')
NOW = datetime.now(TZ)
DATE = NOW.date().isoformat()
EDITION = 'AM' if NOW.hour < 13 else 'PM'
STAMP = NOW.isoformat(timespec='seconds')
AGENT = 'Mozilla/5.0 (compatible; ValueDaily/1.0; +https://github.com/zesong01/value-daily)'

def request(url, form=None):
    data = urllib.parse.urlencode(form).encode() if form else None
    headers = {'User-Agent': AGENT, 'Accept': 'application/json,text/html,application/xml,text/csv,*/*', 'Accept-Language':'zh-CN,zh;q=0.9,en;q=0.7'}
    if form: headers['Content-Type']='application/x-www-form-urlencoded; charset=UTF-8'
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,data=data,headers=headers)
            with urllib.request.urlopen(req, timeout=25) as res:
                raw=res.read(5_000_001)
                if len(raw)>5_000_000: raise ValueError('Source exceeds collection size limit')
                return raw.decode('utf-8-sig',errors='replace')
        except Exception:
            if attempt==2: raise
            time.sleep(1+attempt)

def clean(s):
    s=re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', s,flags=re.S|re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ',s))).strip()

def num(value):
    n=float(str(value).replace(',','').replace('%','').strip())
    if not (-1e12<n<1e12): raise ValueError('Invalid numeric data')
    return n

def source(id,title,publisher,url,published,period):
    return dict(id=id,title=title,publisher=publisher,url=url,publishedDate=published,dataPeriod=period,accessedAt=DATE)

def csi():
    url='https://www.csindex.com.cn/csindex-home/perf/index-perf-oneday?indexCode=000300'
    data=json.loads(request(url))['data']['intraDayHeader']
    day=str(data['tradeDate']); clock=str(data.get('tradeTime',''))
    if re.fullmatch(r'\d{8}',day):day=f'{day[:4]}-{day[4:6]}-{day[6:]}'
    datetime.strptime(day,'%Y-%m-%d')
    if day>DATE:raise ValueError('Future observation date')
    return {'market':dict(code='CSI 300',value=num(data['current']),change=num(data['changePct']),changeUnit='%',asOf=(day+' '+clock).strip(),status='官方行情 · 以显示时点为准',sourceIds=['live-csi']), 'sources':[source('live-csi','沪深300官方指数行情','中证指数',url,day,day+' '+clock)]}

def nasdaq():
    url='https://api.nasdaq.com/api/quote/COMP/info?assetclass=index'
    raw=json.loads(request(url)); data=raw['data']; p=data['primaryData']
    if raw.get('status',{}).get('rCode',200)!=200:raise ValueError('Provider error')
    observed=str(p['lastTradeTimestamp'])
    return {'market':dict(code='NASDAQ',value=num(p['lastSalePrice']),change=num(p['percentageChange']),changeUnit='%',asOf=observed,status='非实时 · '+str(data.get('marketStatus','')),sourceIds=['live-nasdaq']), 'sources':[source('live-nasdaq','Nasdaq Composite 官方行情','Nasdaq',url,observed,observed+' / America/New_York')]}

def treasury():
    year=NOW.year
    url=f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv'
    rows=list(csv.DictReader(io.StringIO(request(url))))
    valid=[]
    for r in rows:
        try:
            day=datetime.strptime(r['Date'],'%m/%d/%Y').date()
            if day<=NOW.date():valid.append((day,num(r['10 Yr'])))
        except (ValueError,KeyError,TypeError):pass
    valid.sort(reverse=True)
    if not valid:raise ValueError('No valid Treasury observations')
    day,value=valid[0];delta=round((value-valid[1][1])*100,4) if len(valid)>1 else None
    return {'market':dict(code='US 10Y',value=value,change=delta,changeUnit='bp',asOf=day.isoformat(),status='官方日度收益率 · 非实时',sourceIds=['live-treasury']), 'sources':[source('live-treasury','Daily Treasury Par Yield Curve Rates','美国财政部',url,day.isoformat(),'10年期 / '+day.isoformat())]}

def fed():
    root=ET.fromstring(request('https://www.federalreserve.gov/feeds/press_monetary.xml'))
    items=[];sources=[]
    for item in root.findall('./channel/item')[:5]:
        title=clean(item.findtext('title',''));url=item.findtext('link','').strip();published=item.findtext('pubDate','')
        if not url.startswith('https://www.federalreserve.gov/'):continue
        dt=parsedate_to_datetime(published)
        if dt>NOW:continue
        # Open the linked original; RSS alone is a discovery feed.
        body=request(url)
        if len(clean(body))<200:continue
        ident='fed-'+hashlib.sha256(url.encode()).hexdigest()[:10]
        items.append(dict(title=title,publisher='美联储',url=url,publishedAt=dt.strftime('%Y-%m-%d'),summary='原始政策发布。需区分利率决议、实施说明与会议纪要；不据标题推断利率变化。'))
        sources.append(source(ident,title,'美联储',url,dt.isoformat(),'官方发布日 '+dt.strftime('%Y-%m-%d')))
        if len(items)==3:break
    if not items:raise ValueError('No verified Federal Reserve publications')
    return {'evidence':items,'sources':sources}

def nbs():
    base='https://www.stats.gov.cn/sj/zxfb/'
    body=request(base);items=[];sources=[];seen=set()
    for block in re.findall(r'<li\b[^>]*>(.*?)</li>',body,re.S|re.I):
        date=re.search(r'20\d{2}-\d{2}-\d{2}',clean(block))
        if not date or date[0]>DATE:continue
        links=re.findall(r'<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>',block,re.S|re.I)
        for href,label in links:
            title=clean(label);url=urllib.parse.urljoin(base,html.unescape(href))
            if not title or url in seen or not url.startswith('https://www.stats.gov.cn/'):continue
            if not any(k in title for k in ['价格','采购经理','经济','工业','消费','投资']):continue
            article=request(url)
            if len(clean(article))<200:continue
            seen.add(url);ident='nbs-'+hashlib.sha256(url.encode()).hexdigest()[:10]
            items.append(dict(title=title,publisher='国家统计局',url=url,publishedAt=date[0],summary='已获取官方正文。统计数据期以标题和原文为准，发布日不等于观察期。'))
            sources.append(source(ident,title,'国家统计局',url,date[0],title))
            if len(items)>=3:return {'evidence':items,'sources':sources}
    if not items:raise ValueError('No verifiable statistical releases')
    return {'evidence':items,'sources':sources}

def filings():
    url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
    start=(NOW-timedelta(days=120)).date().isoformat()
    result=json.loads(request(url,dict(stock='301161,nssc1000828',tabName='fulltext',pageSize=10,pageNum=1,column='szse',seDate=f'{start}~{DATE}',isHLtitle='false')))
    if 'announcements' not in result:raise ValueError('Invalid filing response')
    items=[];sources=[]
    for a in (result['announcements'] or [])[:3]:
        title=clean(a['announcementTitle']); day=datetime.fromtimestamp(a['announcementTime']/1000,TZ).date().isoformat()
        path=a['adjunctUrl']
        if not re.fullmatch(r'finalpage/[0-9-]+/[A-Za-z0-9.-]+\.PDF',path,re.I):continue
        pdf='https://static.cninfo.com.cn/'+path
        items.append(dict(title='唯万密封 · '+title,publisher='巨潮资讯 · 公司公告',url=pdf,publishedAt=day,summary='公告已在官方目录核实；PDF财务数字尚未经自动提取复核，不据此更新公司财务或估值结论。'))
        sources.append(source('filing-'+str(a['announcementId']),title,'巨潮资讯',pdf,day,'公告目录核验；正文待研究复核'))
    return {'evidence':items,'sources':sources,'checkedFilings':True}

def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def main():
    previous=load(REPORTS/'latest.json');report=json.loads(json.dumps(previous))
    successes={};failures={}
    collectors={'中证指数':csi,'Nasdaq':nasdaq,'美国财政部':treasury,'美联储':fed,'国家统计局':nbs,'巨潮资讯':filings}
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs={pool.submit(fn):name for name,fn in collectors.items()}
        for job in futures.as_completed(jobs):
            name=jobs[job]
            try:successes[name]=job.result();print(name+': OK')
            except Exception as e:failures[name]=type(e).__name__;print(name+': collection unavailable ('+type(e).__name__+')')
    status=dict(checkedAt=STAMP,successes=list(successes),failures=failures,mode='官方数据与证据采集')
    # Failure does not relabel an old report as fresh.
    if not successes:
        save(REPORTS/'update-status.json',status)
        raise RuntimeError('All sources failed. Previous reports remain unchanged.')
    by_source={s['id']:s for s in report['sources']}
    evidence=[]
    for result in successes.values():
        for s in result.get('sources',[]):by_source[s['id']]=s
        evidence.extend(result.get('evidence',[]))
        if 'market' in result:
            quote=result['market']
            for market in report['markets']:
                if market['code']==quote['code']:market.update(quote)
    evidence=sorted({e['url']:e for e in evidence}.values(),key=lambda x:x['publishedAt'],reverse=True)[:9]
    report['evidenceUpdates']=evidence
    # Keep only referenced and newly collected source IDs; never silently grow forever.
    ids=set()
    def refs(v):
        if isinstance(v,dict):
            ids.update(v.get('sourceIds',[]))
            for k,x in v.items():
                if k!='sources':refs(x)
        elif isinstance(v,list):
            for x in v:refs(x)
    refs(report)
    for result in successes.values():ids.update(s['id'] for s in result.get('sources',[]))
    report['sources']=[s for id,s in by_source.items() if id in ids]
    for name in failures:
        code={'中证指数':'CSI 300','Nasdaq':'NASDAQ','美国财政部':'US 10Y'}.get(name)
        for market in report['markets']:
            if market['code']==code:market['status']='本次采集失败 · 保留原日期'
    # Same data is a checked status, not a fabricated new edition.
    def signature(r):
        return json.dumps(dict(markets=r['markets'],evidence=r.get('evidenceUpdates',[])),sort_keys=True,ensure_ascii=False)
    if signature(report)==signature(previous):
        save(REPORTS/'update-status.json',{**status,'contentChanged':False,'lastReport':previous['date']+'-'+previous['edition']})
        print('No new evidence. Retained the published report and research date.');return
    report['date']=DATE;report['edition']=EDITION;report['publishedAt']=STAMP
    report['title']=('早间' if EDITION=='AM' else '收盘')+'市场与官方证据更新'
    report['cutoff']='数据采集 '+STAMP+'；行情与公告各自保留观察日期和时区'
    baseline=previous.get('freshness',{}).get('researchUpdatedAt',previous['publishedAt'])
    report['freshness']=dict(checkedAt=STAMP,researchUpdatedAt=baseline,mode='数据已更新 · 研究观点维持',reason='本次自动核验行情与官方发布。公司财报、估值和投资逻辑沿用标注日期的研究基线；公告出现不代表已完成财报复核。')
    missing=[m['name'] for m in report['markets'] if m['value'] is None]
    report['completeness']='部分数据待核实'
    report['coverageNote']='行情按各自来源日期展示；'+('、'.join(missing)+'暂未接入可核验报价。' if missing else '')+('本次未成功采集：'+'、'.join(failures)+'。' if failures else '')+'财报和投资观点保留独立研究日期，不将数据刷新当作评级变化。'
    report['flow']['observation']='成交额、完整行业表现与资金流尚未完成一手核验；不能从指数涨跌推断资金净流入。'
    # Maintain the original thesis verbatim and disclose the scope of this update.
    for t in report['tracking']:
        if '基线' not in t['update'] and '自动采集' not in t['update']:continue
        t['update']='自动采集已检查最新官方发布。尚无新的人工复核财务或估值证据，维持原研究条件；研究基线日期 '+baseline[:10]+'。'
    identifier=DATE+'-'+EDITION
    existing=REPORTS/(identifier+'.json')
    if existing.exists():
        old=load(existing);rev=hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()[:12]
        versions=REPORTS/'revisions';versions.mkdir(exist_ok=True)
        save(versions/(identifier+'-'+rev+'.json'),old)
    save(existing,report);save(REPORTS/'latest.json',report)
    index=load(REPORTS/'index.json')
    index['entries']=[e for e in index['entries'] if e['id']!=identifier]
    index['entries'].append({k:report[k] for k in ['date','edition','title','publishedAt']}|{'id':identifier})
    index['entries'].sort(key=lambda e:e['id'],reverse=True)
    save(REPORTS/'index.json',index)
    save(REPORTS/'update-status.json',{**status,'contentChanged':True,'lastReport':identifier})
    print('Published evidence snapshot '+identifier+'; research baseline '+baseline[:10]+'.')

if __name__=='__main__':main()
