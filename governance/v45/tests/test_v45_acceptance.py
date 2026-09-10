import csv, json, pickle, hashlib, zipfile
from pathlib import Path

ROOT = Path('/mnt/data/v45_inputs')
V40 = ROOT/'v40/AEGIS_V40_WORK'
V41 = ROOT/'v41/AEGIS_V41_WORK'
V42 = ROOT/'v42/v42_server_base'
V43 = ROOT/'v43/v43_checkpoint_small'
V44 = ROOT/'v44'


def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def test_checkpoint_integrity_and_known_hashes():
    expected={
      '/mnt/data/AEGIS_V39_SERVER_CHECKPOINT_20260909.zip': None,
      '/mnt/data/AEGIS_V40_QUALIFICATION_ROUTER_CHECKPOINT_20260909.zip':'270fcf889475477ad8194ddedd0c1f0d766958eb6b5f687d2e5c0e161f3b99e8',
      '/mnt/data/AEGIS_V41_FORWARD_VALIDATION_CHECKPOINT_20260909.zip':'e85dcb36e639ac87f825c2ab9288d1d96f0f9940c134b0943719298519666d54',
      '/mnt/data/AEGIS_V42_EXECUTION_RISK_SAFETY_CHECKPOINT_20260909.zip':None,
      '/mnt/data/AEGIS_V43_NEURAL_INTELLIGENCE_CHECKPOINT_20260910.zip':'f4d32a4f61426ee98adcff5e8cdaf9bdd5113fdaab7ad319b5684b840d31518a',
      '/mnt/data/AEGIS_V44_NEURAL_RULEBOOK_ROUTER_INTEGRATION_CHECKPOINT_20260910.zip':'5f0f68961545ce9e60cc42dc4b5753736ff54c8476fcda4ecf16fe4f13beb541',
    }
    for p,e in expected.items():
        if Path(p).exists():
            with zipfile.ZipFile(p) as z: assert z.testzip() is None
            if e: assert sha256(p)==e


def test_registry_and_forward_boundary():
    with open(V40/'artifacts/v40/registry/AEGIS_V40_RULEBOOK_REGISTRY.csv', newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==6
    assert all(r['status']=='QUALIFIED_RESEARCH_CANDIDATE' and r['production_authorized']=='false' for r in rows)
    with open(V41/'artifacts/v41/forward/AEGIS_V41_FORWARD_DATA_STATUS.csv', newline='') as f: fr=list(csv.DictReader(f))
    assert len(fr)==6 and all(r['status']=='NO_NEW_DATA' for r in fr)
    assert all(r['latest_available_observation']=='2026-08-28 16:55:00' for r in fr)


def test_v42_live_boundary_and_v44_neural_boundary():
    text=(V42/'backend/app/safety/execution_guard.py').read_text()
    assert 'production_authorized: bool = False' in text
    assert 'live_enabled: bool = False' in text
    mt5=(V42/'backend/app/services/mt5_execution_service.py').read_text()
    assert 'DEMO_ONLY = True' in mt5
    policy=(V44/'router/AEGIS_V44_UNIVERSAL_ROUTER_POLICY.md').read_text().lower()
    assert 'research_only' in policy and 'no_live_order' in policy and 'threshold retuning' in policy


def test_v43_locked_research_state():
    report=json.loads((V43/'research/V43_NEURAL_RESEARCH_REPORT.json').read_text())
    assert abs(report['threshold']['selected']['threshold']-0.6000000000000003)<1e-12
    assert abs(report['threshold']['final_test']['precision']-0.576)<1e-12
    assert report['threshold']['final_test']['pf'] < 1.60
    models=pickle.load(open(V43/'research/mlp_ensemble_models.pkl','rb'))
    assert len(models)==2 and [m.random_state for m in models]==[4301,4302]
    assert all(m.n_features_in_==50 for m in models)
