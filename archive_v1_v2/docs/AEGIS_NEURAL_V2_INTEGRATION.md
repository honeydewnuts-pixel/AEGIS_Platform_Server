# AEGIS Neural v2 Integration Checkpoint

## Status

Integrated training checkpoint for the corrected AEGIS v2 rulebook and indicator template.

## Source material

- 139 supplied MT5 screenshots (`1440x720` PNGs).
- `AEGIS-NEW-RULEBOOK.pdf` / corrected rulebook v2 supplied by the project owner.
- Latest AEGIS server checkpoint supplied on 2026-08-25.

## Indicator/template authority

Install order is:

1. #7 MainBB30 White
2. #8 MainBB20 Cobalt/Cyan
3. #6 RSI9 Cobalt/Cyan
4. #4 MA7 Magenta
5. #1 Bands34 White
6. #3 Williams %R60 Brown
7. #9 Hidden Yellow
8. #2 Bands17 Green
9. #5 CCI6 Red

#3 and #6 are template/trend-following indicators and are not direct execution gates. #4 and #5 form the final execution filter.

## Neural model

- Model: `AEGIS_NEURAL_V2`
- Architecture: MLP `68 -> 64 -> 24 -> 3`
- Outputs: `HOLD`, `SELL`, `BUY`
- Input: 12-frame temporal visual feature window, summarized into 68 normalized statistics.
- Production inference: pure Python JSON weights; no PyTorch/TensorFlow dependency is required by the API server.

## Training method

The 139 screenshots did not contain explicit machine-readable BUY/SELL labels. Therefore the training target is a **rulebook-derived teacher probability**, not claimed human ground truth. This prevents invented labels while still using all supplied screenshots to calibrate the neural scorer against the corrected v2 rulebook.

The supplied screenshots also contain legacy orange rendering for the visible Williams %R line in several captures. That legacy color was used only for training-time visual calibration; the active template/color guard remains the exact v2 specification.

Training report:

- Samples: 139
- Teacher distribution: HOLD 4 / SELL 63 / BUY 72
- Holdout MSE: 0.002774
- Holdout direction agreement: 71.43%

The 71.43% figure is **agreement with the rulebook-derived teacher target**, not real-world trading accuracy or a claim of profitability.

## Integration

The former fixed-weight logistic-style `NeuralAssistService` has been replaced by the trained MLP. The service keeps the existing `off`, `confidence`, `filter`, and `hybrid` modes. In `hybrid` mode the trained network can veto a rule-fired BUY/SELL when the corresponding neural probability is below the configured veto threshold.

The active profile is now `indicator_stack=v2` + `rulebook=v2`.

## Verification performed

- Python compilation of modified backend services: PASS.
- Neural model loading: PASS.
- 68-feature extraction smoke test: PASS.
- Neural inference smoke test: PASS.
- v2 rule-engine smoke test: PASS.
- Model metadata and training report packaged with checkpoint.

## Important checkpoint qualification

This is the **first concrete Neural v2 integrated training checkpoint**. It is not represented as proof that the model has achieved production trading accuracy. The supplied screenshot set contains no explicit human BUY/SELL labels, so the next stronger validation stage should use labeled forward-test examples once those are available.
