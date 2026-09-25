from app.services.aegis_ai_service import AegisAiService

def test_ai_refuses_trade_command():
    s = AegisAiService()
    ans = s._answer("please buy GBPUSD for me now")
    assert "cannot place" in ans.lower() or "cannot" in ans.lower()

def test_ai_knows_feed():
    s = AegisAiService()
    ans = s._answer("how do I set up the OHLC feed mq5?")
    assert "OHLC" in ans or "Feed" in ans
