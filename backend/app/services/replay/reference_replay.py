from __future__ import annotations
from pathlib import Path
import hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[2] / "data" / "research"
DATASET = ROOT / "AEGIS_V37_STANDARDIZED_GBPUSD_5M.csv"
LEDGERS = {
    "AEGIS-RB-V31-GBPUSD-5M": ROOT / "AEGIS_V37_V31_REFERENCE_REPLAY.csv",
    "AEGIS-RB-V35-GBPUSD-5M": ROOT / "AEGIS_V37_V35_REFERENCE_REPLAY.csv",
}
EXPECTED_DATA_SHA256 = "6e962ec23023f9c747514bed17077a9bc7dadc4b42591feb1e29140c1e580ed5"


class ReferenceHistoricalReplay:
    """Deterministic historical replay adapter over the frozen V37 reference ledgers.

    Full dataset hash verification runs only when
    AEGIS_V37_STANDARDIZED_GBPUSD_5M.csv is present (external large artifact).
    Ledger CSVs alone are enough for count/metric checks in CI.
    """

    def __init__(self, dataset: Path = DATASET, *, require_dataset: bool = False) -> None:
        self.dataset = Path(dataset)
        self.dataset_validated = False
        if self.dataset.exists():
            self._validate_dataset()
            self.dataset_validated = True
        elif require_dataset:
            raise FileNotFoundError(
                f"Missing research dataset: {self.dataset} "
                "(see EXTERNAL_LARGE_ARTIFACTS.md)"
            )

    def _validate_dataset(self) -> None:
        h = hashlib.sha256(self.dataset.read_bytes()).hexdigest()
        if h != EXPECTED_DATA_SHA256:
            raise ValueError(f"Unexpected V37 dataset SHA-256: {h}")
        df = pd.read_csv(self.dataset, usecols=["datetime"])
        dt = pd.to_datetime(df["datetime"], errors="raise")
        if not dt.is_monotonic_increasing:
            raise ValueError("V37 dataset is not chronologically sorted")

    def replay(self, rulebook_id: str) -> pd.DataFrame:
        try:
            path = LEDGERS[rulebook_id]
        except KeyError as exc:
            raise ValueError("NO_QUALIFIED_RULEBOOK") from exc
        if not path.exists():
            raise FileNotFoundError(path)
        return pd.read_csv(path)
