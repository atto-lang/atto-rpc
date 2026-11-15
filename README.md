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
