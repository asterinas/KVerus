# Spec: Audit kverus-common synchronization with an active Verus checkout
Id: kverus-common-sync
Goal: Verify the installed kverus-common skill's guide-derived references against an active Verus checkout, interpret the checker report faithfully, and drive the ordered repair policy until the checker no longer reports blocking errors.
> The bundled checker (scripts/check_sync.py) is read-only: it reports errors, warnings, and exit codes. Every reference edit is made by the executing agent in place, under the repair policy callee.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill (they govern every edit this spec makes to kverus-common references; the shared layer lives in the kverus-common spec):
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
- The checker is read-only and must stay that way in this spec: no step outside the repair policy may modify the Verus checkout or the kverus-common references.
- Repair order is fixed by the source skill: structural errors first, then unresolvable cross-references, then stale-source summaries; for stale-source warnings, update only relevant summaries.
- After every repair round the checker is re-run; a repair transaction ends only when the checker's exit code is no longer 1.
- A repair retry budget of 3 is temporary — the source skill gives no bound (recorded in the translation ledger).
- Deployment prerequisite (file-state dependency): the checker script self-bootstraps kverus.env at entry, searching upward from its own file without resolving symlinks for the env file written by install-skills.sh at `$AGENT_DIR/kverus.env`. That file must be present in deployments (or `KVERUS_ENV_FILE` must point at one); without it the script still runs but stays under whichever python3 launched it.
- When verus_root is not provided, the checker applies its own precedence: the `VERUS_ROOT` environment variable, then auto-discovery over the agent directory, the working directory, and their parents for `database/*/code/tools/verus` or `tools/verus` candidates containing `source/docs/guide/src` and `source/vstd`.

Inputs:
- verus_root % line  # path to the active Verus checkout (contains source/docs/guide/src and source/vstd); pass empty to let the checker fall back to VERUS_ROOT, then auto-discovery

Outputs:
- checker_report % text  # full stdout of the final checker run (ERROR/WARNING lines and the closing status line)
- checker_exit_code % int  # exit code of the final checker run: 0 synchronized, 2 warnings only, 1 blocking errors
- repair_status % enum(clean, repaired, repaired_with_warnings, warnings_triaged)  # final synchronization state after the policy ran

Config:
  requires_commands: [python3]
## 已批准命令
- python3

## Steps
1. [act] Run the synchronization checker
  - ← verus_root
  + → checker_report % text  # stdout of this checker run: ERROR/WARNING lines plus the closing status line
  + → checker_exit_code % int  # checker exit code: 0 clean, 2 warnings only, 1 blocking errors (or no Verus root resolved)
  > Runs the bundled checker. verus_root empty keeps the checker's own environment/discovery fallback in charge. The script self-bootstraps kverus.env at entry (see Constraints), so no shell sourcing preamble is needed here.
  > ```hop_python
  > argv = ["python3", spec_dir("scripts/check_sync.py")]
  > argv = argv + ["--verus-root", verus_root] if verus_root else argv
  > r = subprocess.run(argv, timeout: 300)
  > checker_report = r.stdout
  > checker_exit_code = r.returncode
  > ```
2. [act] Test whether the checker resolved a Verus root
  - ← checker_report
  + → root_absent % bool  # true when the report shows the no-root error; false when a root was provided or discovered
  > Deterministic substring test on the report — the checker prints this exact error text when no root reached it.
  > ```hop_python
  > root_absent = "no Verus root provided or discovered" in checker_report
  > ```
3. [branch] Provision a Verus root when none was resolved
  - ← root_absent
  + → effective_root % line  # root used by every later checker run; empty keeps the checker's own fallback in charge
  3.1. [case(root_absent)] Ask for the root and re-run the checker with it
    - ← checker_report, verus_root
    + → effective_root % line
    + → checker_report
    + → checker_exit_code
    3.1.1. [ask present_inputs=checker_report] Supply the active Verus checkout path
      - ← checker_report
      + → supplied_root % line  # user-supplied path to the active Verus checkout
      > The checker could not resolve a Verus root — its report is attached. Ask for the checkout directory that contains source/docs/guide/src and source/vstd.
    3.1.2. [act] Re-run the checker with the supplied root
      - ← supplied_root
      + → effective_root % line
      + → checker_report
      + → checker_exit_code
      > Same checker, now with the supplied root pinned. effective_root carries the supplied value onward.
      > ```hop_python
      > argv = ["python3", spec_dir("scripts/check_sync.py"), "--verus-root", supplied_root]
      > r = subprocess.run(argv, timeout: 300)
      > checker_report = r.stdout
      > checker_exit_code = r.returncode
      > effective_root = supplied_root
      > ```
  3.2. [case(root_absent == false)] Carry the resolved root forward
    - ← verus_root
    + → effective_root % line
    > No provisioning needed: the checker already ran with a provided or discovered root; an empty verus_root keeps that fallback in charge for reruns.
    3.2.1. [act] Carry the given root forward
      - ← verus_root
      + → effective_root
      > Deterministic passthrough: the root the checker already accepted stays in charge for interpretation and repair.
      > ```hop_python
      > effective_root = verus_root
      > ```
4. [reason] Interpret the checker report
  - ← checker_report, checker_exit_code
  + → triage_note % text  # which of the checker's five checks failed, with the exact errors and warnings to repair
  > Apply the injected exit-code semantics and five-check list to the report. For exit 1, enumerate every ERROR line grouped by the check that produced it. For exit 2, list each warning and classify stale-by-mtime findings from structural ones. Quote the exact listed paths into triage_note so repair planning is grounded in the report, not recalled.
  > [[kverus-common-sync-knowledge#What the checker verifies]]
  > [[kverus-common-sync-knowledge#Exit code semantics]]
5. [branch] Route by checker outcome
  - ← checker_exit_code
  + → repair_status % enum(clean, repaired, repaired_with_warnings, warnings_triaged)  # final synchronization state after the policy ran
  5.1. [case(checker_exit_code == 1)] Blocking errors — run the repair policy, then re-verify
    - ← triage_note, effective_root
    + → repair_status
    + → checker_report
    + → checker_exit_code
    5.1.1. [call kverus-common-sync-repair(triage_note: triage_note, verus_root: effective_root)] Apply the ordered repair policy
      + → checker_report: checker_report
      + → checker_exit_code: checker_exit_code
    5.1.2. [act] Record the blocking-path outcome
      - ← checker_exit_code
      + → repair_status
      > The callee finished only when the rerun's exit code left 1. Distinguish whether warnings remain.
      > ```hop_python
      > repair_status = "repaired_with_warnings" if checker_exit_code == 2 else "repaired"
      > ```
  5.2. [case(checker_exit_code == 2)] Warnings only — triage stale sources through the same policy
    - ← triage_note, effective_root
    + → repair_status
    + → checker_report
    + → checker_exit_code
    5.2.1. [call kverus-common-sync-repair(triage_note: triage_note, verus_root: effective_root)] Apply the ordered repair policy
      + → checker_report: checker_report
      + → checker_exit_code: checker_exit_code
    5.2.2. [act] Record the warnings-path outcome
      - ← checker_exit_code
      + → repair_status
      > After the callee, exit 0 means the stale summaries were updated; exit 2 means the remaining warnings were triaged as not-mattering, which the source policy allows.
      > ```hop_python
      > repair_status = "repaired" if checker_exit_code == 0 else "warnings_triaged"
      > ```
  5.3. [case(checker_exit_code == 0)] Already synchronized
    - ← checker_exit_code
    + → repair_status
    5.3.1. [act] Record the clean state
      - ← checker_exit_code
      + → repair_status
      > ```hop_python
      > repair_status = "clean"
      > ```
6. [exit] Deliver the audit outcome
  + → checker_report, checker_exit_code, repair_status
