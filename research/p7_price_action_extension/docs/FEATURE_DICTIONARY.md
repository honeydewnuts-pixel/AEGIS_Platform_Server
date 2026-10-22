# P7 Feature Dictionary (SOURCE_VERIFIED from engine)

| Feature | Formula |
|---------|---------|
| body | (close-open)/range; range=high-low; range=0→NaN |
| upper_wick | (high-max(open,close))/range |
| lower_wick | (min(open,close)-low)/range |
| close_location | (close-low)/range |
| relative_range | range / rolling_median(range,20) |
| move3/6/12 | (close-close.shift(k)) / rolling_median(range,20) |
| overlap | intersection(curr,prev)/union; denom0→NaN |
| inside | high≤prev_high AND low≥prev_low (equality counts) |
| outside | high>prev_high AND low<prev_low |

H1 complete: count=12, first=bucket, last=bucket+55m, regular 5-min spacing.
Decision time: bucket+1h.
