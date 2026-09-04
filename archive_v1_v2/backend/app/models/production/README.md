# AEGIS Neural production models

## Active

- `aegis_neural_v2.json` — **production** MLP `68→64→24→3` (HOLD/SELL/BUY)
  - Loaded by `app.services.neural_service.NeuralAssistService`
  - Pure Python inference (no PyTorch on the API server)
  - Trained on 139 MT5 screenshots vs rulebook-v2 teacher
  - Holdout direction agreement ≈ 71.4% (teacher agreement, not live PnL)

## Backups

- `aegis_neural_v1_logistic_backup.py` — previous underfit logistic assist
- `aegis_neural_v2_200samps_55pct_weights.json` — prior calibrated weights if present

## Note on `.pt` checkpoints

If a ChatGPT/PyTorch `.pt` file is supplied, export it to the same JSON schema
(`version`, `architecture`, `feature_dim=68`, `classes`, `normalization`, `layers`)
before production deploy. Render does not require torch at runtime.
