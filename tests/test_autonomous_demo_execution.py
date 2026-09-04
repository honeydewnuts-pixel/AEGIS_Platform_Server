import asyncio
from types import SimpleNamespace

def test_autonomous_module_imports():
    from app.services.autonomous_execution_service import AutonomousDemoExecutionService
    assert AutonomousDemoExecutionService is not None

def test_mt5_adapter_module_imports_without_importing_mt5():
    from app.services.adapters.mt5_adapter import MT5Adapter
    a = MT5Adapter()
    assert a.ADAPTER_VERSION.startswith("V3-MT5")
    assert a.MAGIC == 236600
