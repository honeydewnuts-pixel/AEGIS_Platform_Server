from .v31_gbpusd_5m import evaluate as evaluate_v31
from .v35_gbpusd_5m import evaluate as evaluate_v35

EVALUATORS = {
    "AEGIS-RB-V31-GBPUSD-5M": evaluate_v31,
    "AEGIS-RB-V35-GBPUSD-5M": evaluate_v35,
}
