# Spec: Apply the ordered repair policy for a failing kverus-common sync check
Id: kverus-common-sync-repair
Goal: Bring the installed kverus-common references back into synchronization by applying the source skill's ordered repair policy and re-verifying with the checker.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they govern every edit made to kverus-common references:
- Global rule 1 — Follow the active task skill's hard constraints for whether contracts, executable code, assumptions, or external bodies may be changed.
- Global rule 2 — When the active Verus version supports it, prefer `#[verus_spec(...)]` for newly added contracts and loop annotations on executable Rust. Keep `verus!` primarily for spec/proof declarations, external specifications, and syntax that attributes cannot express.
- Global rule 3 — Use `requires`, `ensures`, `assert`, loop invariants, and helper lemmas as the modular verification tools described by the guide.
- Global rule 4 — Use `expr@` as the guide's shorthand for `expr.view()` when working with abstract views.
- Global rule 5 — For loops, add invariants strong enough for entry, preservation, and exit reasoning; include surrounding facts explicitly when loop isolation requires them.
- Global rule 6 — Use `assert(...) by (bit_vector)` for bitwise facts, `assert(...) by (compute_only)` for fully computable spec facts, and `assert(...) by (nonlinear_arith)` for nonlinear arithmetic facts.
- Global rule 7 — Treat `#[verifier::external_body]` as a trusted verified/unverified boundary, not as an ordinary proof hint.
- Global rule 8 — Write contiguous bounds as chained comparisons when adjacent comparisons share the same intermediate expressions. Combine comparisons only when the chained form is logically equivalent; do not add a missing relation or strengthen a contract merely to form a chain.
- Global rule 9 — When two or more facts depend on the payload of the same `Option`, bind it once with `option matches Some(value) ==> { &&& ... }`. Keep a single implication as-is when binding the payload would not improve the expression.
- Global rule 10 — For every newly added Verus struct, determine its mode explicitly. Actively try `ghost struct` for constants, models, invariant markers, and other types used only by specifications or proofs. Use `tracked struct` for linear proof resources, and retain an ordinary struct whenever the type has runtime state or participates in executable behavior. Verify the selected mode instead of assuming a zero-sized marker must be executable.
- Global rule 11 — Use `use` declarations as much as possible for proof-only functions, lemmas, broadcast groups, and other proof symbols instead of repeatedly writing long fully qualified paths. Prefer explicit imports that remain unambiguous; retain a qualified path when it makes a rare reference clearer.
- Global rule 12 — In spec expressions over a `Seq` or a view (e.g. `bytes@`), prefer the range-slicing sugar `s[i..j]`, `s[..j]`, `s[i..]`, `s[i..=j]` over the equivalent `.subrange(...)`, `.take(...)`, `.skip(...)` calls.
- Global rule 13 — Use `returns expr` for a contract that fixes the exact return value, and `ensures` for other result or state properties; omit unused named return binders and unit return declarations such as `-> (r: ())`. Keep required casts in the `returns` expression and justify that the value fits.
- Global rule 14 — In ghost code, drop `as int` casts that Verus's auto-coercion makes redundant, keeping only the genuinely required ones. Let `E0308` identify missing casts rather than casting defensively.
- Repair order is fixed by the source skill: structural errors first (missing files, invalid source paths — the missing-root case is provisioned by the caller), then unresolvable cross-references, then stale-source summaries. For stale-source warnings, compare the cited guide source with the current reference and update only relevant summaries.
- The repair steps edit the installed kverus-common reference files in place; this is the source skill's maintenance flow. Ground every edit in the cited Verus guide sources or sibling reference files, never invent reference content.
- The checker rerun inside this spec uses the same self-bootstrapping script; an empty verus_root keeps the checker's own environment/discovery fallback in charge.
- The source skill gives no repair retry bound; this spec sets retry=3 on the repair transaction (temporary value recorded in the translation ledger).

Inputs:
- triage_note % text  # which checks failed and the exact errors/warnings to address, from the caller's interpretation
- verus_root % line  # root passed to every checker rerun; empty keeps the checker's own VERUS_ROOT/discovery fallback

Outputs:
- checker_report % text  # full stdout of the post-repair checker rerun
- checker_exit_code % int  # exit code of the post-repair rerun; blocking errors (1) exhaust the retry budget and fail this transaction

Config:
  requires_commands: [python3]
## 已批准命令
- python3

## Steps
1. [subtask retry=3] Apply the ordered repair policy and re-verify
  + → checker_report % text  # post-repair checker report
  + → checker_exit_code % int  # post-repair checker exit code
  1.1. [act free] Repair the installed kverus-common references per the policy
    - ← triage_note, verus_root
    > Work the policy in order — structural errors first, then unresolvable cross-references, then stale-source summaries:
    > [[kverus-common-sync-knowledge#Repair policy]]
    > On retry rounds, first re-read the checker report injected in the correction block (it reflects the previous round's repairs) before editing further.
    > Edit the installed reference files under the kverus-common skill directory directly, in place.
  1.2. [act] Re-run the checker after repairs
    - ← verus_root
    + → checker_report % text  # post-repair checker report (reassigned)
    + → checker_exit_code % int  # post-repair checker exit code (reassigned)
    > Runs the same self-bootstrapping checker against the repaired references. verus_root empty keeps the checker's own fallback.
    > ```hop_python
    > argv = ["python3", spec_dir("scripts/check_sync.py")]
    > argv = argv + ["--verus-root", verus_root] if verus_root else argv
    > r = subprocess.run(argv, timeout: 300)
    > checker_report = r.stdout
    > checker_exit_code = r.returncode
    > ```
  1.3. [check final] Verify the rerun cleared the blocking errors
    - ← checker_report, checker_exit_code
    + → ok % bool  # verdict: true when exit code is 0 or 2 (no blocking errors)
    + → note % text  # failure note: the remaining blocking report when exit code is 1
    > Mechanical verdict on the rerun's exit code.
    > ```hop_python
    > ok = checker_exit_code != 1
    > note = "" if ok else "blocking errors remain after repair (exit code 1): " + checker_report
    > ```
