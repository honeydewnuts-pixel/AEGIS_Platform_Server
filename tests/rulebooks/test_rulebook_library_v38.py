import pandas as pd
import pytest
from app.rulebooks import founding_registry
from app.services.replay import ReferenceHistoricalReplay

V31="AEGIS-RB-V31-GBPUSD-5M"; V35="AEGIS-RB-V35-GBPUSD-5M"

def test_founding_rulebooks_registered_and_immutable():
    r=founding_registry(); assert {x.rulebook_id for x in r.all()} == {V31,V35}
    with pytest.raises(ValueError): r.register(r.get(V31))

def test_lookup_fail_closed():
    r=founding_registry(); assert r.lookup("EURUSD","M5",qualified_only=True)==[]

def test_reference_replay_v31_v35_exact_counts_and_metrics():
    rr=ReferenceHistoricalReplay()
    a=rr.replay(V31); b=rr.replay(V35)
    assert len(a)==2600 and len(b)==2060
    assert a.event_i.tolist()[:5]==[28,80,136,175,223]
    assert b.event_i.tolist()[:5]==[55,71,140,155,175]
    def pf(x):
        pos=x[x.R>0].R.sum(); neg=-x[x.R<0].R.sum(); return pos/neg
    assert abs(pf(a)-1.4803549857)<1e-6
    assert abs(pf(b)-1.7018829896)<1e-6

def test_unknown_replay_fails_closed():
    rr=ReferenceHistoricalReplay()
    with pytest.raises(ValueError, match="NO_QUALIFIED_RULEBOOK"):
        rr.replay("AEGIS-RB-UNKNOWN")
