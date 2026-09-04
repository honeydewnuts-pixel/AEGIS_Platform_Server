from app.services.neural_features_v3 import FEATURE_DIM, FEATURE_NAMES, extract_feature_vector
from app.services.neural_service import NeuralAssistService

def test_feature_vector_v3():
    frame={"band1":{"U":80,"M":140,"L":200},"ma4":150,"rsi6":130,"_indicator_top":0,"_indicator_bottom":300}
    out=extract_feature_vector([frame],{"RULE_A":0,"RULE_B":0,"RULE_C":0,"RULE_F":1,"EXPANSION_BUY":0,"EXPANSION_SELL":0})
    assert FEATURE_DIM==13 and len(out["vector"])==13 and len(FEATURE_NAMES)==13

def test_neural_v3_inference_does_not_override_rule():
    svc=NeuralAssistService()
    out=svc.apply([{"band1":{"U":80,"M":140,"L":200},"ma4":150,"rsi6":130,"_indicator_top":0,"_indicator_bottom":300}], {"signal":"BUY","confidence":0.85,"rule_name":"RULE_F","details":"test","rule_flags":{"RULE_F":1}})
    assert out["neural_model_version"].startswith("AEGIS_NEURAL_V3")
    assert out["signal"]=="BUY"
