from app.services.signal_rule_engine_v3 import SignalRuleEngineV3, crossed, side_of

def frame(p7u=100,p7m=150,p7l=200,p8u=110,p8m=150,p8l=190,rsi=150,ma=150):
    return {"price_band7":{"U":p7u,"M":p7m,"L":p7l},"price_band8":{"U":p8u,"M":p8m,"L":p8l},"band1":{"U":80,"M":140,"L":200},"rsi6":rsi,"ma4":ma,"price_close":210,"_indicator_top":0,"_indicator_bottom":300}

def test_screen_coordinate_direction():
    assert side_of(10,20)=="above"
    assert crossed(30,20,10,20)=="above"
    assert crossed(10,20,30,20)=="below"

def test_contraction():
    r=SignalRuleEngineV3().evaluate([frame(p8u=90,p8l=210),frame(p8u=90,p8l=210)])
    assert r.contraction==1 and r.expansion==0

def test_expansion_buy_rule():
    h=[frame(p8u=120,p8l=180,rsi=230,ma=220),frame(p8u=120,p8l=180,rsi=230,ma=220)]
    r=SignalRuleEngineV3().evaluate(h)
    assert r.expansion==1 and r.signal=="BUY" and r.rule_flags["EXPANSION_BUY"]==1

def test_expansion_sell_rule():
    h=[frame(p8u=120,p8l=180,rsi=50,ma=50),frame(p8u=120,p8l=180,rsi=50,ma=50)]
    r=SignalRuleEngineV3().evaluate(h)
    assert r.expansion==1 and r.signal=="SELL" and r.rule_flags["EXPANSION_SELL"]==1
