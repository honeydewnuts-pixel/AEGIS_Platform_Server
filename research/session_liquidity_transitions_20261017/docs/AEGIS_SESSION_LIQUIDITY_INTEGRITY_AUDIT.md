# Session Liquidity — Integrity Audit Notes

1. **Preregistration** committed at `966214a` before analysis (VERIFIED).  
2. **Controls:** Primary used 03:00/15:00 UTC. Findings correctly note this stacks the deck toward detecting “busy vs quiet,” not transition-specific effects. T2≈T1 ratio is the key integrity check.  
3. **Bootstrap:** Resample of event and control observations (not day-paired); dependence partially addressed; limitation disclosed.  
4. **No volume/depth** — liquidity not measured.  
5. **No executable simulation** — no net trading claim.  
6. **DST:** Fixed UTC only in primary.  
7. **V53.6 / production:** unchanged.
