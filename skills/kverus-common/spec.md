# Spec: kverus-common — shared reference router and Verus-root resolver

Id: kverus-common
Goal: Route a proof task to the exact reference files under references/, machine-verify a candidate Verus checkout root against the acceptance trees, and confirm a cited file exists — the machine core of the shared reference layer. The selection cognition and the fourteen global guide rules live in the knowledge document and in every KVerus spec's Constraints.
Constraints:
- Loading discipline from the source: before editing Verus code, load only the relevant reference for the situation; the topic input carries the executor's classification, never a forced read.
- The exec-preservation topic is mandatory before any addition, removal, or rewrite of executable Rust, and before placing verification-added use imports relative to the original import list; this spec routes references, it never edits code.
- The locate step of the source's path-resolution procedure — inspecting the verification command, repository scripts and configuration, environment, and submodule metadata — is executor cognition; the machine verifies the candidate root by the acceptance trees only. Nothing is invented: a rejected root or a missing file reports as unresolved.
- Topic words (eleven): none, syntax, repair-triage, proof-constructs, invariants, ghost-tracked, trust-boundaries, std-external, exec-preservation, concurrency, unsupported. sub_reference carries the unsupported-features topic file name when topic is unsupported; an empty sub_reference loads the index only.
- citation is a root-relative path under the Verus root — source/docs/..., source/vstd/..., examples/... forms; project paths resolve relative to workspace, never against the spec directory.
- No [commit]: the source defines no file deliverable; every result rides the exit payload (L3 family ruling).
- No external command surface: the machine core uses existence probes only, no subprocess channels.
- Global Verus guide rules carried verbatim from the kverus-common skill into all KVerus skills (the source's fourteen):
- Global rule 1 — Follow the active task skill's hard constraints for whether contracts, executable code, assumptions, or external bodies may be changed.
- Global rule 2 — When the active Verus version supports it, prefer `#[verus_spec(...)]` for newly added contracts and loop annotations on executable Rust. Keep `verus!` primarily for spec/proof declarations, external specifications, and syntax that attributes cannot express.
- Global rule 3 — Use `requires`, `ensures`, `assert`, loop invariants, and helper lemmas as the modular verification tools described by the guide.
- Global rule 4 — Use `expr@` as the guide's shorthand for `expr.view()` when working with abstract views.
- Global rule 5 — For loops, add invariants strong enough for entry, preservation, and exit reasoning; include surrounding facts explicitly when loop isolation requires them.
- Global rule 6 — Use `assert(...) by (bit_vector)` for bitwise facts, `assert(...) by (compute_only)` for fully computable spec facts, and `assert(...) by (nonlinear_arith)` for nonlinear arithmetic facts.
- Global rule 7 — Treat `#[verifier::external_body]` as a trusted verified/unverified boundary, not as an ordinary proof hint.
- Global rule 8 — Write contiguous bounds as chained comparisons when adjacent comparisons share the same intermediate expressions. For example, use `a <= b <= c < d` instead of `a <= b && b <= c && c < d`, including in contracts, invariants, and proof assertions. Combine comparisons only when the chained form is logically equivalent; do not add a missing relation or strengthen a contract merely to form a chain.
- Global rule 9 — When two or more facts depend on the payload of the same `Option`, bind it once with `option matches Some(value) ==> { &&& ... }`. Do not repeat `option is Some ==> ... option->0 ...` clauses. Keep a single implication as-is when binding the payload would not improve the expression.
- Global rule 10 — For every newly added Verus struct, determine its mode explicitly. Actively try `ghost struct` for constants, models, invariant markers, and other types used only by specifications or proofs. Use `tracked struct` for linear proof resources, and retain an ordinary struct whenever the type has runtime state or participates in executable behavior. Verify the selected mode instead of assuming a zero-sized marker must be executable.
- Global rule 11 — Use `use` declarations as much as possible for proof-only functions, lemmas, broadcast groups, and other proof symbols instead of repeatedly writing long fully qualified paths. Apply this throughout proof code, including contracts, lemma calls, `reveal`, and `broadcast use` expressions. Prefer explicit imports that remain unambiguous; retain a qualified path when it makes a rare reference clearer.
- Global rule 12 — In spec expressions over a `Seq` or a view (e.g. `bytes@`), prefer the range-slicing sugar `s[i..j]`, `s[..j]`, `s[i..]`, `s[i..=j]` over the equivalent `.subrange(...)`, `.take(...)`, `.skip(...)` calls. The sugar accepts `Integer`-typed endpoints such as `usize`, so no `as int` cast is needed, and it desugars (inlined) to the same definition. See `references/verus-syntax-quickref.md` for the full table.
- Global rule 13 — Use `returns expr` for a contract that fixes the exact return value, and `ensures` for other result or state properties; omit unused named return binders and unit return declarations such as `-> (r: ())`. This applies to `assume_specification` models as well. Keep required casts in the `returns` expression (e.g. `as usize` on a `Seq` length) and justify that the value fits. See `references/verus-syntax-quickref.md`.
- Global rule 14 — In ghost code, drop `as int` casts that Verus's auto-coercion makes redundant (mixed-type comparisons and widened `+`, `-`, `*` arithmetic), keeping only the genuinely required ones: at a spec function's `int` parameter (unless the range-slicing sugar applies), at a standalone `/` divisor once the dividend is `int`, and at narrowing casts whose fit must be proven. Let `E0308` identify missing casts rather than casting defensively. See `references/verus-syntax-quickref.md`.
Config:
  requires_commands: []
  已批准命令: none — the machine core runs no subprocess; deployment needs nothing beyond the engine.
Inputs:
- candidate_root % line  # the executor's located candidate for the Verus checkout root; accepted only when it contains source/docs/guide/src and source/vstd
- topic % enum(none, syntax, repair-triage, proof-constructs, invariants, ghost-tracked, trust-boundaries, std-external, exec-preservation, concurrency, unsupported)
- sub_reference % line  # optional; the unsupported-features topic file name (e.g. drop.md); defaults to ""
- citation % line  # optional; a root-relative path under the Verus root to confirm before relying on it; defaults to ""
- workspace % line  # the target workspace root; project paths resolve against it

Outputs:
- verus_root % line  # the accepted checkout root, or "" when the candidate fails the acceptance trees
- root_accepted % bool
- selected_references % [line]  # reference file names under references/ for the routed topic
- citation_status % line  # not-requested / no-root / resolved / unresolved
- resolution_report % markdown

## Steps

1. [act] Preset the resolution state
  + → verus_root % line
  + → root_accepted % bool
  + → selected_references % [line]
  + → citation_status % line
  + → resolution_report % markdown
  > ```hop_python
  > verus_root = ""
  > root_accepted = false
  > selected_references = []
  > citation_status = "not-requested"
  > resolution_report = ""
  > ```

2. [reason] The candidate root arrives from the executor's own inspection of the verification command, repository scripts and configuration, environment, and submodule metadata. This spec machines only the acceptance half of the source's resolution procedure: the two trees below decide acceptance, citations confirm against the accepted root, and no path is ever invented — a rejected candidate leaves the root empty and the report says so.

3. [act] Run the root acceptance probe
  - ← candidate_root
  + → root_accepted % bool
  + → verus_root % line
  > ```hop_python
  > docs_ok = exists(path: candidate_root + "/source/docs/guide/src")
  > vstd_ok = exists(path: candidate_root + "/source/vstd")
  > root_accepted = docs_ok and vstd_ok
  > verus_root = candidate_root if root_accepted else ""
  > ```

4. [branch] Route the topic to the reference set
  - ← topic, sub_reference
  4.1. [case(topic == "none")] No reference is force-loaded
    4.1.1. [act] Keep the selection empty
      + → selected_references % [line]
      > ```hop_python
      > selected_references = []
      > ```
    4.1.2. [reason] The loading rule is guidance, not a machine duty: the executor reads the knowledge document and loads only what the situation demands — exactly the source's discipline of reading only the relevant reference before editing Verus code.
  4.2. [case(topic == "syntax")] Route syntax or mode confusion
    4.2.1. [act] Select the quick reference
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["verus-syntax-quickref.md"]
      > ```
  4.3. [case(topic == "repair-triage")] Route verification repair strategy and error triage
    4.3.1. [act] Select the error catalogue
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["common-errors.md"]
      > ```
  4.4. [case(topic == "proof-constructs")] Route proof construction and quantifier, arithmetic, bit-vector, or solver context issues
    4.4.1. [act] Select the proof-construction shelf
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["proof-localization.md", "quantifiers.md", "solvers.md", "arithmetic-lemmas.md", "calc-blocks.md", "opaque-reveal.md", "lemma-shape.md", "set-reasoning.md"]
      > ```
  4.5. [case(topic == "invariants")] Route loop or recursive proof failures and the invariant-versus-contract choice
    4.5.1. [act] Select the invariants reference
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["invariants.md"]
      > ```
  4.6. [case(topic == "ghost-tracked")] Route ghost, tracked, Tracked<T>, Ghost<T>, at, mode-marker placement, and erasure issues
    4.6.1. [act] Select the ghost-tracked reference
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["ghost-tracked.md"]
      > ```
  4.7. [case(topic == "trust-boundaries")] Route axiom-like declarations, external API specifications, trusted boundaries, spec twins, helper naming and scoping, and proof cleanup
    4.7.1. [act] Select the trust-boundaries reference
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["proof-engineering-and-trust-boundaries.md"]
      > ```
  4.8. [case(topic == "std-external")] Route missing or incomplete vstd specifications for std, core, or alloc APIs
    4.8.1. [act] Select the paired external-specification references
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["std-external-specifications.md", "proof-engineering-and-trust-boundaries.md"]
      > ```
  4.9. [case(topic == "exec-preservation")] Route executable Rust preservation
    4.9.1. [act] Select the preservation reference
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["exec-code-preservation.md"]
      > ```
    4.9.2. [reason] This route carries the source's hard ordering: the preservation reference is read and followed before any executable Rust change is edited or reviewed — it governs origin blocks, import placement, and the no-redistribution discipline for user code.
  4.10. [case(topic == "concurrency")] Route concurrency, invariants, permissions, and state-machine navigation
    4.10.1. [act] Select the tokenized state machine reference
      + → selected_references % [line]
      > ```hop_python
      > selected_references = ["tokenized-state-machine.md"]
      > ```
  4.11. [case(topic == "unsupported")] Route Verus-unsupported features and forced rewrites
    4.11.1. [act] Select the index plus the named topic file
      - ← sub_reference
      + → selected_references % [line]
      > ```hop_python
      > refs = ["unsupported-features/index.md"]
      > refs = refs + ["unsupported-features/" + sub_reference] if len(sub_reference) > 0 else refs
      > selected_references = refs
      > ```
    4.11.2. [reason] The source loads the index first and then the relevant topic file from that directory; sub_reference names that topic file (drop.md, transmute.md, pin.md, and the rest of the thirteen-page shelf), and an empty one honestly stops at the index.
  4.12. [case(else)] Keep the selection empty outside the documented word set
    4.12.1. [act] Keep the selection empty
      + → selected_references % [line]
      > ```hop_python
      > selected_references = []
      > ```

5. [act] Confirm the cited file against the accepted root
  - ← citation, verus_root
  + → citation_status % line
  > ```hop_python
  > citation_status = "not-requested" if len(citation) == 0 else ("no-root" if len(verus_root) == 0 else ("resolved" if exists(path: verus_root + "/" + citation) else "unresolved"))
  > ```

6. [act] Compose the resolution report
  - ← workspace, candidate_root, root_accepted, verus_root, topic, selected_references, citation_status, citation
  + → resolution_report % markdown
  > ```hop_python
  > resolution_report = "KVerus common reference resolution\n\nRoot acceptance\ncandidate: " + candidate_root + "\naccepted: " + ("yes" if root_accepted else "no") + "\nverus root: " + verus_root + "\n\nReference selection\nroute: " + topic + "\n" + join(selected_references, "\n") + "\n\nCitation check\nstatus: " + citation_status + "\ncited path: " + citation + "\nworkspace anchor: " + workspace
  > ```

7. [subtask retry=0] Seal the resolver contract
  7.1. [check final] Seal the resolver contract
    - ← root_accepted, verus_root, selected_references, citation_status, topic
    + → ok % bool
    + → note % text
    > ```hop_python
    > root_pair_ok = (len(verus_root) > 0) == root_accepted
    > words_ok = citation_status == "not-requested" or citation_status == "no-root" or citation_status == "resolved" or citation_status == "unresolved"
    > selection_ok = (len(selected_references) > 0) or (topic == "none")
    > ok = root_pair_ok and words_ok and selection_ok
    > note = "" if ok else "resolution state inconsistent: root pair " + str(root_pair_ok) + ", words " + str(words_ok) + ", selection " + str(selection_ok)
    > ```

8. [exit] Carry the resolution
  + → verus_root
  + → root_accepted
  + → selected_references
  + → citation_status
  + → resolution_report
