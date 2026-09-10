from fastapi import APIRouter, HTTPException
from app.transfer.forex_transfer import ForexTransferEngine, SOURCE_RULEBOOKS

router = APIRouter(prefix='/transfer', tags=['transfer'])
_engine = ForexTransferEngine()

@router.get('/version')
def transfer_version():
    return {'transfer_engine_version': _engine.version, 'source_rulebooks': list(SOURCE_RULEBOOKS), 'live_trading': False}

@router.get('/eligibility')
def transfer_eligibility(source_rulebook_id: str, target_instrument: str, timeframe: str = 'M5'):
    if timeframe.upper() != 'M5':
        raise HTTPException(status_code=400, detail='UNSUPPORTED_TIMEFRAME')
    return _engine.eligibility(source_rulebook_id, target_instrument, data_available=False, data_valid=False, spread_available=False, enough_history=False).to_dict()

@router.get('/rulebook')
def transferred_rulebook_lookup(target_instrument: str, timeframe: str = 'M5'):
    # V39 fail-closed until a target dataset is actually audited and a transfer qualifies.
    raise HTTPException(status_code=404, detail='NO_QUALIFIED_RULEBOOK')
