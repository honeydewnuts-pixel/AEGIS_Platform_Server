# Volatility Shock — Integrity Audit

1. Preregistration committed at `c8647f3` **before** outcome analysis — VERIFIED.  
2. Hash `3b940d6fe42b07ab...` matches file — VERIFIED at run start.  
3. Shock uses only pre-bar volatility and completed bar i; outcomes from i+1 onward — no look-ahead by construction.  
4. Controls matched without future outcomes.  
5. N_BOOT reduced to 500 from prereg 1000 for runtime — **documented deviation**; intervals still reported.  
6. Bootstrap unpaired (shock vs control pools), not day-paired — limitation.  
7. V53.6 / production untouched.  
8. Decision consistent with gates (no E/F promotion path).
