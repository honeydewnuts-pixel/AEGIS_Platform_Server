# Neural layer failover

1. BrainCVService loads **v3** rule engine + NeuralAssistServiceV3 when active_profile is v3.
2. On each evaluate(), neural apply() runs on the primary layer.
3. If primary throws, the service loads NeuralAssistService (v2) once and retries.
4. Response includes neural_layer: v3 | fallback_v2 | none.

Clients (Android, Windows, macOS) need no change — failover is server-side.
