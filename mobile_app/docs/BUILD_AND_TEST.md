# AEGIS Mobile v2.0.0 — Build and Regression Test

## Purpose

This build is a clean mobile capture/upload baseline based on the previously
working Android behavior plus the newer registry, MT5, diagnostics, and safety
features.

### Upload invariants

1. Screenshot capture must work independently of MT5 worker availability.
2. `POST /aegis/analyze` is always sent with `image`, `account_id`, and
   `captured_at_ms`.
3. `symbol` is optional and is sent only after `/api/trading/health` confirms
   that the account has a connected MT5 worker.
4. A missing/unavailable worker therefore cannot turn a valid screenshot into
   a 400 upload failure.
5. Only transient HTTP failures (408, 425, 429, 5xx) and transport failures
   are retried/queued. Permanent 4xx responses are not placed in an endless
   offline queue.
6. Each capture uses a unique temporary JPEG filename; concurrent captures can
   never overwrite one another.
7. Uploads are serialized so frames cannot race through a shared transport path.
8. Release builds do not log multipart request bodies.

## Required device acceptance

After installing the APK and configuring the Render URL/API key:

- Start capture with MT5 visible.
- Confirm `Backend Reachable: YES`.
- Confirm `Last Upload: SUCCESS`.
- Confirm `Last HTTP Code: 200`.
- Confirm `Uploads OK` increments with successful captures.
- If MT5 worker is not connected, screenshot uploads must still succeed.
- If MT5 worker is connected and a symbol is configured, synchronized market
  data may be attached to the upload.

## CI

GitHub Actions builds `assembleDebug` and runs `testDebugUnitTest`.
The generated debug APK is uploaded as the `aegis-mobile-v2-debug` artifact.
