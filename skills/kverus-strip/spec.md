# Spec: Strip redundant proof code script-first under a whole-run rlimit guard, keeping the tree verified green
Id: kverus-strip
Goal: Remove all proof code that is not strictly necessary for verification to pass — bundled simplification script first (scoped by the supplied target scope, changed-file discovery when none), then agent postprocess, then the broader manual per-file stripping when a target scope exists — aggressively, per file, under the whole-run rlimit guard, keeping the tree verified green at every step and reporting the five required items honestly.

Constraints:
- Compact translation of the kverus-strip skill; this spec owns the routing, the whole-run rlimit guard, and the delete-verify-restore loop discipline, while the objective, hard constraints, the nine deletion patterns with keep-forms and cautions, failure recovery, the guard protocol detail, the bundled script reference, the module path mapping, and the report labels live in the companion knowledge document [[kverus-strip-knowledge]] — the deletion pattern priority order, pattern cautions, keep-forms, and per-pattern skips are read from [[kverus-strip-knowledge#Deletion patterns]] before any manual deletion.
- Global Verus guide rules carried verbatim from the kverus-common skill; they apply to every deletion candidate the script and the manual phase evaluate:
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
- Hard constraints carried verbatim from the source skill, governing both the script path and the manual path:
- Hard constraint A — never delete `assert(false)`; it intentionally marks unreachable paths and must be preserved (the bundled script also refuses it).
- Hard constraint B — do not modify executable Rust code, i.e. code outside `proof{}`, `ghost{}`, `spec fn`, `proof fn`.
- Hard constraint C — do not modify `requires`, `ensures`, `invariant`, `decreases`, or `recommends` clauses.
- Hard constraint D — do not add `assume`, `admit`, or `#[verifier::external_body]`.
- Hard constraint E — keep edits localized per file; never change multiple files in one pass.
- Compatibility (source header): requires a working Verus verification command.
- Invocation form (source): `$kverus-strip verify="<verification command>" target-dirs="<dir1,dir2>"`; the hyphenated argument-hint names map to underscore-joined spec inputs (target-dirs to target_dirs). `verify` is required; the other three are optional.
- Ask discipline (source conditional-ask rule): when the verification-command input is empty and the dry_run relay is not set, ask and stop before any editing (the blocking ask gate in the steps); under the dry_run relay the command stays empty without asking — the degradation never asks, because the enumeration it relays needs no verification command. The target-scope question is DEFERRED per the source — asked only at the manual-phase gate after the script path and postprocess have finished; an empty answer there skips the manual phase.
- Routing fidelity (chain model per the source's unconditional script-first rule and its Arguments bridge): every run takes the bundled script first — scoped by the explicit target scope when the scope input was supplied, changed-file discovery when not — then the agent postprocess (orphaned comment/binding/empty-branch cleanup, trusted-axiom-call review, formatter), then the broader manual stripping with the nine patterns when a scope exists. The whole-run guard wraps the entire session; the closing measurement follows the final full verification.
- Two policy layers, intentionally overlapping: the script carries the `src/refiner/simplifier.py` policy at function scope with its own per-candidate delete-verify-restore safety loop and rlimit perf guard (only for functions carrying an explicit `#[verifier::rlimit(...)]` budget); the manual phase carries the nine aggressive patterns, Pattern 1 first. Neither layer replaces the other.
- Script invocation mapping: the source's env sourcing (`. "$AGENT_DIR/kverus.env"` plus `$KVERUS_PYTHON`) maps at deployment to the engine-whitelisted `python3` prefix with `spec_dir("scripts/simplify_proof.py")`; the deployed script self-bootstraps the environment per the L1 ruling (env file + venv discovery are its own entry behavior). Flags passed: `--verify-command` when the effective verification command is non-empty (always on the standalone flow; omitted under the dry-run degradation, where the effective command is empty); `--format-command` when the derived formatter command is non-empty and the dry-run degradation is not in force (the source wrapper's no-verify branch passes no format flag); `--base`, `--target-dir`, `--function` when the corresponding inputs were supplied; `--modified-only` when the modified_only relay is set (the kverus-postprocess caller's default changed-lines scope); `--dry-run` when the dry_run relay is set (enumeration without edits). Never passed: `--perf-factor`, `--no-perf-guard`, `--deep-clean`, `--timeout`, `--repo-root`, `--file`, `--no-cleanup`, `--quiet`. The literal `{fn}` placeholder may ride inside a supplied verification command's `--verify-function {fn}` clause (script-side short-name substitution with unscoped auto-fallback; misuse exits 1). The script auto-appends `--time` to the command for its own rlimit accounting. The script asset ships via pack `--assets`, and the kverus.env plus its tree-sitter-verus venv are deployment prerequisites.
- Caller-relay inputs (postprocess composition interface): modified_only and dry_run are optional line relays, empty or not-"true" by default so the standalone flow is byte-for-byte untouched; the kverus-postprocess spec sets modified_only to relay its default changed-lines scope (the source wrapper's SIMPLIFY_SCOPE=modified mapping) and sets dry_run to relay its no-verification-command degradation (the source wrapper's --dry-run branch). The relays change only flag assembly and phase routing: under dry_run the ask gate never fires, the baseline measurement and snapshot, the manual-phase scope question, the whole-tree check, and the guard are skipped with sentinel reaffirmations, the script enumerates candidates without editing, and the report carries the dry-run disclosure.
- Script safety envelope (verbatim substance from the source): tree-sitter-verus is required and the script errors out when it is missing; fix the venv rather than substituting manual stripping, since only the script performs the per-candidate delete-verify-restore loop. The script skips runtime `assert!(...)`, never removes `assert(false)`, skips functions containing `admit`, `assume`, or `#[verifier::external_body]` when `--deep-clean` is absent (never passed here), removes one proof statement at a time, and keeps a removal only when the scoped trial still succeeds.
- Script outcome discipline: per-candidate bare outcome lines `✓ removed …`, `✗ kept … (verify failed)`, `~ kept … (rlimit exceeded: N > Kx baseline M)`, the tqdm postfix live tally, and the per-file `stripping <path>: N function(s)` log carry the run narrative; the closing machine-readable summary line `assert simplification files=N, …, kept_as_perf_hint=N` anchors classification (files= processed, removed= deletions, restored= restores). A run killed by an external budget prints no summary line — its committed deletions stand as the exhausted verdict; continue from what was committed, never restart with a larger budget.
- Polling silence while the script runs: no repeated status narration, no reprinting of output; poll at coarse intervals and report only on finish, timeout, failure, or materially new information.
- Script step is single-attempt: the script subtask carries retry=0 — one invocation, failure routes straight to its fallback classifier (engine semantics: retry=0 with a fallback block means the first failure lands in the fallback; P6 silent). This encodes the source's budget-exhaustion ruling — continue with committed edits, never auto-restart.
- The manual name filter, when the function input was supplied, restricts the manual phase's per-file passes the same way it restricts the script (only matching functions processed; qualified paths accepted).
- Module path mapping for scoped trials: `src/foo/bar.rs` maps to module path `foo::bar`; `src/lib.rs` maps to the crate name derived from the workspace manifest; the crate's module structure decides. Scoped trial form: the full verification command plus `-- --verify-only-module <module_path>`.
- Whole-run guard protocol: two total-rlimit measurements wrap the ENTIRE session — before any proof code is touched and after the entire simplification is finished (script plus postprocess plus manual phase plus formatter plus the final full verification; one pair, not one per file). Both use the project's full verification command with `--time` appended, identical command and scope. The rlimit count is Z3's deterministic machine-independent resource count; the ms figure is load noise. A cached no-op replay (~1-2s, no stats line) is not a measurement — force a real run via the trailing-newline trick on an in-scope file. Skip both measurements when the strip produced no changes or when the dry-run degradation is in force — an enumeration edits nothing, so there is nothing to measure and no snapshot to take. Snapshot the pre-strip content of in-scope files before the first deletion (a dirty worktree defeats plain git diff reconstruction). An unmeasurable or red baseline stops the run loudly before any deletion — no fallback on that gate (registered interpretation: the source's guard assumes a green baseline).
- Guard growth protocol: when post > pre — report the growth (both numbers, delta, percentage); restore most-recent-deletion-first with a full scoped-free re-run of the verification command per round, bounded (engine retry=10 means ten tolerated failures so up to eleven restore cycles — the source's approximate-ten bound plus one initial execution); before restoring, attribute the growth via scoped probes (`-- --verify-only-module <mod> --time`, then `-- --verify-function <fn> --time`); whatever growth remains after the bounded restores is reported plainly with the follow-up levers (error-span-guided re-add via `--profile`, relaxing the strip for the attributed function), leaving the tree verified green. Comment-only deletions are rlimit-neutral and never need the recovery loop.
- Failure recovery restore-only discipline: read the error to understand which proof fact is missing; restore ONLY the specific deleted code that provided that fact; when unsure, restore in reverse order (most recent first), re-checking after each; never add new proof code.
- Executor-side exploration disclosure: file enumeration, the pre-strip snapshot copies, restore copy-backs, scoped attribution probe runs, and cache-busting newline touches execute through the host's execution channel inside cognitive act-free steps — they are not the deterministic channel and are not entries in the approved commands list below.
- L6 dynamic-command discipline: user-supplied command strings are whitespace-split at this layer (no shell metacharacters); the first word of every executed command must be registered in the engine's command whitelist — this spec declares the four forms (python3, verus, cargo, rustfmt); a differently-prefixed verification wrapper is a deployment prerequisite (hopjit.yaml registry), not a spec defect.
- Provisional values (registered in the translation ledger): engine subprocess caps — script run 3600s, verification-shaped runs 900s, formatter 300s. Retry budgets — baseline 3, script 0 (single attempt by ruling), per-file manual unit 3, unified wholecheck 3, closing measurement 2, guard growth restore 10. Engine retry counting: retry=N tolerates N failures so up to N+1 executions; the three catch-hosting cases carry explicit retry=0 so a caught failure lands in the fallback block immediately instead of rerunning the phase.
- L24-family ruling: this spec edits files in place and the script itself commits each candidate deletion only after its trial succeeds; the spec takes no commit step (no delivery verb in the source); the exit carries the report.
- Approximations (registered): the files-processed tally comes from the script's summary `files=` count plus the enumerated manual file count (not a byte-diff); the pre-strip snapshot scope on the script path uses the changed-files discovery approximation; single-function runs compose the supplied scoped-trial command as given; a fully-restored run over-measures deletions harmlessly (closing delta ~0).
- Shared reference discipline: when proof constructs (proof blocks, ghost/tracked values, spec/proof functions) must be understood before deciding deletions, read the relevant reference under `../kverus-common/references/` first — for this skill's decision surface, `exec-code-preservation.md`, `ghost-tracked.md`, `proof-localization.md`, `lemma-shape.md`, `verus-syntax-quickref.md`, and `unsupported-features/index.md` under the sibling kverus-common references tree.

Inputs:
- verify % line  # required; the full verification command string (e.g. "cargo verus focus my_crate"); empty triggers the blocking ask gate
- target_dirs % line  # optional; comma-separated source directories or a single .rs file; empty means the script scans changed files and the scope question is deferred to the manual-phase gate
- function % line  # optional; comma-separated function short names or qualified paths restricting both the script and the manual phase; for single-function work pair the verification command with a scoped module trial per the knowledge document's invocation forms
- base % line  # optional; git base ref for changed-file discovery (e.g. origin/main)
- modified_only % line  # optional relay; "true" passes the script's --modified-only flag (functions overlapping the change's added lines) — set by the kverus-postprocess caller for its default changed-lines scope; empty or anything else preserves this spec's standalone whole-file scope within the supplied target dirs
- dry_run % line  # optional relay; "true" passes the script's --dry-run flag (enumerate candidates without editing) and degrades this spec's machinery — no baseline measurement, no manual-phase scope question, no whole-tree check, no guard — the kverus-postprocess caller sets it when no verification command exists; empty or anything else preserves the full standalone flow

Outputs:
- strip_report % markdown  # the five labeled items, labels verbatim from the source Output section
- strip_outcome % enum(completed, script_failed, verify_failed, measurement_failed)  # script_failed takes precedence when the bundled script hard-failed; then measurement_failed; then verify_failed; else completed
- script_rc % int  # the bundled script's exit code; -1 when the run was killed by the engine subprocess cap or died before returning
- pre_rlimit % int  # baseline whole-run rlimit count; -1 signals an unmeasurable or red baseline (which stops the run loudly before any deletion) or a dry-run enumeration that never measured
- post_rlimit % int  # closing whole-run rlimit count; -1 when the measurement was skipped (no changes, or the dry-run degradation skipped it) or unusable

Config:
  requires_commands: [python3, verus, cargo, rustfmt]
## 已批准命令
- python3
- verus
- cargo
- rustfmt

## Steps
1. [act] Test which invocation inputs are present and coerce the two caller relays
  - ← verify, target_dirs, function, base, modified_only, dry_run
  + → has_verify % bool  # true when the verification-command input was supplied
  + → has_target_dirs % bool  # true when the target-scope input was supplied
  + → has_function % bool  # true when the name filter input was supplied
  + → has_base % bool  # true when the git baseline ref input was supplied
  + → modified_only_active % bool  # true when the modified_only relay was set to "true"
  + → dry_run_active % bool  # true when the dry_run relay was set to "true"
  > Mechanical presence tests on the four invocation inputs, plus coercion of the two optional caller-relay inputs: each relay arrives as a line ("true" when the kverus-postprocess caller set it, empty or anything else when it did not), and `x == "true"` reads an unset relay as false so the standalone flow is untouched.
  > ```hop_python
  > has_verify = len(verify) > 0
  > has_target_dirs = len(target_dirs) > 0
  > has_function = len(function) > 0
  > has_base = len(base) > 0
  > modified_only_active = modified_only == "true"
  > dry_run_active = dry_run == "true"
  > ```
2. [branch] Resolve the verification-command input
  - ← has_verify, dry_run_active
  + → effective_verify % line  # the verification command string the run will execute; empty only under the dry-run degradation
  2.1. [case(dry_run_active)] Degrade to an empty command for the enumeration
    + → effective_verify
    2.1.1. [act] Record the dry-run degradation
      + → effective_verify
      > Deterministic degradation: a dry-run enumeration edits nothing, so it needs no verification command — the script lists candidates without editing, and this spec skips the baseline measurement, the manual-phase scope question, the whole-tree check, and the guard. This is the relay the kverus-postprocess caller uses when it has no verification command of its own; the ask gate below never fires under the degradation.
      > ```hop_python
      > effective_verify = ""
      > ```
  2.2. [case(has_verify)] Carry the given command
    - ← verify
    + → effective_verify
    2.2.1. [act] Carry the supplied command through
      - ← verify
      + → effective_verify
      > Deterministic passthrough of the supplied command string.
      > ```hop_python
      > effective_verify = verify
      > ```
  2.3. [case(has_verify == false)] Ask for the command and stop until answered
    2.3.1. [ask] Supply the verification command
      + → verify_answer % line  # user-supplied verification command string
      > The invocation is missing its required verification command. Ask for the working verification command for this crate. Execution halts until the answer arrives — the source's ask-before-editing rule.
    2.3.2. [act] Adopt the asked command
      - ← verify_answer
      + → effective_verify
      > Deterministic adoption of the asked value.
      > ```hop_python
      > effective_verify = verify_answer
      > ```
3. [act free] Derive the project formatter command
  + → format_command % line  # formatter command string derived from repository configuration; empty when the caller formats itself
  > Inspect the repository configuration (Cargo.toml, rustfmt.toml, CI configuration) and derive the project formatter command — typically `cargo fmt`. Produce an empty command when the caller runs an equivalent formatter and cleanup itself, per the source's omit-rule. The value feeds the script's format flag and the agent-side formatter runs later in this spec.
4. [act] Test whether a formatter command was derived
  - ← format_command
  + → format_present % bool  # true when a formatter command string exists
  > Mechanical presence test on the derived formatter command.
  > ```hop_python
  > format_present = len(format_command) > 0
  > ```
5. [branch] Measure the whole-run rlimit baseline and snapshot the in-scope files unless this is a dry-run enumeration
  - ← dry_run_active
  + → pre_rlimit, snapshot_ref
  > Route: a dry-run enumeration edits nothing, so there is no tree to guard and nothing to snapshot — take the skip arm below and reaffirm the sentinels (the branch interface is produced on every route). Otherwise take the whole-run rlimit baseline with the full verification command and `--time` appended, force a real measurement when the replay is a cached no-op, and copy the in-scope files aside before any deletion. The gate inside the measurement subtask stops the run loudly before the first deletion when the tree is red or no count can be extracted.
  5.1. [case(dry_run_active)] Skip the baseline for the enumeration
    + → pre_rlimit, snapshot_ref
    5.1.1. [act] Record the skip
      + → pre_rlimit, snapshot_ref
      > Deterministic skip record; the sentinel values stand reaffirmed on this path — the measurement never ran and nothing was copied aside.
      > ```hop_python
      > pre_rlimit = -1
      > snapshot_ref = ""
      > ```
  5.2. [case(dry_run_active == false)] Measure the baseline and snapshot
    + → pre_rlimit, snapshot_ref
    5.2.1. [subtask retry=3] Measure the whole-run rlimit baseline and snapshot the in-scope files
      + → pre_rlimit % int  # baseline whole-run rlimit count; -1 when unmeasurable
      + → snapshot_ref % line  # pre-strip snapshot copies of the in-scope files, or empty when nothing was copied
      > Take the whole-run rlimit baseline with the full verification command and `--time` appended, force a real measurement when the replay is a cached no-op, and copy the in-scope files aside before any deletion. The gate inside stops the run loudly before any deletion when the tree is red or no count can be extracted.
      5.2.1.1. [act] Run the full command with the time flag appended
        - ← effective_verify
        + → baseline_rc % int  # exit code of the baseline measurement run
        + → baseline_report % line  # merged stdout and stderr of the baseline run (reassigned each round)
        > The command string is whitespace-split at this layer, `--time` is appended for rlimit accounting, and the streams merge because diagnostics typically land on stderr.
        > ```hop_python
        > argv = split(effective_verify + " --time", " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > baseline_rc = r.returncode
        > baseline_report = r.stdout + r.stderr
        > ```
      5.2.1.2. [act free] Detect cached replays, force a real run, extract the count, and snapshot the files
        - ← baseline_report, has_target_dirs, target_dirs, has_base, base
        + → pre_rlimit
        + → snapshot_ref
        > Read the captured output for the aggregate stats line — a cached no-op replay prints none; force a real run by appending a trailing newline to an in-scope file before the command and removing it after (trailing whitespace encodes nothing, so the count is the true baseline of the clean content). Extract the rlimit count and refill this step's declaration with it, or -1 when no count can be extracted. Copy the in-scope files aside as the pre-strip snapshot — the supplied scope when one exists, otherwise the changed files from git history — because a dirty worktree defeats plain git diff reconstruction. The probe runs and the copies ride the host's execution channel inside this cognitive step, never the deterministic channel.
      5.2.1.3. [check final] Gate the baseline
        - ← baseline_rc, pre_rlimit
        + → ok % bool  # true when the baseline run exited green and a positive count was extracted
        + → note % text  # failure explanation naming the baseline gate
        > Mechanical verdict on the baseline pair. On failure the run stops loudly before any deletion — no fallback on this gate by design: a red or unmeasurable baseline violates the source's fail-before-touch discipline.
        > ```hop_python
        > ok = baseline_rc == 0 and pre_rlimit > 0
        > note = "" if ok else "baseline gate failed: the measurement run did not exit green or no rlimit count could be extracted; fix the tree or the command before stripping anything"
        > ```
6. [act] Pre-provision every later verdict and diagnostic variable with safe defaults
  + → script_rc % int  # -1 preset: killed by the engine subprocess cap or crashed before returning
  + → script_report % line  # empty preset
  + → script_failure_note % line  # empty preset
  + → module_rc % int  # -1 preset: scoped-check residual for the manual unit's retry rounds
  + → module_report % line  # empty preset: same residual role
  + → final_rc % int  # -1 preset
  + → final_report % line  # empty preset
  + → final_green % bool  # false preset
  + → edits_made % bool  # false preset
  + → manual_files % int  # 0 preset
  + → manual_edits % bool  # false preset
  + → manual_tally % line  # empty preset
  + → manual_phase_note % line  # empty preset
  + → fmt1_rc % int  # -1 preset
  + → fmt1_note % line  # empty preset
  + → fmt2_rc % int  # -1 preset
  + → fmt2_note % line  # empty preset
  + → wholecheck_failure_note % line  # empty preset
  + → growth_levers % line  # empty preset
  + → attribution_note % line  # empty preset
  + → recheck_rc % int  # -1 preset
  + → recheck_report % line  # empty preset: guard-round residual for the attribution step
  + → closing_rc % int  # -1 preset
  + → closing_report % line  # empty preset: closing-measurement residual for the extraction step
  + → guard_resolved % bool  # false preset
  + → guard_note % line  # empty preset
  + → measurement_valid % bool  # false preset
  + → postprocess_note % line  # empty preset
  + → dry_run_note % line  # empty preset
  > Engine failure semantics leave prior values intact when a container dies mid-flight or is killed by a cap, and fallback handlers of failed containers read the exports their sibling steps declared. Pre-provisioning every verdict and diagnostic variable here as literals guarantees each later consumer reads a valid value on every path — timeout kills, hard errors, and exhausted retries alike. All twenty-nine declarations carry types and safe sentinel values; the producing steps later refill them in place.
  > ```hop_python
  > script_rc = -1
  > script_report = ""
  > script_failure_note = ""
  > module_rc = -1
  > module_report = ""
  > final_rc = -1
  > final_report = ""
  > final_green = false
  > edits_made = false
  > manual_files = 0
  > manual_edits = false
  > manual_tally = ""
  > manual_phase_note = ""
  > fmt1_rc = -1
  > fmt1_note = ""
  > fmt2_rc = -1
  > fmt2_note = ""
  > wholecheck_failure_note = ""
  > growth_levers = ""
  > attribution_note = ""
  > recheck_rc = -1
  > recheck_report = ""
  > closing_rc = -1
  > closing_report = ""
  > guard_resolved = false
  > guard_note = ""
  > measurement_valid = false
  > postprocess_note = ""
  > dry_run_note = ""
  > ```
7. [subtask retry=0] Run the bundled simplification script once
  + → script_rc, script_report
  > Run the bundled simplification script exactly once — single attempt by ruling — with the verification command whenever the effective command exists (always on the standalone flow; omitted under the enumeration degradation, where the script lists candidates without a verification command), the formatter command when derived and the degradation is not in force, and the baseline ref, target scope, name filter, and the two caller relays when supplied. The script self-bootstraps its environment (deployment prerequisite: the env file and its tree-sitter venv). One-hour engine subprocess cap; a kill and a hard exit both land in the fallback classifier at the tail.
  7.1. [act] Invoke the script with the supplied flags
    - ← effective_verify, format_command, format_present, has_base, base, has_target_dirs, target_dirs, has_function, function, modified_only_active, dry_run_active
    + → script_rc, script_report
    > Assemble the argument vector from the supplied inputs — the verification command when the effective command is non-empty (always on the standalone flow; omitted under the enumeration degradation, where there is nothing to check); the formatter command when present and that degradation is not in force (the source wrapper's empty-command branch passes no format flag); the baseline ref, target scope, and name filter when supplied; `--modified-only` when the first caller relay is set (the kverus-postprocess caller's default changed-lines scope); `--dry-run` when the second caller relay is set (listing without edits) — run it under the engine subprocess cap, and merge the streams. The command strings ride as single arguments (the script splits the verification command itself). The script commits each candidate deletion only after its scoped trial succeeds.
    > ```hop_python
    > argv = ["python3", spec_dir("scripts/simplify_proof.py")]
    > argv = argv + (["--verify-command", effective_verify] if len(effective_verify) > 0 else [])
    > argv = argv + (["--format-command", format_command] if format_present and dry_run_active == false else [])
    > argv = argv + (["--base", base] if has_base else [])
    > argv = argv + (["--target-dir", target_dirs] if has_target_dirs else [])
    > argv = argv + (["--function", function] if has_function else [])
    > argv = argv + (["--modified-only"] if modified_only_active else [])
    > argv = argv + (["--dry-run"] if dry_run_active else [])
    > r = subprocess.run(argv, cwd: ".", timeout: 3600)
    > script_rc = r.returncode
    > script_report = r.stdout + r.stderr
    > ```
  7.2. [check final] Gate the script exit code
    - ← script_rc
    + → ok % bool  # true when the script process exited zero
    + → note % text  # failure explanation naming the script exit code
    > Mechanical verdict on the script process. The captured output carries the closing machine-readable summary line the classifier anchors on.
    > ```hop_python
    > ok = script_rc == 0
    > note = "" if ok else "simplification script exited " + str(script_rc) + "; see the captured output"
    > ```
  7.3. [on fail] Classify the failed script attempt
    7.3.1. [act free] Record which failure family fired
      - ← script_rc, script_report
      + → script_failure_note
      > A missing exit code (the preset sentinel) with no captured output means the engine subprocess cap killed the run mid-flight or the process died before returning — the exhausted family: committed deletions stand, continue from what was committed, never restart with a larger budget. A captured non-zero exit with diagnostics is a hard failure (missing tree-sitter venv, placeholder misuse, discovery error). Record which family fired and quote the captured output; the classifier step reads this narrative.
      > [[kverus-strip-knowledge#Script reference]]
8. [act free] Classify the script outcome
  - ← script_rc, script_report, script_failure_note
  + → script_verdict % enum(clean, exhausted, failed)  # clean: exited zero with a summary line (or empty discovery); exhausted: killed mid-run; failed: hard non-zero exit
  + → script_files % int  # files= count from the summary line; 0 on empty discovery
  + → script_edits % bool  # true when the summary shows any removal or restore
  + → script_tally % line  # the files/removed/restored/kept_as_perf_hint/verification_runs counts plus the per-file outcome legend
  > Classify from the exit code, the captured output, and the failure narrative. Anchors: exit zero plus the closing machine-readable summary line (files=, removed=, restored=, kept_as_perf_hint=, verification_runs=) is clean — read the counts; exit zero with no summary line and a no-Rust-files log is the empty-discovery clean (files=0); a killed run (sentinel exit code, no summary line) is exhausted — committed deletions stand, continue from what was committed; a hard non-zero exit with diagnostics is failed. The per-file outcome legend (removed / kept-trial-failed / kept-rlimit-exceeded), the tqdm postfix, and the per-file stripping log line live in the knowledge document. A dry-run enumeration exits zero listing its candidates; with no removal tallies in the output the classifier reads it as clean with zero counts — honest, since the enumeration edited nothing.
  > [[kverus-strip-knowledge#Script reference]]
9. [act] Fold the script tally into the run-level counts and compose the dry-run disclosure
  - ← script_files, script_edits, edits_made, dry_run_active
  + → files_processed % int  # files the script reported processing
  + → edits_made
  + → dry_run_note % line  # the dry-run degradation disclosure, empty when the degradation did not fire
  > Convergence: files processed starts at the script's summary count; the deletions-made flag folds in the script's edit evidence (any removal or restore). The dry-run disclosure composes here so the report carries it verbatim when the degradation fired — the enumeration applies no deletions, takes no measurements, and runs no whole-tree check.
  > ```hop_python
  > files_processed = script_files
  > edits_made = edits_made or script_edits
  > dry_run_note = "dry-run enumeration only: no deletions were made, no baseline or closing measurement was taken, and no whole-tree check ran" if dry_run_active else ""
  > ```
10. [branch] Route the agent postprocess on the script verdict
  - ← script_verdict
  + → postprocess_note, fmt1_rc, fmt1_note
  > Route on the script verdict: skip the agent postprocess when the script hard-failed (nothing it produced to clean); otherwise run the orphan cleanup, the trusted-axiom-call review, and the formatter gate.
  10.1. [case(script_verdict == "failed")] Skip the postprocess
    + → postprocess_note
    10.1.1. [act] Record the skip
      - ← script_rc
      + → postprocess_note
      > Deterministic skip record: the script hard-failed, so there is no script-shaped residue to clean; the tree stands as the script left it.
      > ```hop_python
      > postprocess_note = "postprocess skipped: simplification script exited " + str(script_rc)
      > ```
  10.2. [case(else)] Clean up and format
    + → postprocess_note, fmt1_rc, fmt1_note
    10.2.1. [act free] Clean orphans and review trusted-axiom calls
      + → postprocess_note
      > Agent postprocess over the script's footprint: clean orphaned comments, dangling bindings, and empty branches left by removals; review any trusted-axiom call the script introduced against the knowledge document's pattern cautions; never re-add deleted proof. Record what was cleaned and what the review found.
      > [[kverus-strip-knowledge#Deletion patterns]]
    10.2.2. [branch] Format the cleaned tree when a formatter command exists
      - ← format_present
      + → fmt1_rc, fmt1_note
      > Formatter gate: when a formatter command was derived, format once here (idempotent — the manual phase formats again after its own edits); when none was derived, the caller formats itself — record the skip.
      10.2.2.1. [case(format_present)] Run the formatter once
        + → fmt1_rc, fmt1_note
        10.2.2.1.1. [subtask retry=0] Format the tree
          + → fmt1_rc, fmt1_note
          > Run the derived formatter command over the workspace once and record the exit code with a short outcome narrative. Whitespace-split applies here (engine layer splits; no shell metacharacters). A formatter failure is recorded, not gated — it surfaces at the final whole-tree check.
          10.2.2.1.1.1. [act] Run the formatter command
            - ← format_command
            + → fmt1_rc, fmt1_note
            > Deterministic formatter invocation under a five-minute cap; streams merge.
            > ```hop_python
            > argv = split(format_command, " ")
            > r = subprocess.run(argv, cwd: ".", timeout: 300)
            > fmt1_rc = r.returncode
            > fmt1_note = "formatter exited " + str(fmt1_rc)
            > ```
          10.2.2.1.1.2. [check final] Gate the formatter exit code
            - ← fmt1_rc
            + → ok % bool  # true when the formatter exited zero
            + → note % text  # failure explanation; non-zero is recorded, not fatal
            > Mechanical verdict on the formatter exit code. A non-zero formatter exit is recorded and left to surface at the whole-tree check (registered ruling: the source treats formatting as cleanup, not a gate).
            > ```hop_python
            > ok = fmt1_rc == 0
            > note = "" if ok else "formatter exited " + str(fmt1_rc) + " (surfacing at the whole-tree check)"
            > ```
          10.2.2.1.1.3. [on fail] Record the formatter kill
            10.2.2.1.1.3.1. [act] Refill the formatter narrative conditionally
              - ← fmt1_rc
              + → fmt1_note
              > Conditional narrative distinguishing a recorded non-zero exit from a cap kill, so the catch cannot overwrite a real exit code's story.
              > ```hop_python
              > fmt1_note = ("formatter exited " + str(fmt1_rc)) if fmt1_rc != -1 else "formatter run killed or crashed before returning an exit code"
              > ```
      10.2.2.2. [case(format_present == false)] Record the formatter skip
        + → fmt1_rc, fmt1_note
        10.2.2.2.1. [act] Record the skip
          + → fmt1_rc, fmt1_note
          > Deterministic skip record; the sentinel exit code is reaffirmed for the formatter run that never happened.
          > ```hop_python
          > fmt1_rc = -1
          > fmt1_note = "formatter skipped: no formatter command derived (caller formats itself)"
          > ```
11. [branch] Resolve the manual-phase scope
  - ← has_target_dirs, script_verdict, dry_run_active
  + → manual_scope % line  # directories or file path the manual phase strips; empty means no manual phase
  + → do_manual % bool  # true when a manual-phase scope exists
  > Resolve the manual-phase scope: under the dry-run degradation the enumeration applied no deletions, so there is nothing to strip and the deferred scope question never fires — skip without asking; otherwise carry the supplied target scope when it exists — a user-explicit scope stands even when the script path failed hard, since the source's manual workflow exists standalone — otherwise defer the scope question to the human exactly here, after the script path and postprocess per the source's conditional-ask rule, with the script's per-file outcome tally as context; an empty answer skips the manual phase. The one remaining combination that skips without asking is a hard script failure with no supplied scope: the source directs fixing the missing simplification environment rather than substituting manual stripping for the failed script path.
  11.1. [case(dry_run_active)] Skip the scope question for the enumeration
    + → manual_scope, do_manual
    11.1.1. [act] Record the skip
      + → manual_scope, do_manual
      > Deterministic skip record: the dry-run enumeration applied no deletions, so the manual phase has nothing to do and its deferred scope question never fires. The safe defaults stand reaffirmed on this path so the branch interface is produced on every route — the ask gate below is never reached under the degradation.
      > ```hop_python
      > manual_scope = ""
      > do_manual = false
      > ```
  11.2. [case(has_target_dirs)] Carry the supplied scope
    + → manual_scope, do_manual
    11.2.1. [act] Carry the supplied scope through
      - ← target_dirs
      + → manual_scope, do_manual
      > Deterministic carry of the supplied scope.
      > ```hop_python
      > manual_scope = target_dirs
      > do_manual = true
      > ```
  11.3. [case(script_verdict == "failed")] Record the no-manual-fallback skip
    + → manual_scope, do_manual
    11.3.1. [act] Skip the manual phase after a hard script failure
      + → manual_scope, do_manual
      > Deterministic skip record; the safe defaults stand reaffirmed for this path so the branch interface is complete on every route. The source's direction when the simplification environment is broken is to repair it, not to substitute manual stripping for the failed script path.
      > ```hop_python
      > manual_scope = ""
      > do_manual = false
      > ```
  11.4. [case(else)] Ask whether to strip beyond the changed files
    + → manual_scope, do_manual
    11.4.1. [ask present_inputs=script_tally] Supply the broader-stripping scope
      - ← script_tally
      + → scope_answer % line  # user-supplied directories or file path; empty skips the manual phase
      > The script path finished without a hard failure and without an explicit scope, and the source defers this question to exactly this point. Ask whether to strip beyond the changed files — supply directories or a single file path; an empty answer skips the manual phase entirely. The script's per-file outcome tally is shown as context.
    11.4.2. [act] Adopt the asked scope
      - ← scope_answer
      + → manual_scope, do_manual
      > Deterministic adoption: the asked scope, or none when the answer was empty.
      > ```hop_python
      > manual_scope = scope_answer
      > do_manual = len(scope_answer) > 0
      > ```
12. [branch] Route the manual stripping phase
  - ← do_manual
  + → manual_phase_note, files_processed, edits_made, manual_tally, manual_edits, manual_files, fmt2_rc, fmt2_note, manual_file_results
  > Route the manual phase: when a scope exists, enumerate its files and strip each aggressively under the nine patterns with per-file scoped checks; when none, record the skip. The phase runs at most once.
  12.1. [case(do_manual) retry=0] Strip the scoped files
    + → manual_phase_note, files_processed, edits_made, manual_tally, manual_edits, manual_files, fmt2_rc, fmt2_note, manual_file_results
    > Scoped manual stripping — catch-hosting case marked single-attempt so a caught failure lands in the tail handler immediately (the engine default would rerun the whole phase). One pass per file; the nine patterns with their priority order and cautions live in the knowledge document.
    > [[kverus-strip-knowledge#Deletion patterns]]
    12.1.1. [act free] Enumerate the scoped Rust files
      - ← manual_scope
      + → manual_file_list % [line]  # workspace-relative paths of the in-scope Rust files, or the single file
      > Enumerate the in-scope Rust files recursively (a single file when the scope names one). The enumeration rides the host execution channel inside this cognitive step.
    12.1.2. [act] Count the enumerated files
      - ← manual_file_list
      + → manual_files
      > Mechanical count of the enumerated files.
      > ```hop_python
      > manual_files = len(manual_file_list)
      > ```
    12.1.3. [loop for-each target_file in manual_file_list, collect file_result into manual_file_results] Strip each scoped file under the nine patterns
      + → manual_file_results % [line]  # collect 列表（失败单元不贡献元素；loop 失败时部分收集不保证写回）
      > Strip each scoped file under the nine patterns with per-file scoped checks; a file whose module check stays red after its restore rounds does not contribute an outcome element. The collected list is written back only when the loop closes — an aborted loop leaves it unwritten, which the tail catch must not read.
      12.1.3.1. [subtask retry=3] Strip one file
        + → file_result % line  # collect 单项端： this file's outcome narrative
        > Strip one file: aggressive deletion pass, derive the module path, scoped module check, record the outcome, gate on the scoped check. Restore-minimal rounds run on retry — the deletion pass reads the prior round's scoped-check failure and restores only the specific deletions that provided the missing fact. Three tolerated failures per file.
        > [[kverus-strip-knowledge#Deletion patterns]]
        12.1.3.1.1. [act free] Run the deletion pass for this file
          - ← target_file, has_function, function, module_report
          > Aggressive deletion pass over the single file: the nine patterns in priority order, Pattern 1 first; hard constraints A through E in force; the name filter restricts processing when supplied. First round deletes aggressively; on retry rounds restore minimal specific deletions instead (reverse order, most recent first, when unsure), reading the prior round's scoped-check failure narrative, and never add new proof code. Executor-side edits ride the host execution channel.
          > [[kverus-strip-knowledge#Deletion patterns]]
          > [[kverus-strip-knowledge#Hard constraints]]
        12.1.3.1.2. [reason] Derive the module path for the scoped check
          - ← target_file
          + → module_path % line  # module path for src/foo/bar.rs style files; the crate name for lib.rs
          > Derive the module path: src/foo/bar.rs maps to foo::bar; src/lib.rs maps to the crate name derived from the workspace manifest; the crate's module structure decides.
          > [[kverus-strip-knowledge#Module path mapping]]
        12.1.3.1.3. [act] Run the scoped module check
          - ← effective_verify, module_path
          + → module_rc % int  # exit code of the scoped module check
          + → module_report % line  # merged output of the scoped module check (reassigned each round)
          > Scoped check: the full verification command plus the module-scoped trial flag for this file's module. Whitespace-split at this layer; streams merge; nine-minute cap.
          > ```hop_python
          > argv = split(effective_verify + " -- --verify-only-module " + module_path, " ")
          > r = subprocess.run(argv, cwd: ".", timeout: 900)
          > module_rc = r.returncode
          > module_report = r.stdout + r.stderr
          > ```
        12.1.3.1.4. [act free] Record this file's outcome
          - ← target_file, module_rc, module_report
          + → file_result
          > Record this file's outcome: the file, the pass or restore status, the deletions applied and restored, and the scoped-check context. This is the outcome element the loop collects.
        12.1.3.1.5. [check final] Gate the scoped check
          - ← module_rc, target_file
          + → ok % bool  # true when the scoped module check exited green
          + → note % text  # failure explanation naming the file
          > Mechanical verdict on the scoped check. A red check drives the restore-minimal rounds on the unit's retry ladder (registered: the source's per-file restore loop).
          > ```hop_python
          > ok = module_rc == 0
          > note = "" if ok else "scoped module check failed for " + target_file
          > ```
    12.1.4. [act free] Tally the manual phase from the collected outcomes
      - ← manual_file_results
      + → manual_tally, manual_edits
      > Tally the manual phase from the collected per-file outcomes: files touched, deletions applied, deletions restored. Reads the collected list only after the loop completed — on an aborted loop this step never runs and the tail catch handles the path.
    12.1.5. [branch] Format the manually stripped files when a formatter command exists
      - ← format_present
      + → fmt2_rc, fmt2_note
      > Second formatter gate, after the manual phase's own edits — same shape as the first gate, same non-gating ruling.
      12.1.5.1. [case(format_present)] Run the formatter once
        + → fmt2_rc, fmt2_note
        12.1.5.1.1. [subtask retry=0] Format the manually stripped tree
          + → fmt2_rc, fmt2_note
          > Run the derived formatter command over the workspace once and record the exit code with a short outcome narrative. A formatter failure is recorded, not gated.
          12.1.5.1.1.1. [act] Run the formatter command
            - ← format_command
            + → fmt2_rc, fmt2_note
            > Deterministic formatter invocation under a five-minute cap; streams merge.
            > ```hop_python
            > argv = split(format_command, " ")
            > r = subprocess.run(argv, cwd: ".", timeout: 300)
            > fmt2_rc = r.returncode
            > fmt2_note = "formatter exited " + str(fmt2_rc)
            > ```
          12.1.5.1.1.2. [check final] Gate the formatter exit code
            - ← fmt2_rc
            + → ok % bool  # true when the formatter exited zero
            + → note % text  # failure explanation; non-zero is recorded, not fatal
            > Mechanical verdict on the formatter exit code; non-zero surfaces at the whole-tree check.
            > ```hop_python
            > ok = fmt2_rc == 0
            > note = "" if ok else "formatter exited " + str(fmt2_rc) + " (surfacing at the whole-tree check)"
            > ```
          12.1.5.1.1.3. [on fail] Record the formatter kill
            12.1.5.1.1.3.1. [act] Refill the formatter narrative conditionally
              - ← fmt2_rc
              + → fmt2_note
              > Conditional narrative distinguishing a recorded non-zero exit from a cap kill.
              > ```hop_python
              > fmt2_note = ("formatter exited " + str(fmt2_rc)) if fmt2_rc != -1 else "formatter run killed or crashed before returning an exit code"
              > ```
      12.1.5.2. [case(format_present == false)] Record the formatter skip
        + → fmt2_rc, fmt2_note
        12.1.5.2.1. [act] Record the skip
          + → fmt2_rc, fmt2_note
          > Deterministic skip record; the sentinel exit code is reaffirmed for the formatter run that never happened.
          > ```hop_python
          > fmt2_rc = -1
          > fmt2_note = "formatter skipped: no formatter command derived (caller formats itself)"
          > ```
    12.1.6. [act] Fold the manual phase into the run-level tallies
      - ← files_processed, manual_files, edits_made, manual_edits
      + → files_processed, edits_made, manual_phase_note
      > Deterministic fold: add the manual file count to the run-level processed count, OR the deletion flags, and record the phase narrative.
      > ```hop_python
      > files_processed = files_processed + manual_files
      > edits_made = edits_made or manual_edits
      > manual_phase_note = "manual phase: " + str(manual_files) + " file(s) processed"
      > ```
    12.1.7. [on fail] Catch the aborted manual phase
      12.1.7.1. [act free] Diagnose the phase and restore toward green
        - ← manual_scope, snapshot_ref
        + → manual_phase_note
        > Inspect the workspace to locate the in-flight file and any un-restored deletions; restore surgically from the pre-strip snapshot (the in-flight file, or a cross-module minimal set when the failure was cross-module). Then record the phase state honestly — interrupted, partial, what was restored. This handler deliberately does not read the loop's collected list: on an aborted loop the partial collection is not guaranteed to be written back.
      12.1.7.2. [act] Append the interruption marker to the tally
        - ← manual_tally
        + → manual_tally
        > Deterministic marker so the report cannot overstate the phase.
        > ```hop_python
        > manual_tally = (manual_tally + "; manual phase interrupted before completion") if len(manual_tally) > 0 else "manual phase interrupted before completion"
        > ```
  12.2. [case(do_manual == false)] Record the manual-phase skip
    + → manual_phase_note
    12.2.1. [act] Record the skip
      - ← dry_run_active, script_verdict
      + → manual_phase_note
      > Deterministic skip record covering the three no-manual routes: the dry-run enumeration (no deletions to strip), the deferred question answered empty, or a hard script failure removing the manual fallback.
      > ```hop_python
      > manual_phase_note = ("broader manual stripping not run: dry-run enumeration applied no deletions") if dry_run_active else (("broader manual stripping not run: hard script failure removed the manual fallback") if script_verdict == "failed" else "broader manual stripping not run (no target scope)")
      > ```
13. [branch] Run the unified cross-module whole-tree check unless this is a dry-run enumeration
  - ← dry_run_active
  + → final_rc, final_report
  > Route: a dry-run enumeration deleted nothing, so there is no tree state to re-verify — take the skip arm below and reaffirm the sentinels (the branch interface is produced on every route). Otherwise take the unified path below: one whole-tree check across every module the script and manual phase touched — never per-module checks at this point — with the full verification command as supplied. On entry the tree passes through unchanged (the per-file scoped checks already held each file); on retry the restore discipline informs the deletion pass: read the error, restore only the specific deleted code that provided the missing fact, never add new proof code. Three tolerated failures; exhaustion lands in the tail catch, which records the regression narrative and restores toward green from the snapshot.
  > [[kverus-strip-knowledge#Failure recovery]]
  13.1. [case(dry_run_active)] Skip the whole-tree check for the enumeration
    + → final_rc, final_report
    13.1.1. [act] Record the skip
      + → final_rc, final_report
      > Deterministic skip record; the sentinel exit code and empty report stand reaffirmed on this path so the branch interface is produced on every route — the check never ran because the enumeration edited nothing.
      > ```hop_python
      > final_rc = -1
      > final_report = ""
      > ```
  13.2. [case(dry_run_active == false)] Run the unified whole-tree check
    + → final_rc, final_report
    13.2.1. [subtask retry=3] Run the unified cross-module whole-tree check and restore toward green
      + → final_rc, final_report
      > One unified whole-tree check across every module the script and manual phase touched — never per-module checks at this point — with the full verification command as supplied. On entry the tree passes through unchanged (the per-file scoped checks already held each file); on retry the restore discipline informs the deletion pass: read the error, restore only the specific deleted code that provided the missing fact, never add new proof code. Three tolerated failures; exhaustion lands in the tail catch, which records the regression narrative and restores toward green from the snapshot.
      13.2.1.1. [act free] Prepare the restore discipline for this check
        - ← script_tally, manual_tally, snapshot_ref
        > First entry is a pass-through (no restore yet — the tree stands as the phases left it). On retry rounds, read the tallies of what was removed and where, and prepare the minimal specific restores the failure will name; never add new proof code.
      13.2.1.2. [act] Run the full verification command
        - ← effective_verify
        + → final_rc, final_report
        > The command string is whitespace-split at this layer; streams merge because diagnostics typically land on stderr; nine-minute cap.
        > ```hop_python
        > argv = split(effective_verify, " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > final_rc = r.returncode
        > final_report = r.stdout + r.stderr
        > ```
      13.2.1.3. [check final] Gate the whole-tree check
        - ← final_rc, final_report
        + → ok % bool  # true when the whole-tree check exited green
        + → note % text  # failure explanation naming the check exit code
        > Mechanical verdict on the unified check. A red check drives the restore discipline on the subtask's retry ladder.
        > ```hop_python
        > ok = final_rc == 0
        > note = "" if ok else "whole-tree check failed (exit code " + str(final_rc) + "): " + final_report
        > ```
      13.2.1.4. [on fail] Record the exhausted whole-tree check
        13.2.1.4.1. [act free] Diagnose the cross-module regression and restore toward green
          - ← final_report, snapshot_ref, script_tally, manual_tally
          + → wholecheck_failure_note
          > The unified check stayed red after its restore rounds. Read the whole-tree check output, restore surgically from the pre-strip snapshot toward green (most recent first when unsure), and record the cross-module regression narrative honestly: what was restored, what could not be, and the final state of the tree.
14. [act] Recompute the green verdict from the whole-tree check
  - ← final_rc
  + → final_green
  > Deterministic recompute from the exit code, so every downstream consumer reads a verdict consistent with the last check (the preset stands when the check never ran; the -1 sentinel of the dry-run enumeration keeps the preset verdict standing instead of flipping it red).
  > ```hop_python
  > final_green = true if final_rc == -1 else (final_rc == 0)
  > ```
15. [act] Decide whether the closing measurement is needed
  - ← edits_made, final_green
  + → measure_needed % bool  # true when deletions were made and the tree is green
  > The guard measures only when deletions were made and the tree is green — the source's skip-both-measurements-when-no-changes rule, extended to a red tree (measuring a red close is meaningless).
  > ```hop_python
  > measure_needed = edits_made and final_green
  > ```
16. [branch] Closing measurement and whole-run guard
  - ← measure_needed
  + → post_rlimit, guard_resolved, guard_note, measurement_valid
  > Route: when deletions were made and the tree is green, take the closing whole-run rlimit measurement — identical command and scope to the baseline, one pair wrapping the entire session — and exercise the guard; otherwise skip both per the source's no-change rule.
  16.1. [case(measure_needed) retry=0] Measure and guard
    + → post_rlimit, guard_resolved, guard_note, measurement_valid
    > Catch-hosting case marked single-attempt: exhaustion of the closing measurement routes straight to the tail catch below instead of rerunning the measurement.
    16.1.1. [subtask retry=2] Take the closing whole-run measurement
      + → post_rlimit, closing_rc, closing_report
      > Measure the whole-run rlimit after all stripping with the full verification command and `--time` appended — the same command and scope as the baseline pair. Force a real measurement when the replay is a cached no-op, then extract the aggregate count. Two tolerated failures.
      16.1.1.1. [act] Run the full command with the time flag appended
        - ← effective_verify
        + → closing_rc, closing_report
        > Same command shape as the baseline run: whitespace-split, `--time` appended for rlimit accounting, streams merged, nine-minute cap.
        > ```hop_python
        > argv = split(effective_verify + " --time", " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > closing_rc = r.returncode
        > closing_report = r.stdout + r.stderr
        > ```
      16.1.1.2. [act free] Force a real run and extract the count
        - ← closing_report, effective_verify
        + → post_rlimit
        > Read the captured output for the aggregate stats line — a cached no-op replay prints none; force a real run by appending a trailing newline to an in-scope file before the command and removing it after (trailing whitespace encodes nothing), then extract the rlimit count. Refill with -1 when no count can be extracted. The probe rides the host execution channel inside this cognitive step.
      16.1.1.3. [check final] Gate the closing measurement
        - ← closing_rc, post_rlimit
        + → ok % bool  # true when the measurement run exited green and a positive count was extracted
        + → note % text  # failure explanation naming the closing measurement
        > Mechanical verdict on the measurement pair.
        > ```hop_python
        > ok = closing_rc == 0 and post_rlimit > 0
        > note = "" if ok else "closing measurement unusable (exit code " + str(closing_rc) + " or no rlimit count extracted)"
        > ```
    16.1.2. [act] Flag whether the measurement is usable
      - ← post_rlimit
      + → measurement_valid
      > Deterministic usability flag from the extracted count.
      > ```hop_python
      > measurement_valid = post_rlimit > 0
      > ```
    16.1.3. [act] Derive the guard verdict
      - ← pre_rlimit, post_rlimit
      + → rlimit_growth % bool  # true when the closing count exceeds the baseline count
      + → guard_state % enum(post_lte_pre, growth)  # post_lte_pre: closing count at or below baseline; growth: it exceeds
      > Deterministic comparison of the two whole-run counts. Equal or lower is the healthy outcome of stripping; only growth triggers the recovery protocol.
      > ```hop_python
      > rlimit_growth = post_rlimit > pre_rlimit
      > guard_state = "growth" if rlimit_growth else "post_lte_pre"
      > ```
    16.1.4. [branch] Route the guard on the verdict
      - ← guard_state
      + → guard_resolved, guard_note
      > Route: healthy counts report and stop; growth enters the bounded restore protocol.
      16.1.4.1. [case(guard_state == "post_lte_pre")] Record the healthy guard
        + → guard_resolved, guard_note
        16.1.4.1.1. [act] Record the healthy outcome
          - ← pre_rlimit, post_rlimit
          + → guard_resolved, guard_note
          > Deterministic healthy record; a decrease is the normal outcome of stripping.
          > ```hop_python
          > guard_resolved = true
          > guard_note = "guard healthy: rlimit pre " + str(pre_rlimit) + " post " + str(post_rlimit) + " (a decrease is the normal outcome)"
          > ```
      16.1.4.2. [case(guard_state == "growth") retry=0] Run the bounded restore protocol
        + → guard_resolved, guard_note
        > Catch-hosting case marked single-attempt: exhaustion of the restore protocol routes straight to the tail catch below.
        16.1.4.2.1. [subtask retry=10] Restore most-recent-first until the guard is healthy
          + → post_rlimit, attribution_note, recheck_rc
          > Bounded restore protocol: attribute the growth via scoped probes, restore the most recent unrestored deletion, re-check with the full command, re-measure. Up to ten tolerated failures (eleven cycles including the first entry); the pre-strip snapshot guides surgical re-insertion. When the bound exhausts with growth unresolved, the tail catch records it honestly with follow-up levers.
          > [[kverus-strip-knowledge#Whole-run rlimit guard]]
          16.1.4.2.1.1. [act free] Attribute the growth via scoped probes
            - ← closing_report, recheck_report, attribution_note
            + → attribution_note
            > Attribute the rlimit growth before restoring anything: scoped probes (module scope first, then per-name scope, each with `--time`) over the error spans of the closing measurement on the first round and of the re-measurement on later rounds; reuse the attribution already recorded on retry rounds instead of re-probing from scratch. The probes ride the host execution channel inside this cognitive step.
          16.1.4.2.1.2. [act free] Restore the most recent unrestored deletion
            - ← snapshot_ref, script_tally, manual_tally
            > Snapshot-guided surgical re-insertion of the most recent unrestored deletion — the tallies name what was removed and where. Executor-side copy-back rides the host execution channel.
          16.1.4.2.1.3. [act] Re-check the tree with the full command
            - ← effective_verify
            + → recheck_rc
            > Same command shape as the baseline run — identical command and scope is the guard's comparison rule. Nine-minute cap.
            > ```hop_python
            > argv = split(effective_verify, " ")
            > r = subprocess.run(argv, cwd: ".", timeout: 900)
            > recheck_rc = r.returncode
            > ```
          16.1.4.2.1.4. [act free] Force a real re-measurement and extract the count
            - ← effective_verify
            + → post_rlimit
            > The same force-real discipline as the closing measurement: trailing-newline trick when the replay is a cached no-op, then extract the aggregate rlimit count; -1 when unextractable. The probe rides the host execution channel.
          16.1.4.2.1.5. [check final] Gate the restore round
            - ← recheck_rc, post_rlimit, pre_rlimit
            + → ok % bool  # true when the tree is green again and the count no longer exceeds the baseline
            + → note % text  # failure explanation with both counts
            > Mechanical verdict: the tree is green again and the re-measured count no longer exceeds the baseline. A red tree or persisting growth drives the next restore round.
            > ```hop_python
            > ok = recheck_rc == 0 and post_rlimit <= pre_rlimit
            > note = "" if ok else "guard round incomplete: exit code " + str(recheck_rc) + ", rlimit post " + str(post_rlimit) + " vs pre " + str(pre_rlimit)
            > ```
        16.1.4.2.2. [act] Mark the guard resolved
          + → guard_resolved
          > Deterministic resolution flag after a healthy restore round.
          > ```hop_python
          > guard_resolved = true
          > ```
        16.1.4.2.3. [reason] Compose the resolution narrative
          - ← attribution_note, pre_rlimit, post_rlimit, recheck_rc
          + → guard_note
          > Compose the growth resolution: rounds applied, the attributed functions, both counts, and the final exit code. Reference the attribution narrative the restore protocol recorded.
        16.1.4.2.4. [on fail] Record the unresolved growth honestly
          16.1.4.2.4.1. [act] Record the unresolved guard state
            - ← recheck_rc, pre_rlimit, post_rlimit
            + → guard_resolved, guard_note
            > Deterministic unresolved record: distinguish a red tree after restores from a still-green tree whose growth the bound could not bring down.
            > ```hop_python
            > guard_resolved = false
            > guard_note = ("verify red after restores (exit code " + str(recheck_rc) + "); growth remains") if recheck_rc != 0 else ("rlimit growth unresolved: pre " + str(pre_rlimit) + " post " + str(post_rlimit))
            > ```
          16.1.4.2.4.2. [act free] Compose the follow-up levers
            - ← attribution_note, guard_note
            + → growth_levers
            > Compose the follow-up levers from the attribution: error-span-guided re-add via the profile flag, relaxing the strip for the attributed routine, and the assurance that the tree is left verified green.
          16.1.4.2.4.3. [act] Append the levers to the guard narrative
            - ← guard_note, growth_levers
            + → guard_note
            > Deterministic append so the report carries both the unresolved state and the levers.
            > ```hop_python
            > guard_note = guard_note + growth_levers
            > ```
      16.1.5. [on fail] Record the unusable closing measurement
        16.1.5.1. [act] Mark the measurement unusable
          - ← closing_rc
          + → post_rlimit, measurement_valid, guard_resolved, guard_note
          > Deterministic catch: the closing measurement subtask exhausted its retries (run killed by the cap or count unextractable). The guard is not exercised; the report says so instead of guessing a delta.
          > ```hop_python
          > post_rlimit = -1
          > measurement_valid = false
          > guard_resolved = false
          > guard_note = "closing measurement unusable (exit code " + str(closing_rc) + "); rlimit delta not taken"
          > ```
  16.2. [case(measure_needed == false)] Skip the measurement and guard
    + → post_rlimit, guard_resolved, guard_note, measurement_valid
    16.2.1. [act] Record the skip
      + → post_rlimit, guard_resolved, guard_note, measurement_valid
      > Deterministic skip record per the source's no-change rule: no deletions were made or the tree is not green, so no closing measurement is taken and the guard is not exercised.
      > ```hop_python
      > post_rlimit = -1
      > guard_resolved = true
      > measurement_valid = true
      > guard_note = "no changes — closing measurement skipped per the source's no-change rule; guard not exercised"
      > ```
17. [act] Compose the strip outcome
  - ← script_verdict, measurement_valid, final_green, recheck_rc
  + → strip_outcome % enum(completed, script_failed, verify_failed, measurement_failed)  # precedence: script_failed over measurement_failed over verify_failed over completed
  > Deterministic precedence: a hard script failure outranks an unusable closing measurement, which outranks a red tree, else completed. The green verdict refreshes from the guard protocol when that protocol ran — a restore round's full-command recheck exit code is the tree's latest word, and the -1 sentinel (guard skipped, healthy without restores, or measurement unusable) leaves the whole-tree verdict standing.
  > ```hop_python
  > tree_green = final_green if recheck_rc == -1 else (recheck_rc == 0)
  > strip_outcome = "script_failed" if script_verdict == "failed" else ("measurement_failed" if measurement_valid == false else ("verify_failed" if tree_green == false else "completed"))
  > ```
18. [reason] Compose the five-item strip report
  - ← files_processed, edits_made, script_tally, manual_tally, script_rc, script_verdict, script_report, script_failure_note, postprocess_note, fmt1_rc, fmt1_note, fmt2_rc, fmt2_note, manual_phase_note, final_rc, final_green, wholecheck_failure_note, pre_rlimit, post_rlimit, guard_resolved, guard_note, measurement_valid, strip_outcome, dry_run_note
  + → strip_report % markdown  # the five labeled items, labels verbatim from the source Output section
  > Compose the report with the five required items, labels verbatim from the source: "Number of files processed", "Number of deletions made (total lines removed)", "Number of deletions that had to be restored", "Final verification result (pass/fail)", "Whole-run rlimit, pre vs post (and the delta; plus any guard restores if the total grew)". Draw the counts from the script summary anchors and the manual tally (approximation registered); quote the script outcome legend and the failure narratives when they exist; carry the guard narrative including both counts, the delta, and any growth-protocol restores with their attribution; state plainly what failed, where, and what stands when a path exhausted its fallbacks; keep the no-changes and measurement-skipped cases honest; carry the dry-run disclosure when the degradation fired (enumeration only — no deletions, no baseline or closing measurement, no whole-tree check). Never fabricate a count the run did not produce.
  > [[kverus-strip-knowledge#Report requirements]]
19. [act] Soft-gate the five report labels
  - ← strip_report
  + → report_labels_ok % bool  # true when all five required labels appear in the report
  + → strip_report
  > Soft label gate: check that the composed report carries all five required labels; when one is missing, append an explicit defect admission to the report instead of failing the run — the report still delivers, and the admission says what is wrong with it.
  > ```hop_python
  > has_files_label = len(split(strip_report, "files processed")) > 1
  > has_deletions_label = len(split(strip_report, "deletions made")) > 1
  > has_restored_label = len(split(strip_report, "had to be restored")) > 1
  > has_result_label = len(split(strip_report, "verification result")) > 1
  > has_rlimit_label = len(split(strip_report, "rlimit")) > 1
  > report_labels_ok = has_files_label and has_deletions_label and has_restored_label and has_result_label and has_rlimit_label
  > strip_report = strip_report if report_labels_ok else strip_report + "\nlabel defect: one or more of the five required report labels is missing"
  > ```
20. [exit] Deliver the strip outcome
  + → strip_report, strip_outcome, script_rc, pre_rlimit, post_rlimit
  > The five declared outputs. The report carries the five labeled items; the outcome encodes the worst family that fired; the script exit code, the baseline count, and the closing count let the caller audit the guard.
