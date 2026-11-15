# atto-rpc

Remote procedure call abstractions, transports, and protocol integration for AttoLang.

## Responsibilities

RPC invocation, schema evolution, transport contracts, and cross-process safety.

## Design guidelines

- Keep application-facing contracts separate from hosted Atto services.
- Explicitly specify error, cancellation, concurrency, and resource-lifecycle behavior where applicable.
- Document supported compiler backends, host restrictions, wire formats, and compatibility constraints.

## Development and verification

Use the source tree and CI for verified build/test commands. Tests should cover positive cases, invalid inputs, lifecycle behavior, and cross-backend interoperability where relevant.

## Status

This README describes the project's intended role. It does not imply that the listed APIs or platforms are already implemented or supported.

## Related

- [AttoLang](https://github.com/atto-lang)
- [Language specification](https://github.com/atto-lang/atto-spec)
- [Platform conformance](https://github.com/atto-lang/atto-platform-conformance)

## Repository ownership and contribution routing

**Belongs here:** RPC interface/schema and transport adapters, remote errors, deadlines, cancellation, stable serialization contracts and actor-safe calls.

**Belongs elsewhere:** HTTP route matching in atto-http-routing; serialization primitives in atto-serialization-and-validation; hosted gateway/service control in atto-co.

**Security and portability boundary:** Authenticate peers and capabilities, bound payloads and retries, fence stale actor/tenant generations and reject non-serializable closures over channels.

AttoLang is the public name; preserve existing Oreslang/.ores compatibility and use canonical .atto for new portable library source. This README defines scope, not feature readiness.

**Acceptance:** name exact source SHA/tree, runtime/toolchain, positive and negative checks and execution receipt before claiming support. Host-only tests and empty CI steps do not prove guest execution.

## Experimental RPC envelope v1 (host contract only)

The new `reference/rpc_envelope.py` provides deterministic UTF-8 JSON encode/decode for request, notification, response and error envelopes. The contract rejects duplicate JSON keys, unknown top-level fields, nonfinite constants, oversized messages (64 KiB), unsafe call IDs and invalid snake_case method/error names. Request and error responses are paired through a JS-safe numeric `id`; notifications intentionally have no ID.

This is **not** a production RPC transport, authentication layer, cancellation protocol, streaming implementation, or AttoLang guest runtime. It is a deliberately bounded reference surface for future backend parity work. Run `python3 -m unittest discover -s tests -v` to execute local host-only checks. Transport authentication, deadlines and actor generation fencing remain required integration work.

### Strict JSON numeric and nesting boundary

All params/results are recursively validated before encoding or after decoding: maximum 32 nested levels, string-only object keys, finite floating-point numbers, and signed integers within the exact JavaScript-safe ±(2^53−1) range. Encode wider integer values using a separately specified decimal-string schema. Malformed exponential values such as `1e9999` are rejected even if a parser maps them to infinity. This reference is still host-only.
