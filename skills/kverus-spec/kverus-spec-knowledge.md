# kverus-spec knowledge

Companion knowledge for the kverus-spec spec. Mirrors the source skill's "Shared Verus References", "Objective", and "Hard Constraints" sections where they guide editing behavior; nothing here adds to or contradicts the source.

## Shared reference reading order

Before annotating executable functions or loops, read `../kverus-common/references/verus-syntax-quickref.md` (the sibling kverus-common skill's reference tree, deployed next to this spec's skill directory). For other Verus syntax, modes, loop invariants, `decreases`, `recommends`, ghost/tracked values, or spec/proof helper patterns, read the relevant shared reference in that tree before editing. If the narrow exception requires adding, removing, or rewriting executable Rust, first read and follow `../kverus-common/references/exec-code-preservation.md`.

## Annotation focus

Add only the specification structure needed to improve proof readiness of the target file. Focus on, in order of typical applicability:

1. `requires`
2. `ensures`
3. loop invariants
4. `decreases`
5. `recommends`
6. `spec fn`
7. ghost/spec helper declarations

Prefer `#[verus_spec(...)]` for new executable-function contracts and supported loop annotations; use `verus!` for spec/proof helpers and constructs the active Verus attribute syntax cannot express. Do not focus on finishing proofs.

## Origin Rust record format

When executable logic must change under the narrow preservation exception, document the change using the exact reason-first `Origin Rust:` block-comment format defined in `../kverus-common/references/exec-code-preservation.md`. The format rules live in that file; this spec only requires consulting it before such an edit.

## Clarification carried from the source

The goal is NOT to fully prove the code. Improve the specification layer while preserving executable behavior, preparing the file for a later proof-generation stage.
