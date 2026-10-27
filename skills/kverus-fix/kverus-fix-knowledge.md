# kverus-fix knowledge

Companion knowledge for the kverus-fix spec. Mirrors the source skill's procedural sections (discovery, confirmation gate, missing-stdlib branch, failure policy); the Hard Constraints live verbatim in the spec's Constraints, not here.

## Shared reference reading order

Before adding verification annotations to executable functions or loops, read `../kverus-common/references/verus-syntax-quickref.md` (sibling kverus-common tree). If a failure appears caused by Verus syntax, modes, ghost/tracked values, loop invariants, quantifiers, specialized solvers, or tokenized state-machine rules, read the relevant reference under `../kverus-common/references/` before editing. If fresh verification output implicates a `std`, `core`, or `alloc` API with no applicable vstd specification, read both `../kverus-common/references/std-external-specifications.md` and `../kverus-common/references/proof-engineering-and-trust-boundaries.md` before drafting.

## Verification command discovery procedure

When verify is missing, discover it before the target so the target is grounded in fresh diagnostics:

1. Inspect workspace instructions and documented developer workflows first: `AGENTS.md`, `README*`, `CONTRIBUTING*`, CI configuration, `Makefile`, `Justfile`, task files, package manifests, and repository scripts.
2. Search those sources for commands that invoke Verus or a project wrapper's verification/check target. Prefer a repository-documented, non-interactive command scoped to the current project over a broad workspace command.
3. Use the known target, current package, and repository layout to rank candidates when available. Never infer a command merely from an unrelated neighboring project.
4. Execute the strongest safe candidate from the repository root or the working directory its documentation requires, capturing stdout, stderr, exit status, and working directory. A verification failure is successful command discovery; command-not-found, argument/usage errors, or infrastructure failures are not.
5. If a candidate cannot execute, try the next well-supported candidate. Never install tools, change project configuration, or execute deploy, publish, cleanup, or other destructive targets as part of discovery.

If no supported verification command can be found or launched, stop before editing and ask the user for the command, briefly listing the evidence checked and the candidates that failed.

## Target location from diagnostics

When target is missing, run the resolved verification command before choosing a target, even when an initial error message was supplied:

1. Read the earliest high-signal root-cause diagnostic, preferring Verus verification errors over cascaded Rust errors and warnings.
2. Resolve diagnostic locations against the verification command's working directory. Select the first in-workspace Verus/Rust source file directly associated with that root cause.
3. Exclude generated output, caches, vendored code, and external dependencies unless the diagnostic and repository layout clearly show one is an editable project dependency required by the verification target.
4. When the primary diagnostic points at a call site but the failed obligation is defined in a local callee, specification, or proof module, inspect that dependency edge and choose the file owning the smallest compliant repair. Treat that file as the entry target and keep further edits within its smallest necessary dependency closure.
5. If several diagnostics are cascades of the same root cause, choose one target from the root cause. If they are independent, begin with the earliest failure and re-run verification before considering another target.

If verification succeeds, make no edits and report that no failing target exists. If diagnostics do not identify an in-workspace source file, inspect command/package scope and local module mappings; if the target still cannot be determined with reasonable confidence, stop before editing and ask the user for the target with the relevant diagnostic locations.

## Confirmation gate presentation

After automatic discovery has resolved both the command and the target, present to the user:

- the exact verification command and working directory
- the selected target path
- which values were supplied and which were discovered
- the root diagnostic and source location used to select the target

The user approves the command-target pair, corrects either value, or declines. A correction is adopted as the new authoritative value, any affected diagnostic evidence is refreshed, and the resolved pair is presented again. A decline means no edits are made.

## Missing standard-library specification branch

Use this branch only when fresh verification output implicates a `std`, `core`, or `alloc` API for which the active Verus/vstd version provides no applicable contract:

1. Confirm the root cause is a missing specification rather than a missing import, disabled module, version mismatch, unsupported type, unsatisfied trait bound, or an existing contract whose preconditions the caller has not proved.
2. Search the active `vstd` and the repository's existing external-spec libraries for the exact API and closely related operations. Reuse or extend a sound existing model instead of creating a duplicate specification.
3. Follow `std-external-specifications.md` to inspect the standard-library implementation and its source comments or API documentation for the exact Rust toolchain in use. Trace delegated helpers when the public method body alone does not establish its behavior.
4. Draft the smallest sound specification that preserves every relevant runtime effect while exposing only semantics justified by those sources. Keep reusable external contracts in the repository's dedicated external-spec library, not beside the failing caller.

Add the external specification and any minimal model, external type specification, proved bridge lemma, or broadcast group it requires. Re-run focused verification for the spec library and target, then run the resolved full verification command. Treat successful verification as evidence that the contract integrates with the proof, not that Rust's implementation has been verified.

For every added or changed `assume_specification`, record: the qualified API, the spec location, the Rust source and documentation basis, the focused and full verification results, and the residual trusted boundary.

## Failure policy summary contents

When verification cannot succeed without violating the hard constraints, stop at the smallest blocking point, fabricate nothing, and bypass nothing. The summary file under out_path describes:

- blocking location(s)
- why the constraints prevent a compliant fix
- what additional assumptions or spec changes would be required

Keep the summary concise. It is the only file this spec writes.
