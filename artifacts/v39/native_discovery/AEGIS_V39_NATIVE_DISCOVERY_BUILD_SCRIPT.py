import pandas as pd, numpy as np, zipfile, io, os, hashlib
from numba import njit

def tick_zip_to_m5(path):
    outs=[]
    with zipfile.ZipFile(path) as outer:
      for n in outer.namelist():
        if not n.lower().endswith('.zip'): continue
        with zipfile.ZipFile(io.BytesIO(outer.read(n))) as z:
          cn=next((x for x in z.namelist() if x.lower().endswith('.csv')),None)
          if not cn: continue
          raw=z.read(cn)
          d=pd.read_csv(io.BytesIO(raw),header=None,usecols=[0,1,2,3]); d.columns=['dt','bid','ask','vol']
          d['datetime']=pd.to_datetime(d.dt.astype(str),format='%Y%m%d %H%M%S%f',errors='coerce')
          if d.datetime.isna().all(): d['datetime']=pd.to_datetime(d.dt.astype(str),format='%Y%m%d%H%M%S%f',errors='coerce')
          d['bid']=pd.to_numeric(d.bid,errors='coerce'); d['ask']=pd.to_numeric(d.ask,errors='coerce'); d['vol']=pd.to_numeric(d.vol,errors='coerce')
          d=d.dropna(subset=['datetime','bid','ask']).sort_values('datetime').drop_duplicates('datetime')
          x=d.set_index('datetime')
          o=pd.DataFrame({'datetime':x.index.floor('5min')})
          g=x.groupby(x.index.floor('5min'))
          out=pd.DataFrame({'datetime':g.bid.first().index,'BidOpen':g.bid.first().values,'BidHigh':g.bid.max().values,'BidLow':g.bid.min().values,'BidClose':g.bid.last().values,'AskOpen':g.ask.first().values,'AskHigh':g.ask.max().values,'AskLow':g.ask.min().values,'AskClose':g.ask.last().values,'Volume':g.vol.sum().values})
          outs.append(out)
    return pd.concat(outs,ignore_index=True).drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)

def m1_2024_to_m5(path):
    outs=[]
    with zipfile.ZipFile(path) as outer:
      for n in outer.namelist():
        if '2024' not in n or not n.lower().endswith('.zip'): continue
        with zipfile.ZipFile(io.BytesIO(outer.read(n))) as z:
          cn=next(x for x in z.namelist() if x.lower().endswith('.csv'))
          d=pd.read_csv(io.BytesIO(z.read(cn)),header=None,usecols=[1,2,3,4,5,6]); d.columns=['dt','Open','High','Low','Close','Volume']
          d['datetime']=pd.to_datetime(d.dt.astype(str),format='%Y%m%d%H%M',errors='coerce')
          for c in ['Open','High','Low','Close','Volume']: d[c]=pd.to_numeric(d[c],errors='coerce')
          d=d.dropna(subset=['datetime','Open','High','Low','Close']).sort_values('datetime').drop_duplicates('datetime').set_index('datetime')
          g=d.resample('5min'); out=g.agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna().reset_index(); out.columns=['datetime','BidOpen','BidHigh','BidLow','BidClose','Volume']; outs.append(out)
    return pd.concat(outs,ignore_index=True).drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)

def prep(d):
 d=d.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True); c=d.BidClose.values; h=d.BidHigh.values; l=d.BidLow.values
 prev=np.r_[np.nan,c[:-1]]; tr=np.maximum.reduce([h-l,np.abs(h-prev),np.abs(l-prev)]); atr=pd.Series(tr).ewm(alpha=1/14,adjust=False).mean().values; ra=(h-l)/atr
 def sh(a,n): return pd.Series(a).shift(1).rolling(n).mean().values
 f={}
 for L in [6,12,24,48]: f[f'comp{L}']=sh(ra,L)
 f['ra']=ra; f['mom6']=(c-np.r_[np.full(6,np.nan),c[:-6]])/atr; f['mom12']=(c-np.r_[np.full(12,np.nan),c[:-12]])/atr; f['disp24']=(c-np.r_[np.full(24,np.nan),c[:-24]])/atr; f['disp48']=(c-np.r_[np.full(48,np.nan),c[:-48]])/atr
 f['breakdown']=c<pd.Series(l).shift(1).rolling(12).min().values; f['breakup']=c>pd.Series(h).shift(1).rolling(12).max().values
 f['exlow']=(np.r_[np.full(12,np.nan),c[:-12]]-np.r_[np.nan,c[:-1]])/(pd.Series(h).shift(1).rolling(12).max().values-pd.Series(l).shift(1).rolling(12).min().values)
 f['exhigh']=(np.r_[np.nan,c[:-1]]-np.r_[np.full(12,np.nan),c[:-12]])/(pd.Series(h).shift(1).rolling(12).max().values-pd.Series(l).shift(1).rolling(12).min().values)
 return d, f, atr

@njit
def simulate(mask,atr,bc,bh,bl,bo,ao,short):
 n=len(bc); out=np.empty(n); k=0; last=-1000000; i=50
 while i<n-1:
  if not mask[i] or not np.isfinite(atr[i]) or i-last<12: i+=1; continue
  entry=ao[i+1] if short else bo[i+1]; risk=1.5*atr[i]; stop=entry+risk if short else entry-risk; be=False; j=i+1; end=min(n,i+73)
  while j<end:
   if short and bh[j]>=stop: out[k]=(entry-stop)/risk; k+=1; break
   if (not short) and bl[j]<=stop: out[k]=(stop-entry)/risk; k+=1; break
   rr=(entry-bc[j])/risk if short else (bc[j]-entry)/risk
   if rr>=1 and not be: stop=entry; be=True
   if be:
    new=bc[j]+0.75*atr[j] if short else bc[j]-0.75*atr[j]; stop=min(stop,new) if short else max(stop,new)
   j+=1
  else:
   j=end-1; out[k]=(bc[j]-entry)/risk; k+=1
  last=i; i=j+1
 return out[:k]

def score(R):
 R=R-0.085
 pos=R[R>0].sum(); neg=-R[R<0].sum(); return len(R), pos/neg if neg>0 else 0, R.mean() if len(R) else np.nan, R.sum()

def discovery(d,pair,ask=True):
 d,f,atr=prep(d); N=len(d); train=int(.7*N); inner=int(.7*train)
 c=[]
 for L in [6,12,24,48]:
  for E in [1.2,1.5]:
   for dr in [0,1]:
    base=(f[f'comp{L}']<1)&(f['ra']>=E)
    for st in ['momentum','multiscale','break','exhaust']:
     if st=='momentum': q=f['mom6']<0 if dr==0 else f['mom6']>0
     elif st=='multiscale': q=(f['disp24']<0)&(f['disp48']<0) if dr==0 else (f['disp24']>0)&(f['disp48']>0)
     elif st=='break': q=f['breakdown'] if dr==0 else f['breakup']
     else: q=f['exlow']<0.5 if dr==0 else f['exhigh']<0.5
     c.append((L,E,'short' if dr==0 else 'long',st,(base&q).fillna(False).values))
 def ev(m,s,e,dr):
  sub=d.iloc[s:e]; return score(simulate(m[s:e],atr[s:e],sub.BidClose.values,sub.BidHigh.values,sub.BidLow.values,sub.BidOpen.values,sub.AskOpen.values if 'AskOpen' in sub else sub.BidOpen.values,dr=='short'))
 scores=[]
 for k,x in enumerate(c): scores.append((k,*ev(x[4],0,inner,x[2])))
 scores=sorted(scores,key=lambda z:(-z[2],-z[1]))[:8]
 outer=[]
 for k,*_ in scores:
  x=c[k]; outer.append((k,*ev(x[4],inner,train,x[2])))
 outer=sorted(outer,key=lambda z:(-z[2],-z[1])); best=c[outer[0][0]]
 rows=[]
 for name,s,e in [('Train',0,train),('Validation',train,int(.85*N)),('Final Test',int(.85*N),N)]: rows.append((pair,*best[:4],name,*ev(best[4],s,e,best[2])))
 # six blocks across full series
 six=[]
 for b in range(6):
  s=int(b*N/6); e=int((b+1)*N/6); six.append((b+1,*ev(best[4],s,e,best[2])))
 return pd.DataFrame(rows,columns=['pair','L','E','direction','state','period','trades','PF','avg_R','total_R']), pd.DataFrame(scores,columns=['id','trades','PF','avg_R','total_R']), pd.DataFrame(outer,columns=['id','trades','PF','avg_R','total_R']), six, best

# EURJPY 12m new + 12m old
euj=tick_zip_to_m5('/mnt/data/EURJPY.zip'); old=pd.read_csv('/mnt/data/v39_targets/EURJPY_M5_BID_ASK.csv'); old.datetime=pd.to_datetime(old.datetime,errors='coerce'); euj=pd.concat([old,euj],ignore_index=True).drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
print('EURJPY',len(euj),euj.datetime.min(),euj.datetime.max()); r,s,o,six,b=discovery(euj,'EURJPY'); print(r.to_string(index=False)); print('six',six); print('best',b[:4]); r.to_csv('/mnt/data/EURJPY_NATIVE_DISCOVERY_RESULTS.csv',index=False); s.to_csv('/mnt/data/EURJPY_NATIVE_DISCOVERY_SCREEN.csv',index=False); o.to_csv('/mnt/data/EURJPY_NATIVE_DISCOVERY_OUTER.csv',index=False); pd.DataFrame(six,columns=['block','trades','PF','avg_R','total_R']).to_csv('/mnt/data/EURJPY_NATIVE_DISCOVERY_SIX_BLOCK.csv',index=False)
# GBPJPY 12m new Bid-only 2024 + 12m old BidAsk
gbp=m1_2024_to_m5('/mnt/data/GBPJPY.zip'); old=pd.read_csv('/mnt/data/v39_targets/GBPJPY_M5_BID_ASK.csv'); old.datetime=pd.to_datetime(old.datetime,errors='coerce'); gbp=pd.concat([old,gbp],ignore_index=True).drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
print('GBPJPY',len(gbp),gbp.datetime.min(),gbp.datetime.max()); r,s,o,six,b=discovery(gbp,'GBPJPY'); print(r.to_string(index=False)); print('six',six); print('best',b[:4]); r.to_csv('/mnt/data/GBPJPY_NATIVE_DISCOVERY_RESULTS.csv',index=False); s.to_csv('/mnt/data/GBPJPY_NATIVE_DISCOVERY_SCREEN.csv',index=False); o.to_csv('/mnt/data/GBPJPY_NATIVE_DISCOVERY_OUTER.csv',index=False); pd.DataFrame(six,columns=['block','trades','PF','avg_R','total_R']).to_csv('/mnt/data/GBPJPY_NATIVE_DISCOVERY_SIX_BLOCK.csv',index=False)
