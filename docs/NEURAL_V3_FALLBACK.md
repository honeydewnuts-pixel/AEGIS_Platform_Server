# AEGIS Platform Server V3 — Fallback Backup

Version: v2.3.6.6
Status: INACTIVE FALLBACK
Primary active checkpoint: AEGIS Platform Server V3 v2.3.6.6 Activated

This package is a reviewed copy of the supplied `AEGIS_v3_integration (1).zip`.
It is preserved as a rollback/fallback checkpoint and should not be activated
unless the primary V3 checkpoint fails validation or operation.

The package contains the supplied V3 rule engine, V3 neural service/model,
V3 feature extractor, V3 indicator stack, V3 rulebook descriptor, tests,
and training/replay artifacts.

No legacy V1/V2 activation is introduced by this fallback package.

Known caveat: the supplied source documents Rule A as experimental because
its Higher-Low/Lower-High pivot and cross sequencing details are not fully
specified by the rulebook text. This has not been silently changed here.
