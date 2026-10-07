# RPC wire, ownership, and binding conformance

Consumer contract is [Oreslang compiler PR #411](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/411).

The canonical binding matrix is: `const x` fixed/read-only; `val x` (`const mut x`) fixed/mutable; `let x` rebindable/read-only; `let mut x` rebindable/mutable. Mutable referent access requires ownership/exclusive borrow and cannot bypass read-only nested paths. Source uses `rt copy`, `rt take`, `rt share`, `rt borrow`, not pointer sigils.

RPC contracts and generated HTTP handlers transfer **serialized values**, never raw pointers, Java object identities, borrowed Oreslang views, closures, or executable function payloads. Reject those transitively in nested arrays, structs, unions and extension fields, not only at top level. Runtime endpoints may hold local callback function references, but generated wire schemas must not embed them.

Generated payload type must preserve readonly read paths by default. A decode into `const request` is a read-only receiver; mutation of a deserialized owned object requires `val request` or `const mut request`, with checked ownership. Avoid treating wire-immutability as proof that all aliases are frozen, and do not leak arena/borrowed decode views after response dispatch.

Cross-version schema evolution must preserve unknown fields only within configured size/depth bounds; never round-trip executable capabilities through unknown-field storage. Local channel transport can eventually carry callbacks/objects within an actor-safe domain, but RPC/actor mailbox channels always serialize.

Conformance: recursive forbidden-wire-capability rejection, alias-free decode, cancellation while streaming, borrowed-view lifetime, deep readonly mutation failure, explicit owned mutable decode, and schema/codegen parity.
