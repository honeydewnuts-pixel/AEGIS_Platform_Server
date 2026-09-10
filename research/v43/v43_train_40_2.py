import numpy as np,time,pickle,json
from pathlib import Path
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score,balanced_accuracy_score,precision_score,log_loss
import pandas as pd
O=Path('/mnt/data/AEGIS_V43_WORK'); Xtr=np.load(O/'X_train.npy'); Xv=np.load(O/'X_validation.npy'); Xt=np.load(O/'X_final_test.npy'); ytr0=np.load(O/'y_train.npy'); yv0=np.load(O/'y_validation.npy'); yt0=np.load(O/'y_final_test.npy'); mp={-1:0,0:1,1:2}; ytr=np.array([mp[x] for x in ytr0]); yv=np.array([mp[x] for x in yv0]); yt=np.array([mp[x] for x in yt0]);
psv=[]; pst=[]; ptr=[]; models=[]
for seed in [4301,4302]:
 t=time.time(); m=MLPClassifier(hidden_layer_sizes=(64,32),max_iter=40,batch_size=4096,learning_rate_init=.001,alpha=1e-4,random_state=seed,early_stopping=False,solver='adam'); m.fit(Xtr,ytr); print('seed',seed,'iter',m.n_iter_,'sec',time.time()-t,flush=True); ptr.append(m.predict_proba(Xtr)); psv.append(m.predict_proba(Xv)); pst.append(m.predict_proba(Xt)); models.append(m)
pv=np.mean(psv,0); pt=np.mean(pst,0); ptr=np.mean(ptr,0)
def met(p,y):
 q=p.argmax(1); return {'accuracy':accuracy_score(y,q),'balanced_accuracy':balanced_accuracy_score(y,q),'macro_precision':precision_score(y,q,average='macro',zero_division=0),'logloss':log_loss(y,p,labels=[0,1,2])}
print('VAL',met(pv,yv)); print('TEST',met(pt,yt),flush=True)
# threshold sweep only
rows=[]
for thr in np.arange(.34,.91,.01):
 side=np.where(pv[:,2]>=pv[:,0],1,-1); conf=np.maximum(pv[:,2],pv[:,0]); sel=conf>=thr; labs=yv[sel]; s=side[sel]; wins=labs==np.where(s==1,2,0); losses=labs==np.where(s==1,0,2); res=wins|losses
 if res.sum()<100: continue
 r=np.where(wins,.915,-1.085)[res]; rows.append((thr,res.sum(),wins[res].mean(),r[r>0].sum()/-r[r<0].sum()))
s=pd.DataFrame(rows,columns=['threshold','resolved','precision','pf']); s.to_csv(O/'validation_threshold_sweep.csv',index=False); print(s.sort_values(['precision','pf'],ascending=False).head(10).to_string(index=False))
# best by validation precision then PF with >=100
br=s.sort_values(['precision','pf'],ascending=False).iloc[0]; thr=float(br.threshold)
def ev(p,y):
 side=np.where(p[:,2]>=p[:,0],1,-1); conf=np.maximum(p[:,2],p[:,0]); sel=conf>=thr; labs=y[sel]; ss=side[sel]; wins=labs==np.where(ss==1,2,0); losses=labs==np.where(ss==1,0,2); res=wins|losses; r=np.where(wins,.915,-1.085)[res]; eq=r.cumsum(); return {'threshold':thr,'signals':int(sel.sum()),'resolved':int(res.sum()),'precision':float(wins[res].mean()) if res.sum() else 0,'pf':float(r[r>0].sum()/-r[r<0].sum()) if np.any(r<0) else 999,'total_R':float(r.sum()),'max_DD_R':float((np.maximum.accumulate(eq)-eq).max()) if len(r) else 0}
rep={'validation':met(pv,yv),'final_test':met(pt,yt),'threshold':{'selected':br.to_dict(),'validation':ev(pv,yv),'final_test':ev(pt,yt)}}
(O/'V43_NEURAL_RESEARCH_REPORT.json').write_text(json.dumps(rep,indent=2,default=float)); (O/'V43_NEURAL_RESEARCH_SUMMARY.md').write_text('# V43 Neural Research\n\n'+json.dumps(rep,indent=2,default=float)); pickle.dump(models,open(O/'mlp_ensemble_models.pkl','wb'))
