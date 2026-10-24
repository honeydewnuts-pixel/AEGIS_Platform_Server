# Variant B V4 - pullback-failure (became Variant B after trend filter added)
# Two-stage state machine:
# 1. Record pullback: RSI or WPR crosses back through middle band after break.
# 2. Enter only when RSI9 crosses back through MA7 or middle band
#    in the direction of the original break (pullback failure).
# Trailing stop activates only after 1 ATR favorable movement.
# This is the core of the accepted Variant B / Variant B-V rulebook.
