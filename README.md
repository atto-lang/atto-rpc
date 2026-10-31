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
  contracts.add_http_field_binding(
    rpc.http_path_field(42, "id", "id")
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

## Native full-document export and independent validation

The four `tests/export_*.ores` entry points each generate the same validated
contract graph and stream exactly one output format to `stdio.stdout.write`.
They never use `println` or insert a separator between `TextDocument`
fragments. `scripts/export-contracts.sh` requires a passing `scripts/test.sh`
preflight against an **exact, clean `SOURCE_REF` compiler checkout**. It checks
each source before executing and captures each complete guest stream. The
`scripts/emit-guest-document.py` helper uses the existing bounded-process
runner to terminate the process group if it exceeds its output or time
budget: **64 KiB** combined stdout/stderr for each compiler check,
**1 MiB** combined stdout/stderr for each artifact-producing execution,
and a configurable per-process timeout (**120 seconds** by default).
The pinned-compiler test preflight is also bounded. Invalid UTF-8,
empty artifacts, and any failed process prevent publishing a **new** output
directory. No partial destination is published on failure.

```bash
# Use a clean Java compiler checkout at the pinned SOURCE_REF.
# Build with JDK 25 and Maven as described in scripts/compiler.sh:
#   mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
export ORESLANG_SOURCE_DIR=/absolute/path/to/oreslang-source.java
export ORESLANG_COMPILER="$PWD/scripts/compiler.sh"
python3 -m pip install 'jsonschema==4.26.0'
python3 -m unittest discover -s tests -p 'test_*.py' -v

# Destination must NOT yet exist; parent directory must exist.
bash scripts/export-contracts.sh /tmp/rpc-contract-export-verified

# Requires real protoc and @typespec/compiler CLI (tsp) with
# @typespec/http installed in the TypeSpec project.
python3 scripts/verify-contract-output.py \
  --json-schema /tmp/rpc-contract-export-verified/contracts.schema.json \
  --protobuf /tmp/rpc-contract-export-verified/contracts.proto \
  --messagepack /tmp/rpc-contract-export-verified/contracts.mpackdef \
  --typespec /tmp/rpc-contract-export-verified/contracts.tsp
```

The independent validator checks JSON Schema 2020-12 and MessagePack
syntax, **cross-checks JSON Schema/MessagePack model registries, property
names, requiredness, field types and named references**, and runs external
`protoc`/`tsp` on the actual exported files. It rejects symlinks, empty or
over-1-MiB inputs, non-JSON NaN/Infinity tokens and malformed required
properties; external validators have 90-second timeouts. Missing validators
cause a failure, never a skipped success. It cannot compare numeric wire IDs
against JSON Schema (which has no field-number representation).

The eleven export harness tests use a **fake compiler** to verify
byte-preservation, process timeout, stdout/stderr overflow, UTF-8 rejection,
fixture parity and cleanup. The twelve validator unit tests cover parsing,
schema parity, malformed input and fail-closed behavior. These source-level
tests and their local model-level checks are **not native Oreslang guest
execution evidence**. The native fixture now has 102 expected output lines,
including six reserved MessagePack primitive-name rejections. Actual pinned
compiler execution, full artifact validation and security review are still
required.

The live output/time budget limits captured output and wall-clock time for
each invoked subprocess, but it is **not** a guest heap-memory limit, an
untrusted input-byte limit, a recursion-depth limit, or a total multi-process
work budget. These gaps still block untrusted RPC contract ingestion. The
compiler executable must also be independently attested to the pinned source
checkout; the SHA/clean-checkout checks do not establish binary provenance.

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
