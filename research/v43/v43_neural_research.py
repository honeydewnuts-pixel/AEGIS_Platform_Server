import os, json, hashlib, math, random, time
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score, precision_score, recall_score, confusion_matrix, log_loss, brier_score_loss
from sklearn.linear_model import LogisticRegression
import torch
from torch import nn

SEED=4301
np.random.seed(SEED); random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
BASE=Path('/mnt/data/v43_data'); OUT=Path('/mnt/data/AEGIS_V43_WORK'); OUT.mkdir(exist_ok=True)
DATA=BASE/'AEGIS_V43_GBPUSD_32M_M5_BID_ASK.csv'
print('loading',DATA)
df=pd.read_csv(DATA,parse_dates=['datetime'])
df=df.sort_values('datetime').reset_index(drop=True)
# midpoint OHLC and spread
for c in ['mid_open','mid_high','mid_low','mid_close']:
    if c not in df: pass
p=df.mid_close.values.astype('float64'); h=df.mid_high.values.astype('float64'); l=df.mid_low.values.astype('float64'); o=df.mid_open.values.astype('float64')
# Causal Wilder ATR14
tr=np.full(len(df),np.nan)
tr[0]=h[0]-l[0]
tr[1:]=np.maximum(h[1:]-l[1:],np.maximum(np.abs(h[1:]-p[:-1]),np.abs(l[1:]-p[:-1])))
atr=np.full(len(df),np.nan); atr[14]=np.nanmean(tr[1:15])
for i in range(15,len(df)): atr[i]=(13*atr[i-1]+tr[i])/14.0
df['atr14']=atr
# Helpers
X={}
for k in [1,2,3,6,12,24,48]: X[f'ret{k}']=p/pd.Series(p).shift(k).values-1
rng=h-l; body=p-o
X['range_atr']=rng/atr; X['body_atr']=body/atr; X['body_dir']=np.sign(body)
X['upper_wick']=(h-np.maximum(o,p))/atr; X['lower_wick']=(np.minimum(o,p)-l)/atr; X['close_pos']=(p-l)/(rng+1e-12)
for k in [5,10,20,40,60]:
    roll=pd.Series(p).rolling(k)
    mean=roll.mean().values; sd=roll.std(ddof=0).values
    X[f'z_{k}']=(p-mean)/(sd+1e-12); X[f'atr_ratio_{k}']=atr/pd.Series(atr).rolling(k).mean().values
    X[f'high_dist_{k}']=(p-pd.Series(h).rolling(k).max().values)/atr
    X[f'low_dist_{k}']=(p-pd.Series(l).rolling(k).min().values)/atr
for k in [5,10,20,50,100]:
    ema=pd.Series(p).ewm(span=k,adjust=False).mean().values; X[f'ema_dist_{k}']=(p-ema)/atr
# RSI14 causal
s=pd.Series(p); delta=s.diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
avg_gain=gain.ewm(alpha=1/14,adjust=False).mean(); avg_loss=loss.ewm(alpha=1/14,adjust=False).mean(); rs=avg_gain/(avg_loss+1e-12); X['rsi14']=(100-100/(1+rs)-50)/50
# MACD hist normalized
ema12=s.ewm(span=12,adjust=False).mean(); ema26=s.ewm(span=26,adjust=False).mean(); macd=ema12-ema26; sig=macd.ewm(span=9,adjust=False).mean(); X['macd_hist_atr']=((macd-sig)/pd.Series(atr)).values
# Bollinger 20
m=s.rolling(20).mean(); sd=s.rolling(20).std(ddof=0); X['bb_pct']=((s-m)/(2*sd+1e-12)).values; X['bb_width_atr']=(4*sd/pd.Series(atr)).values
# ADX14
up=pd.Series(h).diff(); dn=-pd.Series(l).diff(); plus=np.where((up>dn)&(up>0),up,0); minus=np.where((dn>up)&(dn>0),dn,0)
tr_s=pd.Series(tr); atr_s=pd.Series(atr); pdi=100*pd.Series(plus).ewm(alpha=1/14,adjust=False).mean()/(atr_s+1e-12); mdi=100*pd.Series(minus).ewm(alpha=1/14,adjust=False).mean()/(atr_s+1e-12); dx=100*(pdi-mdi).abs()/(pdi+mdi+1e-12); adx=dx.ewm(alpha=1/14,adjust=False).mean(); X['adx_signed']=(adx*np.sign(pdi-mdi)/100).values
# Spread features
spread=((df.AskClose-df.BidClose).values); X['spread_atr']=spread/atr; X['spread_rel_price']=spread/p; X['log_tick_count']=np.log1p(df.tick_count.values)
# Cyclical HistData time-of-day (timestamp label is source clock; no DST adjustment)
hour=df.datetime.dt.hour.values+df.datetime.dt.minute.values/60
X['hour_sin']=np.sin(2*np.pi*hour/24); X['hour_cos']=np.cos(2*np.pi*hour/24); dow=df.datetime.dt.dayofweek.values; X['dow_sin']=np.sin(2*np.pi*dow/5); X['dow_cos']=np.cos(2*np.pi*dow/5)
feat=pd.DataFrame(X)
# Explicit 3-class future directional label.
entry_ask=df.AskOpen.values.astype(float); entry_bid=df.BidOpen.values.astype(float)
# +1 if 12-bar forward midpoint close exceeds next-bar AskOpen by +0.5 ATR14;
# -1 if it is below next-bar BidOpen by -0.5 ATR14; otherwise 0.
y=np.full(len(df),-99,dtype=np.int8)
for i in range(len(df)-12):
    a=atr[i]
    if not np.isfinite(a) or a<=0: continue
    fut=p[i+12]; le=entry_ask[i+1]; se=entry_bid[i+1]
    up=fut-le; dn=fut-se
    if up >= 0.5*a and dn <= -0.5*a:
        y[i]=0  # conservative ambiguity when both directional thresholds are crossed
    elif up >= 0.5*a:
        y[i]=1
    elif dn <= -0.5*a:
        y[i]=-1
    else:
        y[i]=0
# valid rows only; final 12 cannot be labeled
valid=np.isfinite(feat).all(axis=1) & (y!=-99)
feat=feat.loc[valid].reset_index(drop=True); y=y[valid]
dt=df.datetime.loc[valid].reset_index(drop=True)
# chronological 70/15/15
n=len(feat); a=int(n*.70); b=int(n*.85)
Xtr,Xv,Xte=feat.iloc[:a],feat.iloc[a:b],feat.iloc[b:]
ytr,yv,yte=y[:a],y[a:b],y[b:]
# train-only scaler
scaler=StandardScaler(); Xtrs=scaler.fit_transform(Xtr); Xvs=scaler.transform(Xv); Xtes=scaler.transform(Xte)
np.save(OUT/'X_train.npy',Xtrs); np.save(OUT/'X_validation.npy',Xvs); np.save(OUT/'X_final_test.npy',Xtes); np.save(OUT/'y_train.npy',ytr); np.save(OUT/'y_validation.npy',yv); np.save(OUT/'y_final_test.npy',yte)
features=list(feat.columns); (OUT/'feature_columns.json').write_text(json.dumps(features,indent=2))
# model class
class MLP(nn.Module):
    def __init__(self,d):
        super().__init__(); self.net=nn.Sequential(nn.Linear(d,96),nn.ReLU(),nn.BatchNorm1d(96),nn.Dropout(.15),nn.Linear(96,48),nn.ReLU(),nn.Dropout(.10),nn.Linear(48,3))
    def forward(self,x): return self.net(x)
classes=np.array([-1,0,1]); mapc={-1:0,0:1,1:2}; yt=np.array([mapc[v] for v in ytr]); yval=np.array([mapc[v] for v in yv]); ytest=np.array([mapc[v] for v in yte])
# class weights train only
counts=np.bincount(yt,minlength=3); weights=counts.sum()/(3*np.maximum(counts,1)); weights=torch.tensor(weights,dtype=torch.float32)
models=[]; val_probs=[]; test_probs=[]; train_probs=[]
for seed in [4301,4302,4303]:
    torch.manual_seed(seed); model=MLP(Xtrs.shape[1]); opt=torch.optim.AdamW(model.parameters(),lr=2e-3,weight_decay=1e-4); lossfn=nn.CrossEntropyLoss(weight=weights)
    tx=torch.tensor(Xtrs,dtype=torch.float32); ty=torch.tensor(yt); vx=torch.tensor(Xvs,dtype=torch.float32); vy=torch.tensor(yval)
    best=1e9; best_state=None; patience=0
    for epoch in range(250):
        model.train(); opt.zero_grad(); loss=lossfn(model(tx),ty); loss.backward(); opt.step()
        model.eval();
        with torch.no_grad(): vl=lossfn(model(vx),vy).item()
        if vl<best-1e-5: best=vl; best_state={k:v.detach().clone() for k,v in model.state_dict().items()}; patience=0
        else: patience+=1
        if patience>=25: break
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad():
        train_probs.append(torch.softmax(model(torch.tensor(Xtrs,dtype=torch.float32)),1).numpy()); val_probs.append(torch.softmax(model(vx),1).numpy()); test_probs.append(torch.softmax(model(torch.tensor(Xtes,dtype=torch.float32)),1).numpy())
    models.append(model)
vp=np.mean(val_probs,axis=0); tep=np.mean(test_probs,axis=0); trp=np.mean(train_probs,axis=0)
# Logistic baseline for context
lr=LogisticRegression(max_iter=1000,multi_class='multinomial',C=.5,random_state=SEED); lr.fit(Xtrs,yt); lrv=lr.predict_proba(Xvs); lrt=lr.predict_proba(Xtes)
# Metrics

def metrics(probs, yy):
 pred=classes[np.argmax(probs,1)]; true=classes[yy]
 return {'accuracy':float(accuracy_score(true,pred)),'balanced_accuracy':float(balanced_accuracy_score(true,pred)),'macro_precision':float(precision_score(true,pred,labels=classes,average='macro',zero_division=0)),'macro_recall':float(recall_score(true,pred,labels=classes,average='macro',zero_division=0)),'log_loss':float(log_loss(yy,probs,labels=[0,1,2])),'roc_auc_ovr_macro':float(roc_auc_score(yy,probs,multi_class='ovr',average='macro')),'n':int(len(yy)),'class_counts':{str(int(c)):int((true==c).sum()) for c in classes}}
report={'dataset':{'rows_m5':int(len(df)),'labeled_rows':int(n),'features':len(features),'start':str(df.datetime.min()),'end':str(df.datetime.max()),'duplicates':int(df.datetime.duplicated().sum())},'split':{'train':a,'validation':b-a,'final_test':n-b},'mlp_ensemble':{'train':metrics(trp,yt),'validation':metrics(vp,yval),'final_test':metrics(tep,ytest)},'logistic_baseline':{'validation':metrics(lrv,yval),'final_test':metrics(lrt,ytest)}}
# Validation threshold search: directional confidence only, signal when P(long/short) >= threshold and exceeds opposite; neutral otherwise. Choose threshold using validation maximizing precision while requiring >=100 resolved signals and positive PF.
def trade_stats(probs, yy, segment_df):
    # predicted direction and confidence
    pshort, pneu, plong=probs[:,0],probs[:,1],probs[:,2]; side=np.where(plong>=pshort,1,-1); conf=np.maximum(plong,pshort)
    rows=[]
    for thr in np.arange(.34,.901,.01):
        sel=conf>=thr
        inds=np.where(sel)[0]
        if len(inds)==0: continue
        actual=classes[np.argmax(probs[inds],1)]
        # outcome using actual future label yy (already execution-aware barrier label); predicted side wins if label matches, loses if opposite, neutral otherwise.
        labels=yy[inds]
        ps=side[inds]; wins=(labels==ps); losses=(labels==-ps); resolved=wins|losses
        # cost 0.085R applied to every resolved trade
        r=np.where(wins,1-.085,np.where(losses,-1-.085,0.0)); r=r[resolved]
        if len(r)==0: continue
        gp=r[r>0].sum(); gl=-r[r<0].sum(); pf=gp/gl if gl>0 else np.inf
        rows.append({'threshold':round(float(thr),2),'signals':int(len(inds)),'resolved':int(len(r)),'wins':int(wins[resolved].sum()),'losses':int(losses[resolved].sum()),'precision':float(wins[resolved].mean()),'pf':float(pf),'total_R':float(r.sum()),'max_DD_R':float((-pd.Series(r).cumsum().cummax()+pd.Series(r).cumsum()).max()*-1 if len(r) else 0)})
    return pd.DataFrame(rows)
val_stats=trade_stats(vp,yv,Xv); val_stats.to_csv(OUT/'validation_threshold_sweep.csv',index=False)
# choose validation threshold: max PF among >=100 resolved and precision >=0.55; if none, max precision >=100. Test untouched.
q=val_stats[val_stats.resolved>=100].copy(); q2=q[q.precision>=.55].copy();
if len(q2): bestrow=q2.sort_values(['pf','precision','resolved'],ascending=False).iloc[0]
elif len(q): bestrow=q.sort_values(['precision','pf','resolved'],ascending=False).iloc[0]
else: bestrow=val_stats.iloc[0]
thr=float(bestrow.threshold)

def eval_threshold(probs, yy, thr):
 pshort,pneu,plong=probs[:,0],probs[:,1],probs[:,2]; side=np.where(plong>=pshort,1,-1); conf=np.maximum(plong,pshort); sel=conf>=thr; inds=np.where(sel)[0]; labels=yy[inds]; ps=side[inds]; wins=(labels==ps); losses=(labels==-ps); resolved=wins|losses; r=np.where(wins,1-.085,np.where(losses,-1-.085,0))[resolved];
 eq=np.cumsum(r); peak=np.maximum.accumulate(eq); dd=peak-eq
 return {'threshold':thr,'signals':int(len(inds)),'resolved':int(len(r)),'wins':int(wins[resolved].sum()),'losses':int(losses[resolved].sum()),'precision':float(wins[resolved].mean()) if len(r) else 0,'pf':float(r[r>0].sum()/-r[r<0].sum()) if np.any(r<0) else float('inf'),'total_R':float(r.sum()),'max_DD_R':float(dd.max()) if len(dd) else 0,'avg_R':float(r.mean()) if len(r) else 0}
report['threshold_selection']={'selection_rule':'Validation only: >=100 resolved, prefer precision>=55%, then highest PF; otherwise highest precision. Final Test untouched.','selected':bestrow.to_dict(),'validation':eval_threshold(vp,yv,thr),'final_test':eval_threshold(tep,yte,thr)}
# Save model weights + scaler
for i,m in enumerate(models,1): torch.save(m.state_dict(),OUT/f'mlp_seed_{i}.pt')
import pickle
with open(OUT/'scaler.pkl','wb') as f: pickle.dump(scaler,f)
(OUT/'V43_NEURAL_RESEARCH_REPORT.json').write_text(json.dumps(report,indent=2,default=lambda x:float(x) if isinstance(x,np.floating) else int(x) if isinstance(x,np.integer) else x))
(OUT/'V43_NEURAL_RESEARCH_SUMMARY.md').write_text('# AEGIS V43 Neural Intelligence Research\n\n'+json.dumps(report,indent=2,default=str))
print(json.dumps(report,indent=2,default=str))
