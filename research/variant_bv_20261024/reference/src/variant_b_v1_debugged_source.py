# Variant B V1 (original user logic, debugged) - signal generator + cash test
# Core differences from Variant B:
# - Break flags expire after 100 bars
# - Early short entry on RSI recross above middle band
# - Long pullback branch was unreachable in the original script
# - Chandelier trail uses 2.5 ATR from entry-bar extreme immediately
# Result on GBPUSD M5: 10,426 trades, -100% return (costs and overtrading)
# See conversation history for full debugging notes.
