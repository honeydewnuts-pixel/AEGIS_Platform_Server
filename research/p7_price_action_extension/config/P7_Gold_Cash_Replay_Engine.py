"""P7 gold in-sample cash replay. Frozen P7, no parameter optimization.
Model was fit on these data. Cash results are historical diagnostic only.
"""
import pandas as pd
import numpy as np
FEATURES=['body','upper_wick','lower_wick','close_location','relative_range','move3','move6','move12','overlap','inside','outside']

def load(path):
 d=pd.read_csv(path);d.columns=[str(x).strip().strip('<>').lower() for x in d.columns]
 if 'time' not in d:
  for k in ['timestamp','datetime']:
   if k in d:d=d.rename(columns={k:'time'});break
 d.time=pd.to_datetime(d.time,utc=True,errors='raise')
 for k in ['open','high','low','close']:d[k]=pd.to_numeric(d[k],errors='raise').astype(float)
 if d.time.isna().any() or not d.time.is_unique or not d.time.is_monotonic_increasing:raise ValueError('Invalid time')
 if not np.isfinite(d[['open','high','low','close']]).all().all():raise ValueError('Nonfinite OHLC')
 if not ((d.high>=d[['open','close','low']].max(axis=1))&(d.low<=d[['open','close','high']].min(axis=1))).all():raise ValueError('Invalid OHLC')
 return d.reset_index(drop=True)

def hourly(d):
 z=d.copy();z['bucket']=z.time.dt.floor('h');g=z.groupby('bucket',sort=True)
 h=g.agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),first_observed=('time','first'),last_observed=('time','last'),count=('time','size'));h['decision_time']=h.index+pd.Timedelta(hours=1)
 regular=g.time.apply(lambda x:len(x)==12 and np.array_equal(x.astype('int64').to_numpy()-x.astype('int64').iloc[0],np.arange(12)*300000000000))
 h['complete']=(h['count']==12)&(h.first_observed==h.index)&(h.last_observed==h.index+pd.Timedelta(minutes=55))&regular
 return h.reset_index()

def features(d):
 o,h,l,c=[d[k] for k in ['open','high','low','close']];rg=(h-l).replace(0,np.nan);sc=(h-l).rolling(20).median().replace(0,np.nan);x=pd.DataFrame(index=d.index)
 x['body']=(c-o)/rg;x['upper_wick']=(h-pd.concat([o,c],axis=1).max(axis=1))/rg;x['lower_wick']=(pd.concat([o,c],axis=1).min(axis=1)-l)/rg;x['close_location']=(c-l)/rg;x['relative_range']=rg/sc
 for p in [3,6,12]:x['move'+str(p)]=(c-c.shift(p))/sc
 it=(pd.concat([h,h.shift()],axis=1).min(axis=1)-pd.concat([l,l.shift()],axis=1).max(axis=1)).clip(lower=0);un=pd.concat([h,h.shift()],axis=1).max(axis=1)-pd.concat([l,l.shift()],axis=1).min(axis=1)
 x['overlap']=it/un.replace(0,np.nan);x['inside']=((h<=h.shift())&(l>=l.shift())).astype(float);x['outside']=((h>h.shift())&(l<l.shift())).astype(float)
 x.loc[~(d.complete.astype(int).rolling(20).min()==1),:]=np.nan
 return x[FEATURES],sc

def align(h,other):
 x,sc=features(h);ox,_=features(other);r=ox.add_prefix('other_');r['external_end']=other.decision_time;r['available']=other.decision_time+pd.Timedelta(hours=1)
 j=pd.merge_asof(h[['decision_time']].reset_index().rename(columns={'index':'own_index'}),r.sort_values('available'),left_on='decision_time',right_on='available',direction='backward',tolerance=pd.Timedelta(hours=1)).set_index('own_index').reindex(h.index)
 return x,pd.concat([x,j[['other_'+k for k in FEATURES]]],axis=1),sc,j[['external_end','available']]

def outcomes(h,sc):
 n=len(h);cnt=n-5;en=np.arange(cnt)+1;o,hi,lo=[h[k].to_numpy() for k in ['open','high','low']];days=h.first_observed.astype('int64').to_numpy()//86400000000000;risk=2*sc.to_numpy()[:cnt];ep=o[en];ys={}
 for sd in [1,-1]:
  sl=ep-sd*risk;tp=ep+sd*risk;alive=np.ones(cnt,bool);px=np.full(cnt,np.nan);ex=np.full(cnt,-1,int)
  for k in range(4):
   i=en+k;gs=o[i]<=sl if sd==1 else o[i]>=sl;gt=o[i]>=tp if sd==1 else o[i]<=tp;hs=lo[i]<=sl if sd==1 else hi[i]>=sl;ht=hi[i]>=tp if sd==1 else lo[i]<=tp
   a=alive&gs;b=alive&~gs&gt;c=alive&~gs&~gt&hs;e=alive&~gs&~gt&~hs&ht
   for mask,p in [(a,o[i]),(b,tp),(c,sl),(e,tp)]:px[mask]=p[mask];ex[mask]=i[mask]
   alive&=~(a|b|c|e)
  i=en+4;px[alive]=o[i[alive]];ex[alive]=i[alive];fin=(days[ex]-days[en])*.1;net=(sd*(px-ep)-.42-fin)/risk
  ys[sd]=pd.DataFrame({'exit_i':ex,'net_R':net,'risk':risk}).reindex(range(n))
 return ys

def prepare(raw,fx,models):
 h=hourly(raw);other=hourly(fx);x,xc,sc,av=align(h,other);valid=np.isfinite(xc).all(axis=1).to_numpy()&(2*sc.to_numpy()>=.84);p=np.full((len(h),2),np.nan)
 for k,sd in enumerate([1,-1]):p[valid,k]=models[sd].predict(x.loc[valid])
 ts=raw.time.astype('int64').to_numpy();ht=h.bucket.astype('int64').to_numpy();side=np.zeros(len(raw),int);risk=np.full(len(raw),np.nan);exit_due=np.full(len(raw),np.iinfo(np.int64).max,dtype=np.int64);sid=np.full(len(raw),-1,int);audit=[]
 for t in np.flatnonzero(valid):
  pl,ps=p[t];sd=1 if pl>ps and pl>.05 else -1 if ps>pl and ps>.05 else 0
  if not sd:continue
  i=int(np.searchsorted(ts,h.decision_time.iloc[t].value,side='left'))
  if i>=len(raw):continue
  entrybucket=int(np.searchsorted(ht,(raw.time.iloc[i].floor('h')).value,side='left'));k=entrybucket+4
  due=int(np.searchsorted(ts,h.first_observed.iloc[k].value,side='left')) if k<len(h) else np.iinfo(np.int64).max
  side[i]=sd;risk[i]=2*sc.iloc[t];exit_due[i]=due;sid[i]=t
  audit.append(dict(signal_H1_index=int(t),decision_time=str(h.decision_time.iloc[t]),next_M5_open_time=str(raw.time.iloc[i]),side=sd,risk_distance=risk[i],pred_long_R=pl,pred_short_R=ps,external_end=str(av.external_end.iloc[t])))
 return side,risk,exit_due,sid,pd.DataFrame(audit)

def cash(raw,signals,initial,sizing,mult=1.):
 side_signal,risk_signal,due_signal,signal_idx=signals[:4];n=len(raw);o,h,l,c=[raw[k].to_numpy(float) for k in ['open','high','low','close']];ts=raw.time.astype('int64').to_numpy();days=ts//86400000000000
 fee=.21*mult;daily=.1*mult;bal=float(initial);peak=bal;dd=0.;guard=False;guard_reason='';guard_time='';sd=0;units=0;ep=stop=target=0.;entry_i=-1;due=n+1;entry_balance=0.;entry_fee=fin_trade=0.;closed=entries=rejected=0;total_fin=total_fee=0.;rows=[];equity=np.empty(n);balances=np.empty(n);ddpath=np.empty(n)
 for i in range(n):
  if units and i and days[i]>days[i-1]:
   charge=units*daily*(days[i]-days[i-1]);bal-=charge;fin_trade+=charge;total_fin+=charge
  # No re-entry on the same M5 bar as an exit; hourly signals while positioned ignored.
  if units==0 and not guard and side_signal[i]!=0:
   risk=float(risk_signal[i]);sd0=int(side_signal[i]);eq=bal
   if sizing=='risk0.25pct':want=eq*.0025/(risk+2*fee)
   else:want=eq*(1 if sizing=='notional1x' else 5)/o[i]
   u=min(10000,int(np.floor(max(0,want)+1e-12)));margin=u*o[i]/100
   if u<1 or margin+u*fee>bal:rejected+=1
   else:
    units=u;sd=sd0;ep=o[i];stop=ep-sd*risk;target=ep+sd*risk;entry_i=i;due=int(due_signal[i]);entry_balance=bal;entry_fee=units*fee;fin_trade=0.;bal-=entry_fee;total_fee+=entry_fee;entries+=1
  if units:
   px=None;why=''
   if (sd==1 and o[i]<=stop) or (sd==-1 and o[i]>=stop):px=o[i];why='gap_stop'
   elif i>=due:px=o[i];why='time_open'
   elif (sd==1 and o[i]>=target) or (sd==-1 and o[i]<=target):px=target;why='gap_target'
   else:
    hs=l[i]<=stop if sd==1 else h[i]>=stop;ht=h[i]>=target if sd==1 else l[i]<=target
    if hs:px=stop;why='both_stop_first' if ht else 'stop'
    elif ht:px=target;why='target'
   if px is not None:
    gross=sd*units*(px-ep);exit_fee=units*fee;bal+=gross-exit_fee;total_fee+=exit_fee;net=gross-entry_fee-exit_fee-fin_trade
    rows.append([entry_i,i,str(raw.time.iloc[entry_i]),str(raw.time.iloc[i]),sd,units,ep,stop,target,px,why,gross,entry_fee+exit_fee,fin_trade,net,entry_balance,bal]);closed+=1;units=0;sd=0
  eq=bal+sd*units*(c[i]-ep)-units*fee if units else bal
  peak=max(peak,eq);dd=max(dd,(peak-eq)/peak);margin=units*c[i]/100
  if not guard and (eq<=.75*peak or (units and eq<=.5*margin)):
   guard=True;guard_reason='25% completed-M5 equity drawdown' if eq<=.75*peak else '50% close-margin stopout';guard_time=str(raw.time.iloc[i]+pd.Timedelta(minutes=5))
   if units:
    px=c[i];gross=sd*units*(px-ep);exit_fee=units*fee;bal+=gross-exit_fee;total_fee+=exit_fee;net=gross-entry_fee-exit_fee-fin_trade
    rows.append([entry_i,i,str(raw.time.iloc[entry_i]),str(raw.time.iloc[i]),sd,units,ep,stop,target,px,guard_reason,gross,entry_fee+exit_fee,fin_trade,net,entry_balance,bal]);closed+=1;units=0;sd=0;eq=bal
   dd=max(dd,(peak-eq)/peak)
  equity[i]=eq;balances[i]=bal;ddpath[i]=dd
 cols=['entry_i','exit_i','entry_bucket_M5_time','exit_bucket_M5_time','side','units_oz','entry','stop','target','exit','exit_reason','gross_USD','cost_USD','financing_USD','net_USD','entry_balance','exit_balance']
 trades=pd.DataFrame(rows,columns=cols);gp=trades.net_USD[trades.net_USD>0].sum();gl=-trades.net_USD[trades.net_USD<0].sum()
 summary=dict(initial_USD=initial,sizing=sizing,cost_scenario='base' if mult==1 else 'double',ending_balance_USD=bal,ending_equity_USD=equity[-1],return_pct=100*(equity[-1]/initial-1),closed_trades=closed,entries=entries,rejected_entries=rejected,net_PF=float(gp/gl) if gl else np.nan,max_close_DD_pct=100*dd,shutdown=guard,shutdown_reason=guard_reason,shutdown_time=guard_time,open_units=sd*units,paid_costs_USD=total_fee,paid_finance_USD=total_fin)
 horizons={'1day':pd.Timedelta(days=1),'1week':pd.Timedelta(weeks=1),'1month':pd.DateOffset(months=1),'6months':pd.DateOffset(months=6),'1year':pd.DateOffset(years=1),'5years':pd.DateOffset(years=5)};out=[];close_times=raw.time+pd.Timedelta(minutes=5)
 for name,delta in horizons.items():
  k=min(n-1,int(close_times.searchsorted(raw.time.iloc[0]+delta,side='right'))-1)
  out.append(dict(initial_USD=initial,sizing=sizing,cost_scenario=summary['cost_scenario'],horizon=name,equity_USD=equity[k],balance_USD=balances[k],return_pct=100*(equity[k]/initial-1),max_close_DD_pct=100*ddpath[k]))
 return summary,pd.DataFrame(out),trades,equity

class FrozenTree:
 def __init__(self,tree):self.tree=tree
 def predict(self,data):
  vals=np.asarray(data,dtype=np.float32);out=[];t=self.tree
  for row in vals:
   node=0
   while t['left'][node]!=t['right'][node]:node=t['left'][node] if row[t['feature'][node]]<=t['threshold'][node] else t['right'][node]
   out.append(t['value'][node])
  return np.asarray(out)

if __name__=='__main__':
 import argparse,json,hashlib
 p=argparse.ArgumentParser();p.add_argument('gold_csv');p.add_argument('fx_csv');p.add_argument('--snapshot',default='P7_Unchanged_Frozen_Model.json');p.add_argument('--prefix',default='P7_cash')
 a=p.parse_args();raw_model=open(a.snapshot,'rb').read()
 if hashlib.sha256(raw_model).hexdigest()!='18380c1ee7b1f6f0a5febb55c5e88e872abdd3c45f92edbec671a21d06cbe8fa':raise ValueError('Wrong frozen P7 model')
 s=json.loads(raw_model);m={1:FrozenTree(s['long_tree']),-1:FrozenTree(s['short_tree'])};gold=load(a.gold_csv);fx=load(a.fx_csv);signals=prepare(gold,fx,m);signals[4].to_csv(a.prefix+'_signals.csv',index=False)
 summaries=[];horizons=[];trades=[]
 for initial in [50,100,250,500,1000,5000,10000]:
  for sizing in ['notional1x','notional5x','risk0.25pct']:
   for mult in [1.,2.]:
    row,h,t,_=cash(gold,signals,initial,sizing,mult);summaries.append(row);horizons.append(h)
    if len(t):
     t=t.assign(initial_USD=initial,sizing=sizing,cost_scenario='base' if mult==1 else 'double');trades.append(t)
 pd.DataFrame(summaries).to_csv(a.prefix+'_scenarios.csv',index=False);pd.concat(horizons,ignore_index=True).to_csv(a.prefix+'_horizons.csv',index=False)
 if trades:pd.concat(trades,ignore_index=True).to_csv(a.prefix+'_all_trades.csv',index=False)
