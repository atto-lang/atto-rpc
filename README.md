# oreslang-rpc

Pure Oreslang RPC contracts, HTTP bindings, and interface-description generation.

There is no Java implementation layer in this package. The contract graph, validation, HTTP/RPC conversion, and schema emitters are all written in native Oreslang.

## What it does

`oreslang-rpc` keeps one transport-neutral contract graph and can project it in both directions:

- HTTP handler metadata -> RPC method definition
- RPC method definition -> HTTP handler metadata

The same graph emits:

- JSON Schema 2020-12
- Protocol Buffers v3 message definitions
- gRPC service definitions, including client/server/bidirectional streaming flags
- MessagePack shared definitions (`mpackdef v1`)
- TypeSpec models and HTTP route decorators

Those outputs are intended to become stable inputs for later TypeScript, Rust, Go, Dart, Gleam, Swift, Kotlin, and other client generators.

## HTTP routing interoperability

The package deliberately uses the same stable route metadata already carried by
[`oreslang-http-routing`](https://github.com/ores-truffle-oreslang/oreslang-http-routing):

- `handler_id`
- `pipeline_id`
- `contract_id`
- `operation_id`

The routing library owns path matching and dispatch. The RPC library owns wire-contract identity, request/response types, RPC service/method identity, and generated schemas.

A route generated from an RPC definition therefore preserves the exact IDs expected by `RouterBuilder.route(...)`. The reverse direction accepts those same HTTP handler fields and raises them into an RPC method.

HTTP request fields can also be bound explicitly without polluting the transport-neutral message type:

```ores
contracts.add_http_field_binding(
  rpc.http_path_field(42, "id", "id")
).unwrap();

contracts.add_http_field_binding(
  rpc.http_query_field(42, "include_deleted", "includeDeleted")
).unwrap();
```

Path/query/header/cookie bindings are validated against the RPC request message. Path fields must be required. Unbound request fields remain payload/body data when TypeSpec is generated.

See `examples/http_routing_interop.ores`.

## Contract model

Core definitions live in `src/rpc.ores`:

- `TypeRef`
- `FieldDef`
- `MessageDef`
- `RpcMethodDef`
- `HttpHandlerDef`
- `ContractSet`
- `ContractBuilder`

The builder fails closed on duplicate message names, duplicate wire field names/numbers, duplicate contract IDs, duplicate operation IDs, duplicate HTTP method/path pairs, unresolved request/response message types, and HTTP bindings without a matching RPC method.

Field numbers are shared by protobuf and MessagePack so one compatibility policy governs both representations.

The checked builder has deliberately conservative per-graph limits:
**64 messages**, **128 fields per message**, **256 RPC methods**,
**256 HTTP handlers**, and **512 HTTP field bindings**. It also rejects
duplicate HTTP path placeholders, contradictory `required + repeated`
fields, and ambiguous generated names. These are **cardinality limits**,
not yet byte-length/depth/output-size limits. The pinned Java runtime
does not provide a verified `String.length` member, so byte budgets and
recursion-depth admission remain release blockers for arbitrary untrusted
contracts.

Field-number text must now be the **canonical decimal representation** of its
integer value, with no leading zeros, signs, whitespace, or substitutions.
Validation uses bounded integral arithmetic and rejects mismatches before code
generation; field IDs 19000–19999 remain reserved by protobuf.

For untrusted inputs use `generate_all_checked(...)` and handle its
`Result<GeneratedBundle, String>`. It conservatively admits HTTPS ASCII schema
IDs, identifier-only dotted protobuf packages/TypeSpec namespaces, and simple
slash-separated literal or `{field}` HTTP paths. Route placeholders must match
explicit required path bindings in both directions. HTTP header collisions are
checked case-insensitively. Malformed or reserved cross-IDL names reject.

Message, field, service, RPC method, and referenced message type names
must satisfy the compiler's identifier predicate before they can become
schema/IDL source. HTTP field binding names must satisfy the identifier
predicate, while external wire names must satisfy the route-segment predicate.

HTTP field bindings also reject two request fields claiming the same external
wire parameter within one contract and location. Equivalent names in distinct
locations or distinct contracts remain separate; header-name case folding and
full transport parser compatibility still need independent verification.
Low-level emitter functions (`json_schema`, `protobuf`, `typespec`,
`messagepack_defs`, and legacy `generate_all`) remain **trusted-only APIs**;
they do not perform all generator-entry checks. The checked entrypoint rejects
unsafe top-level names, but no full compiler-executed verification has yet been
completed. Keep untrusted schema publication disabled until full source and
external parser checks are green.

## Example

```ores
import module rpc from "./src/rpc.ores";

pub routine main(): void {
  val request = rpc.message("GetUserRequest", arr[
    rpc.field("id", 1, "1", rpc.string_type(), true, false)
  ]);

  val response = rpc.message("User", arr[
    rpc.field("id", 1, "1", rpc.string_type(), true, false),
    rpc.field("display_name", 2, "2", rpc.string_type(), true, false)
  ]);

  let contracts = rpc.builder();
  contracts.add_message(request).unwrap();
  contracts.add_message(response).unwrap();

  val method = rpc.rpc_method(
    42,
    "Users",
    "GetUser",
    "users.get",
    "GetUserRequest",
    "User"
  );

  contracts.add_rpc_as_http(
    method,
    "GET",
    "/users/{id}",
    1001,
    7
  ).unwrap();

  val graph = contracts.build().unwrap();

  val outputs = rpc.generate_all_checked(
    rt borrow graph,
    "https://example.test/schema/rpc",
    "example.api",
    "Example.Api"
  ).unwrap();

  // TextDocument is a sequence of native Oreslang String fragments.
  // A CLI/file/socket adapter can stream them without a Java StringBuilder.
  stdio.println(outputs.protobuf.part_count());
}
```

## Native text emission

The current Oreslang core intentionally has a small string surface. Generators therefore return a `TextDocument`: an ordered sequence of immutable string fragments and newlines.

That has two advantages:

1. schema generation requires no Java/host string builder;
2. callers can stream fragments directly to stdout, files, sockets, channels, or future build-tool APIs without first constructing one giant host string.

## MessagePack

MessagePack has no universal schema language equivalent to `.proto`. This package emits a deliberately small `mpackdef 1` shared definition. Maps use stable positive integer field keys matching protobuf field numbers.

See `docs/MESSAGEPACK.md` for compatibility rules.

## Validation

`tests/rpc_semantics.ores` exercises:

- HTTP -> RPC conversion
- RPC -> HTTP conversion
- contract/operation ID preservation
- request/response registration
- duplicate wire-field rejection
- missing-message rejection
- JSON Schema generation
- protobuf/gRPC generation
- MessagePack definition generation
- TypeSpec generation

The repository pins the compiler revision in `SOURCE_REF`.

## Compiler compatibility checkpoint (2026-10-06)

This repository tracks the latest 10 compiler PRs as **unmerged proposals**, without changing its stable compiler pin or API behavior. See [docs/compiler-pr-sync.md](docs/compiler-pr-sync.md) for oreslang-rpc-specific migration invariants, dependencies and validation gates.

## Runner CI and native-suite coverage

The `Test runner contracts` workflow uses a compiler test double to check the
runner's working directory, exact arguments, check-before-run ordering, output
comparison, and failure propagation. It rejects floating SOURCE_REF values and
dirty explicit compiler checkouts. Actions have read-only permissions and no
persisted credentials.

This is a runner gate, not evidence that the native RPC suite passes. The
2026-10-07 probe against compiler `5ffc52d9297d175307094d530293c69f1cafc7cd`
rejected mutation through readonly `messages_copy` in the library. The existing
SOURCE_REF remains unchanged until ownership migration and golden-output
validation succeed on a pinned compiler.

## Backend compatibility

See [the compiler compatibility contract](docs/BACKENDS.md) for pinned Java/LLVM
revisions, reproducible checks, and unsupported features.
