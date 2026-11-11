import json, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if "NotoSansCJK-Regular" in f: fm.fontManager.addfont(f)
plt.rcParams["font.family"]="Noto Sans CJK JP"; plt.rcParams["axes.unicode_minus"]=False
ev=json.load(open("데이터/event_study_paths.json"))
fig,ax=plt.subplots(figsize=(7.2,3.7),dpi=200)
cfg={"PG&E 캠프파이어":("#b71c1c","-","PG&E 캠프파이어"),"Hawaiian Electric 마우이":("#e65100","-","하와이안일렉트릭 마우이"),"Edison Intl 이튼화재":("#8e24aa","-","에디슨 이튼화재"),"Vistra 모스랜딩 ESS":("#757575","--","Vistra(해석 보류)"),"카카오 SK C&C 판교":("#0b5ed7","-","카카오 판교"),"르네사스 나카공장":("#1b7f4b","-","르네사스 나카")}
ends=[]
for e in ev:
    p=e["path"][2:]; base=1+e["path"][2]/100; y=[((1+v/100)/base-1)*100 for v in p]; x=list(range(-1,-1+len(y)))
    c,ls,n=cfg[e["name"]]; ax.plot(x,y,color=c,ls=ls,lw=2.0); ends.append([y[-1],n,c])
ends.sort()
for i in range(1,len(ends)):
    if ends[i][0]-ends[i-1][0]<5.2: ends[i][0]=ends[i-1][0]+5.2
for y,n,c in ends: ax.text(20.6,y,n,color=c,fontsize=8.5,va="center")
ax.axvline(0,color="#444",lw=.8,ls=":"); ax.axhline(0,color="#888",lw=.6)
ax.set_xlim(-1,30); ax.set_ylim(-78,12); ax.set_xticks([0,5,10,15,20])
ax.set_xlabel("사건 첫 반응일(0) 이후 거래일",fontsize=9); ax.set_ylabel("누적 초과수익률 CAR (%)",fontsize=9)
ax.grid(alpha=.2); ax.tick_params(labelsize=8.5)
for s in ("top","right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("그림/fig_car_v2.png")
