from __future__ import annotations
import sys
import csv, hashlib, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.transfer.audit import sha256_file
from backend.app.transfer.forex_transfer import ForexTransferEngine, SOURCE_RULEBOOKS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'v39'
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = ['EURUSD','USDJPY','GBPJPY','EURGBP','AUDUSD','NZDUSD','USDCAD','USDCHF','EURCHF','EURJPY','AUDJPY','CADJPY','CHFJPY','EURAUD','EURNZD','GBPAUD','GBPCAD','GBPCHF','GBPNZD','AUDCAD','AUDCHF','AUDNZD','CADCHF','NZDJPY','NZDCAD','NZDCHF']

def main():
    rows=[]
    for symbol in TARGETS:
        for source in SOURCE_RULEBOOKS:
            rows.append({'instrument':symbol,'timeframe':'M5','source': 'LOCAL_WORKSPACE_AND_LIBRARY_INVENTORY','file_name':'','file_size_bytes':'','sha256':'','date_start':'','date_end':'','rows':'','columns':'','ohlc_available':'','bid_ask_available':'','spread_available':'','duplicate_count':'','chronology_status':'','missing_bar_characteristics':'','data_quality_status':'DATA_NOT_AVAILABLE','source_rulebook_id':source})
    fields=list(rows[0])
    with open(OUT/'AEGIS_V39_FOREX_DATA_INVENTORY.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    with open(OUT/'AEGIS_V39_FOREX_DATA_LINEAGE.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['source_rulebook_id','target_instrument','data_file','data_hash','normalization_version','parameter_mapping_version','result','qualification']);
        for r in rows: w.writerow([r['source_rulebook_id'],r['instrument'],'','','V39.1','V39.1-PREDECLARED-ATR-MEDIAN','DATA_NOT_AVAILABLE','DATA_NOT_AVAILABLE'])
    params=[]
    for source in SOURCE_RULEBOOKS:
        for symbol in TARGETS:
            params += [
              [source,symbol,'M5','compression_threshold','1.0','ratio of range/ATR; source mechanism frozen','predeclared source ratio threshold','preceding 12 completed bars','V39.1','Preserve V31/V35 compression mechanism in dimensionless form','NO_TARGET_DATA','PENDING'],
              [source,symbol,'M5','expansion_threshold','1.5','current range/ATR','1.5','current completed bar','V39.1','Preserve V35 expansion mechanism','NO_TARGET_DATA','PENDING'],
              [source,symbol,'M5','initial_sl','1.5 ATR','ATR-relative','1.5 ATR14','current ATR14','V39.1','Frozen source execution geometry','NO_TARGET_DATA','PENDING'],
              [source,symbol,'M5','trailing_stop','0.75 ATR','ATR-relative','0.75 ATR14','current ATR14','V39.1','Frozen source execution geometry','NO_TARGET_DATA','PENDING'],
              [source,symbol,'M5','max_holding_bars','72','bar count','72','fixed causal execution rule','V39.1','Frozen source execution limit','NO_TARGET_DATA','PENDING'],
            ]
    with open(OUT/'AEGIS_V39_TRANSFER_PARAMETER_SCHEMA.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['source_rulebook_id','target_instrument','timeframe','parameter_name','source_value','normalization_method','target_value','causal_window','adaptation_version','adaptation_reason','data_version','status']); w.writerows(params)
    common_header=['source_rulebook_id','target_instrument','timeframe','status','validation_trades','validation_pf','final_test_trades','final_test_pf','notes']
    for fn in ['AEGIS_V39_FOREX_TRANSFER_RESULTS.csv','AEGIS_V39_V31_TRANSFER_RESULTS.csv','AEGIS_V39_V35_TRANSFER_RESULTS.csv']:
        with open(OUT/fn,'w',newline='') as f:
            w=csv.writer(f); w.writerow(common_header)
            for symbol in TARGETS:
                sources=SOURCE_RULEBOOKS if fn.endswith('TRANSFER_RESULTS.csv') and fn=='AEGIS_V39_FOREX_TRANSFER_RESULTS.csv' else ((SOURCE_RULEBOOKS[0],) if 'V31' in fn else (SOURCE_RULEBOOKS[1],))
                for source in sources: w.writerow([source,symbol,'M5','DATA_NOT_AVAILABLE',0,0.0,0,0.0,'No target Forex OHLC/Bid-Ask dataset found in mounted workspace or Library; no performance evaluation executed.'])
    with open(OUT/'AEGIS_V39_SIX_BLOCK_ROBUSTNESS.csv','w',newline='') as f:
        csv.writer(f).writerow(['source_rulebook_id','target_instrument','block','trade_count','win_rate','pf','avg_R','total_R','max_drawdown','status'])
    for fn, rowspec in [('AEGIS_V39_LEAKAGE_AUDIT.csv',['no_future_ohlc','no_future_spread','no_future_atr','no_future_volatility','no_future_parameter_selection','no_future_timestamps','no_final_test_tuning','no_future_outcomes','no_future_confirmation']),('AEGIS_V39_EXECUTION_AUDIT.csv',['next_bar_entry','bid_ask_side','atr_stop','break_even','atr_trailing','time_exit','one_position','event_throttle','cost_treatment','instrument_specific_spread'])]:
        with open(OUT/fn,'w',newline='') as f:
            w=csv.writer(f); w.writerow(['audit_item','status','evidence']);
            for x in rowspec: w.writerow([x,'PASS' if 'future' in x or x in ('next_bar_entry','atr_stop','break_even','atr_trailing','time_exit','one_position','event_throttle') else 'PENDING','Architecture/policy audit; empirical target replay unavailable without target datasets.'])
    with open(OUT/'AEGIS_V39_INDEPENDENT_REPRODUCTION.csv','w',newline='') as f:
        csv.writer(f).writerow(['source_rulebook_id','target_instrument','status','reason'])
    with open(OUT/'AEGIS_V39_RULEBOOK_REGISTRY.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['rulebook_id','source_rulebook_id','target_instrument','timeframe','transfer_version','data_hash','qualification_status']);
    with open(OUT/'AEGIS_V39_INSTRUMENT_REGISTRY.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['instrument','asset_class','base_currency','quote_currency','timeframe','data_source','data_hash','coverage','spread_availability','volatility_profile','transfer_eligibility','qualification_status']);
        for s in TARGETS:
            base, quote=s[:3],s[3:]; w.writerow([s,'FOREX',base,quote,'M5','','','','UNKNOWN','NOT_COMPUTED','DATA_NOT_AVAILABLE','DATA_NOT_AVAILABLE'])
    with open(OUT/'AEGIS_V39_TRANSFER_DIAGNOSTICS.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['diagnostic','status','detail']); w.writerow(['target_dataset_count','0','No non-GBPUSD Forex target dataset found in mounted workspace; Library search found only registry/spec artifacts.']); w.writerow(['qualification_evaluations','0','No target data; no transfer performance fabricated.'])
    print(OUT)

if __name__ == '__main__': main()
