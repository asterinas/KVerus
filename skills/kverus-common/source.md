---
name: kverus-common
description: Shared Rust/Verus proof references for other KVerus skills. Use when Codex is repairing Verus failures, adding specifications, migrating Rust, classifying axioms or trusted boundaries, modeling external APIs, or cleaning proof scaffolding.
---

# KVerus Common

Use this skill as a shared reference layer for KVerus tasks. It does not define a standalone repair workflow; pair it with task skills such as `kverus-fix`, `kverus-spec`, or `kverus-migrate`.

## Loading Rule

Before editing Verus code, load only the relevant reference:

- Syntax or mode confusion: read `references/verus-syntax-quickref.md`.
- Verification repair strategy or error triage: read `references/common-errors.md`.
- Proof construction, quantifiers, arithmetic, bit-vector, or SMT context issues: read the relevant file under `references/` — `proof-localization.md`, `quantifiers.md`, `solvers.md`, `arithmetic-lemmas.md`, `calc-blocks.md`, `opaque-reveal.md`, `lemma-shape.md`, or `set-reasoning.md`.
- Loop or recursive proof failures, or choosing between a type invariant and explicit `inv()` contracts for a model: read `references/invariants.md`.
- `ghost`, `tracked`, `Tracked<T>`, `Ghost<T>`, `@`, mode-marker placement, or erasure issues: read `references/ghost-tracked.md`.
- Axiom-like declarations, external API specifications, trusted boundaries, pairing an exec helper with a spec model (`dual_spec`, spec twins, `when_used_as_spec`), proof helper naming and scoping, or proof cleanup: read `references/proof-engineering-and-trust-boundaries.md`.
- Missing or incomplete vstd specifications for `std`, `core`, or `alloc` APIs: read `references/std-external-specifications.md` together with `references/proof-engineering-and-trust-boundaries.md`.
- Any addition, removal, or rewrite of executable Rust, or placing verification-added `use` imports relative to the original import list: read and follow `references/exec-code-preservation.md` before editing or reviewing the change.
- Concurrency, invariants, permissions, or state-machine navigation: read `references/tokenized-state-machine.md`.
- Verus-unsupported features, forced rewrites, or trait associated constant limitations: read `references/unsupported-features/index.md`, then load the relevant topic file from that directory.

## Project Policy

Read the target workspace's instructions before applying these general references. For an Asterinas/VOSTD workspace, read `AGENTS.md` and `docs/coding-guidelines/README.md`, then follow the relevant linked guideline.

## Source Path Resolution

Resolve every citation from the target workspace; never assume a machine-specific absolute path.

1. Inspect the verification command, repository scripts and configuration, environment, and submodule metadata to locate the active Verus checkout.
2. Accept a candidate as the Verus root only when it contains the cited `source/docs/guide/src` and `source/vstd` trees.
3. Resolve `source/docs/...`, `source/vstd/...`, and `examples/...` relative to the discovered Verus root. Resolve project paths relative to the target workspace root.
4. Keep citations in these root-relative forms instead of resolving them against the skill directory. Confirm a cited file exists before relying on it; if no active checkout can be located, report the unresolved citation rather than inventing a path.

## Global Verus Guide Rules

Carry these rules into all KVerus skills unless the user explicitly requests a different policy:

1. Follow the active task skill's hard constraints for whether contracts, executable code, assumptions, or external bodies may be changed.
2. When the active Verus version supports it, prefer `#[verus_spec(...)]` for newly added contracts and loop annotations on executable Rust. Keep `verus!` primarily for spec/proof declarations, external specifications, and syntax that attributes cannot express.
3. Use `requires`, `ensures`, `assert`, loop invariants, and helper lemmas as the modular verification tools described by the guide.
4. Use `expr@` as the guide's shorthand for `expr.view()` when working with abstract views.
5. For loops, add invariants strong enough for entry, preservation, and exit reasoning; include surrounding facts explicitly when loop isolation requires them.
6. Use `assert(...) by (bit_vector)` for bitwise facts, `assert(...) by (compute_only)` for fully computable spec facts, and `assert(...) by (nonlinear_arith)` for nonlinear arithmetic facts.
7. Treat `#[verifier::external_body]` as a trusted verified/unverified boundary, not as an ordinary proof hint.
8. Write contiguous bounds as chained comparisons when adjacent comparisons share the same intermediate expressions. For example, use `a <= b <= c < d` instead of `a <= b && b <= c && c < d`, including in contracts, invariants, and proof assertions. Combine comparisons only when the chained form is logically equivalent; do not add a missing relation or strengthen a contract merely to form a chain.
9. When two or more facts depend on the payload of the same `Option`, bind it once with `option matches Some(value) ==> { &&& ... }`. Do not repeat `option is Some ==> ... option->0 ...` clauses. Keep a single implication as-is when binding the payload would not improve the expression.
10. For every newly added Verus struct, determine its mode explicitly. Actively try `ghost struct` for constants, models, invariant markers, and other types used only by specifications or proofs. Use `tracked struct` for linear proof resources, and retain an ordinary struct whenever the type has runtime state or participates in executable behavior. Verify the selected mode instead of assuming a zero-sized marker must be executable.
11. Use `use` declarations as much as possible for proof-only functions, lemmas, broadcast groups, and other proof symbols instead of repeatedly writing long fully qualified paths. Apply this throughout proof code, including contracts, lemma calls, `reveal`, and `broadcast use` expressions. Prefer explicit imports that remain unambiguous; retain a qualified path when it makes a rare reference clearer.
12. In spec expressions over a `Seq` or a view (e.g. `bytes@`), prefer the range-slicing sugar `s[i..j]`, `s[..j]`, `s[i..]`, `s[i..=j]` over the equivalent `.subrange(...)`, `.take(...)`, `.skip(...)` calls. The sugar accepts `Integer`-typed endpoints such as `usize`, so no `as int` cast is needed, and it desugars (inlined) to the same definition. See `references/verus-syntax-quickref.md` for the full table.
13. Use `returns expr` for a contract that fixes the exact return value, and `ensures` for other result or state properties; omit unused named return binders and unit return declarations such as `-> (r: ())`. This applies to `assume_specification` models as well. Keep required casts in the `returns` expression (e.g. `as usize` on a `Seq` length) and justify that the value fits. See `references/verus-syntax-quickref.md`.
14. In ghost code, drop `as int` casts that Verus's auto-coercion makes redundant (mixed-type comparisons and widened `+`, `-`, `*` arithmetic), keeping only the genuinely required ones: at a spec function's `int` parameter (unless the range-slicing sugar applies), at a standalone `/` divisor once the dividend is `int`, and at narrowing casts whose fit must be proven. Let `E0308` identify missing casts rather than casting defensively. See `references/verus-syntax-quickref.md`.

## Source Basis

This skill summarizes the Verus guide under `source/docs/guide/src`, resolved against the Verus root above.
