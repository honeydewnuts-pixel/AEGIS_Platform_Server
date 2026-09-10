# AEGIS V43 Neural Model Card

## Result
Validation accuracy: 40.5493%
Validation balanced accuracy: 37.7176%
Validation macro precision: 43.5498%
Validation log loss: 1.06190

Final Test accuracy: 40.8918%
Final Test balanced accuracy: 38.7451%
Final Test macro precision: 45.2325%
Final Test log loss: 1.06570

## Confidence-filtered directional evaluation
Threshold selected on Validation: 0.60
Validation: 181 signals / 142 resolved; precision 61.2676%; PF 1.33398; total R 19.93; max DD 12.615R.
Final Test: 177 signals / 125 resolved; precision 57.6000%; PF 1.14564; total R 8.375R; max DD 11.975R.

## Decision
REJECTED_FOR_PRODUCTION.
The model does not approach the required 85% precision gate, and the unseen Final Test PF deteriorates materially versus Validation. The model is retained as an auditable V43 research artifact only.
