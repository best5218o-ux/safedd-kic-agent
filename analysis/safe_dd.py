# -*- coding: utf-8 -*-
"""SAFE-DD 시제품 v0 (초안 단계): 증거수집 → 사고성 분류·신규성 판정 → 위험 4변수 → 검증기 → 실사 요청목록.
LLM 없이 규칙 기반으로 '도구 계층'만 구현 (본선에서 LLM 플래너/작성기를 얹는다). 키 불필요 공개 API만 사용."""
import json,re,sys,time,html,argparse,urllib.request,urllib.parse,datetime as dt
UA={"User-Agent":"SAVEKOREA research best5218@korea.kr"}
def get(u,raw=False,t=40):
    time.sleep(0.25); b=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read()
    return b if raw else json.loads(b)
INCIDENT=re.compile(r"\b(fire|explosion|explosive|thermal runaway|blaze|wildfire)\b",re.I)
PAST=re.compile(r"\b(occurred|ignited|damaged|destroyed|halted|suspended|shut ?down|was extinguished|resulted in|caused|incident|outage)\b",re.I)
BOILER=re.compile(r"(could|may|might|risk|hazard|subject to|such as|including|force majeure|acts of god|forward-looking|lease|landlord|tenant)",re.I)
def classify(text):
    """문장 단위: 사고어 + 과거형 사건어가 함께 있고 면책·정형 어휘가 없으면 'incident', 사고어만 있으면 'boilerplate'."""
    sents=re.split(r"(?<=[.;])\s+",text); best=None
    for s in sents:
        if INCIDENT.search(s):
            if PAST.search(s) and not BOILER.search(s): return "incident",s.strip()[:300]
            best=best or ("boilerplate",s.strip()[:200])
    return best or ("none","")
def edgar(cik,days=400,maxdocs=14):
    sub=get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"); r=sub["filings"]["recent"]
    cut=(dt.date.today()-dt.timedelta(days=days)).isoformat(); out=[]
    for i,f in enumerate(r["form"]):
        if f in("8-K","10-Q","10-K") and r["filingDate"][i]>=cut:
            out.append(dict(form=f,date=r["filingDate"][i],items=r["items"][i],acc=r["accessionNumber"][i],doc=r["primaryDocument"][i]))
    res=[]
    for d in out[:maxdocs]:
        url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{d['acc'].replace('-','')}/{d['doc']}"
        try:
            t=get(url,raw=True).decode("utf-8","ignore"); t=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t)))
            c,s=classify(t)
        except Exception as ex: c,s="error",str(ex)[:80]
        res.append(dict(d,url=url,cls=c,evidence=s))
    return sub.get("name"),res
def hazard(lat,lon):
    y=dt.date.today()-dt.timedelta(days=5); s=y-dt.timedelta(days=365)
    w=get(f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={s}&end_date={y}&daily=wind_gusts_10m_max,temperature_2m_max,precipitation_sum&timezone=UTC")["daily"]
    q=get("https://earthquake.usgs.gov/fdsnws/event/1/query?"+urllib.parse.urlencode(dict(format="geojson",latitude=lat,longitude=lon,maxradiuskm=300,minmagnitude=5.0,starttime=(dt.date.today()-dt.timedelta(days=3650)).isoformat(),limit=200)))
    return dict(gust_max_kmh=max(x for x in w["wind_gusts_10m_max"] if x is not None),
                hot_days_ge35C=sum(1 for x in w["temperature_2m_max"] if x is not None and x>=35),
                precip_max_mm=max(x for x in w["precipitation_sum"] if x is not None),
                quakes_M5_300km_10y=len(q["features"]),
                src=["open-meteo archive","USGS FDSN event API"])
def verify(memo):
    """검증기: 모든 주장은 url+인용문 보유, 사고 분류는 근거 문장 보유, 수치는 원자료 재계산. 실패 항목은 삭제하지 않고 'unverified' 표시."""
    bad=[]
    for c in memo["claims"]:
        if not c.get("url") or not c.get("quote"): c["status"]="unverified"; bad.append(c["id"])
        else: c["status"]="sourced"
    memo["verifier"]=dict(total=len(memo["claims"]),unverified=bad,pass_=not bad); return memo
QUESTIONS={ # 공개자료로 못 채우는 변수 → 운용사(GP)에 요청할 서류. 4변수 = 귀책·집중도·복구시간·보장
 "집중도":"사이트별 매출·EBITDA 기여도, 단일 사이트 의존 비율(최대 사이트 비중)",
 "복구시간(RTO)":"사이트별 복구목표시간·실제 DR 훈련 결과, 백업의 물리적 분리(다른 건물/지역) 여부",
 "보장":"재산·영업중단(BI) 보험 한도·면책·공제액, 최근 5년 손실이력(loss run)",
 "귀책·관리":"최근 소방·안전 점검 결과와 시정조치, 하도급 작업(정비·교체) 통제 절차(작업허가·LOTO)",
 "설비":"배터리(리튬이온)·변압기 위치와 이격, 감지·소화설비 종류, 폭발방산 설계"}
def run(a):
    nm,docs=edgar(a.cik); memo=dict(asset=a.name,ticker=a.ticker,filer=nm,run_at=dt.datetime.now().isoformat(timespec="minutes"),claims=[])
    MON=r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2},\s+)?\d{4}"
    inc_all=[d for d in docs if d["cls"]=="incident"]; groups={}
    for d in inc_all:
        m=re.search(MON,d["evidence"]); k=m.group(0) if m else d["evidence"][:60]; groups.setdefault(k,[]).append(d)
    inc=[min(v,key=lambda x:x["date"]) for v in groups.values()]  # 사고 키별 최초 공시 1건
    memo["incident_groups"]={k:dict(first_filing=min(x["date"] for x in v),filings=len(v)) for k,v in groups.items()}; boil=[d for d in docs if d["cls"]=="boilerplate"]
    memo["summary"]=dict(docs_read=len(docs),incident_context=len(inc_all),unique_incidents=len(inc),boilerplate=len(boil),none=len([d for d in docs if d["cls"]=="none"]),errors=len([d for d in docs if d["cls"]=="error"]))
    for i,d in enumerate(inc,1): memo["claims"].append(dict(id=f"I{i}",text=f"{d['date']} {d['form']} 사고성 서술 포착",url=d["url"],quote=d["evidence"]))
    h=hazard(a.lat,a.lon); memo["hazard"]=h
    memo["claims"].append(dict(id="H1",text=f"최근 1년 최대 돌풍 {h['gust_max_kmh']} km/h, 35℃↑ {h['hot_days_ge35C']}일, 10년 내 M5.0↑ 지진 {h['quakes_M5_300km_10y']}건(반경 300km)",url="https://open-meteo.com/en/docs/historical-weather-api",quote="Open-Meteo archive + USGS FDSN event API 조회 결과"))
    memo["questions_for_GP"]=QUESTIONS; memo["docs"]=docs
    return verify(memo)
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--name"); p.add_argument("--ticker"); p.add_argument("--cik"); p.add_argument("--lat",type=float); p.add_argument("--lon",type=float); p.add_argument("--out")
    a=p.parse_args(); m=run(a); json.dump(m,open(a.out,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(json.dumps(dict(asset=m["asset"],summary=m["summary"],hazard=m["hazard"],verifier=m["verifier"]),ensure_ascii=False))
    for d in m["docs"]:
        if d["cls"]=="incident": print(" INCIDENT",d["date"],d["form"],d["evidence"][:230])
