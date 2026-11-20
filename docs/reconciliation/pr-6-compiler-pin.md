# PR #6 — pinned RPC compiler integration semantic reconciliation

Historical branch `1f772028c76a1ffaef761ee8d32576e9b5623d4c`; current main `bd02fafc178f88d16bace58089978440dfbff639`.

The historical request was to repin to compiler SHA `edea24f9bf980025b68650b749a3ef0fc1813c20`. Current main instead pins `4fe60a8b7d381b69695af17f5bfead27c5469da5`, and its shell test script already contains the historical runner failure-status fixes (identical blob to this old PR). **Preserve the current SHA** rather than silently rolling back verified dependency provenance to the older `edea24f`.

Current RPC contract: require exactly pinned clean compiler checkout and fail closed on missing/running-but-failed compiler, invalid or floating reference, and non-empty/unreadable git status. RPC requires both compile-only --check and exact platform=server runtime execution; failure of either is a failure, never a skipped success.

Add `tests/source-ref-forward-port.sh` as a small source-free **shape** gate: validates full lowercase immutable 40-hex ref and verifies the test runner still contains the relevant admission checks. It does not prove the compiler at that SHA was built or successfully ran; an inspected source string alone is not attestation.

This reconciliation intentionally changes neither stable `SOURCE_REF` nor existing test runner logic. Release needs exact-source compiler and dependent package execution with output matching its pinned oracle, plus authorized Actions/self-hosted evidence and independent review. Do not treat Git mergeability as a pin-upgrade success.
