# Play Protect / harmful app on install

Sideloaded (non-Play-Store) APKs often trigger Google Play Protect.

This is not because AEGIS steals data. Common triggers:
- APK not from Play Store
- Debug or ad-hoc signing certificate
- Overlay / screen-capture permissions (optional chart capture)

## For clients
1. Distribute only release-signed APKs.
2. Install → More details → Install anyway (first time).
3. Long-term: Google Play or enterprise MDM.

AEGIS does not request SMS, contacts, or call logs.
