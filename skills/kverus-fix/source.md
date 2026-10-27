---
name: kverus-fix
description: Fix Verus verification errors by iterating minimal proof-preserving edits until verification succeeds. Use with an explicit target and verification command, or automatically discover the command and locate the target from fresh diagnostics when either input is unavailable.
license: MIT
metadata:
  author: kverus
  version: "1.0"
---

Fix Verus verification failures by iterating edits and verification until the verification command succeeds.

Preferred invocation:

```text
$kverus-fix target=path/to/entry.rs verify="<verification command>" error_message="<initial error message>" out_path=path/to/output
```

Automatic discovery:

```text
$kverus-fix mode=auto
```

Enter automatic discovery mode when `mode=auto` is requested or either `target` or `verify` is missing; otherwise use explicit mode. Treat any supplied value as authoritative and discover only the missing value. Do not ask for missing inputs until the discovery procedure below has been exhausted.

Treat `target` as an entry file for diagnosis, not as the only file that may be edited.

If `error_message` is provided, use it as a first-pass hint, then always trust fresh output from the verification command.

If `out_path` is missing, use a reasonable workspace-local default path and report it.

## Shared Verus References

Before adding verification annotations to executable functions or loops, read `../kverus-common/references/verus-syntax-quickref.md`.

If a failure appears caused by Verus syntax, modes, ghost/tracked values, loop invariants, quantifiers, specialized solvers, or tokenized state-machine rules, read the relevant reference under `../kverus-common/references/` before editing.

If verification shows that a `std`, `core`, or `alloc` API has no applicable vstd specification, read both `../kverus-common/references/std-external-specifications.md` and `../kverus-common/references/proof-engineering-and-trust-boundaries.md`.

## Objective

Given Verus code and its verification failure, produce a corrected version that passes verification while preserving proof intent.

Start from `target`, then modify only the smallest necessary dependency closure required to clear the verification failure.

## Automatic Discovery Mode

Discover the verification command before the target so that the target is grounded in fresh diagnostics.

### Discover the Verification Command

When `verify` is missing:

1. Inspect workspace instructions and documented developer workflows first, including `AGENTS.md`, `README*`, `CONTRIBUTING*`, CI configuration, `Makefile`, `Justfile`, task files, package manifests, and repository scripts.
2. Search those sources for commands that invoke Verus or a project wrapper's verification/check target. Prefer a repository-documented, non-interactive command scoped to the current project over a broad workspace command.
3. Use the known `target`, current package, and repository layout to rank candidates when available. Do not infer a command merely from an unrelated neighboring project.
4. Execute the strongest safe candidate from the repository root or the working directory required by its documentation, capturing stdout, stderr, exit status, and working directory. A verification failure is successful command discovery; command-not-found, argument/usage errors, or infrastructure failures are not.
5. If a candidate cannot execute, try the next well-supported candidate. Do not install tools, change project configuration, or execute deploy, publish, cleanup, or other destructive targets as part of discovery.

If no supported verification command can be found or launched, stop before editing and ask the user for `verify`, briefly listing the evidence checked and the candidates that failed.

### Locate the Target from Diagnostics

When `target` is missing, run the discovered or supplied verification command before choosing a target, even when `error_message` was supplied.

1. Read the earliest high-signal root-cause diagnostic, preferring Verus verification errors over cascaded Rust errors and warnings.
2. Resolve diagnostic locations against the verification command's working directory. Select the first in-workspace Verus/Rust source file directly associated with that root cause.
3. Exclude generated output, caches, vendored code, and external dependencies unless the diagnostic and repository layout clearly show that one is an editable project dependency required by the verification target.
4. When the primary diagnostic points at a call site but the failed obligation is defined in a local callee, specification, or proof module, inspect that dependency edge and choose the file that owns the smallest compliant repair. Treat that file as the entry target and keep any further edits within its smallest necessary dependency closure.
5. If several diagnostics are cascades of the same root cause, choose one target from the root cause. If they are independent, begin with the earliest failure and re-run verification before considering another target.

If verification succeeds, make no edits and report that no failing target exists. If diagnostics do not identify an in-workspace source file, inspect command/package scope and local module mappings; if the target still cannot be determined with reasonable confidence, stop before editing and ask the user for `target` with the relevant diagnostic locations.

### Confirmation Gate

After automatic discovery has resolved both `verify` and `target`, present the following to the user:

- the exact verification command and working directory
- the selected target path
- which values were supplied and which were discovered
- the root diagnostic and source location used to select the target

Ask the user to confirm this command-target pair, then stop and wait. Do not edit code or continue the repair/validation loop before explicit confirmation. If the user corrects either value, use the correction, refresh any affected diagnostic evidence, and present the resolved pair for confirmation again. If the user declines, make no edits.

## Missing Standard-Library Specifications

Use this branch only when fresh verification output implicates a `std`, `core`, or `alloc` API for which the active Verus/vstd version provides no applicable contract.

1. Confirm the root cause is a missing specification rather than a missing import, disabled module, version mismatch, unsupported type, unsatisfied trait bound, or an existing contract whose preconditions the caller has not proved.
2. Search the active `vstd` and the repository's existing external-spec libraries for the exact API and closely related operations. Reuse or extend a sound existing model instead of creating a duplicate specification.
3. Follow `std-external-specifications.md` to inspect the standard-library implementation and its source comments or API documentation for the exact Rust toolchain in use. Trace delegated helpers when the public method body alone does not establish its behavior.
4. Draft the smallest sound specification that preserves every relevant runtime effect while exposing only semantics justified by those sources. Keep reusable external contracts in the repository's dedicated external-spec library, not beside the failing caller.

Add the external specification and any minimal model, external type specification, proved bridge lemma, or broadcast group it requires. Re-run focused verification for the spec library and target, then run the resolved full verification command. Treat successful verification as evidence that the contract integrates with the proof, not that Rust's implementation has been verified.

## Hard Constraints

1. Do not modify existing `requires`.
2. Do not modify existing `ensures`.
3. Do not add new `assume(...)` statements.
4. Add or change `assume_specification` only through the missing-standard-library branch.
5. Do not add new `admit`.
6. Do not add `#[verifier::external_body]` to skip proof obligations.
7. Keep edits minimal and localized to the smallest necessary dependency closure.
8. Do not edit unrelated files.
9. Do not modify the exec code.

## Required Workflow

1. Resolve `verify` and `target` from explicit inputs or automatic discovery.
2. If automatic discovery was used, pass the confirmation gate and wait for the user's explicit approval.
3. Inspect the entry target file and immediate dependencies.
4. If `error_message` is provided, use it to prioritize the first repair attempt, but trust fresh command output when they differ.
5. Reuse the resolved verification command to collect current errors and classify any missing standard-library specification before ordinary proof repair.
6. Apply the smallest fix addressing the highest-signal error.
7. Re-run verification with the same command and working directory.
8. Repeat until verification succeeds or a real blocker remains.

Avoid broad refactors up front.

## Validation Loop

Use this exact loop:

1. inspect
2. verify
3. minimally edit
4. verify again
5. repeat

## Failure Policy

If you cannot make verification succeed without violating constraints:

1. Stop at the smallest blocking point.
2. Do not fabricate behavior.
3. Do not bypass proof obligations with banned constructs.
4. Generate a concise summary file under `out_path` describing:
   - blocking location(s)
   - why constraints prevent a compliant fix
   - what additional assumptions or spec changes would be required

## Output Expectations

Perform edits in-place in the workspace when allowed.

Report whether `verify` and `target` were supplied or discovered. If discovered, include the resolved command, working directory, target path, and the diagnostic evidence used to select it.

For every added or changed `assume_specification`, report the qualified API, spec location, Rust source and documentation basis, focused and full verification results, and the residual trusted boundary.

Keep explanation short unless asked for details.
