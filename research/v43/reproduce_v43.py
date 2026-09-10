import json,pickle,hashlib
from pathlib import Path
import numpy as np
from sklearn.metrics import accuracy_score
O=Path(__file__).parent
Xv=np.load(O/'X_validation.npy'); Xt=np.load(O/'X_final_test.npy'); yv=np.load(O/'y_validation.npy'); yt=np.load(O/'y_final_test.npy')
models=pickle.load(open(O/'mlp_ensemble_models.pkl','rb'))
pv=np.mean([m.predict_proba(Xv) for m in models],axis=0); pt=np.mean([m.predict_proba(Xt) for m in models],axis=0)
# deterministic digest of probabilities for independent replay check
for name,p in [('validation',pv),('final_test',pt)]:
 print(name,'shape',p.shape,'sha256',hashlib.sha256(p.astype('float64').tobytes()).hexdigest())
print('models',len(models),'validation_pred_match',float(accuracy_score(yv,pv.argmax(1))))
print('final_test_pred_match',float(accuracy_score(yt,pt.argmax(1))))
