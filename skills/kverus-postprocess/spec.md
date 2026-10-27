# Spec: Postprocess a KVerus proof change — cache-only dynamic-rule checker, delegated simplification, and always-run closing duties
Id: kverus-postprocess
Goal: Run the postprocess bookends over a KVerus proof change — a cache-only dynamic-rule checker pass (bounded parallel refresh delegation when the cache verdict asks, never blocking the main flow), fix of every checker ERROR and review of every WARN, verification, delegation of assert simplification to the strip spec (enumeration-only mode when no verification command exists), re-verification, formatting, and then the closing duties that always run: a final cache-only checker pass, the git whitespace check, and the tree status — composing the five-element report and the honest worst-family outcome.

Constraints:
- Compact translation of the kverus-postprocess skill; this spec owns the routing, the phase cascade, the parallel refresh/checker topology, the completion gates, and the outcome precedence, while the severity catalogue, the checker finding catalogue, the dynamic-rule trust criteria and refresh policy, the full script CLI surface, the env-var fallbacks, the wrapper env-to-flag mapping, and the L1 self-bootstrap note live in the companion knowledge document [[kverus-postprocess-knowledge]] — the nine static seed rules and the automation boundary are read from [[kverus-postprocess-knowledge#Static seed rules]] and [[kverus-postprocess-knowledge#Automation boundary]] before the fix phase edits anything.
- Global Verus guide rules carried verbatim from the kverus-common skill; they govern every edit the fix phase and the delegated simplification make:
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
- Global rule 13 — Use `returns expr` for a contract that fixes the exact return value, and `ensures` for other result and state properties; omit unused named return binders and unit return declarations such as `-> (r: ())`. Keep required casts in the `returns` expression and justify that the value fits.
- Global rule 14 — In ghost code, drop `as int` casts that Verus's auto-coercion makes redundant, keeping only the genuinely required ones. Let `E0308` identify missing casts rather than casting defensively.
- Compatibility (source header): the verification command is optional; when it is unavailable the simplification delegate runs in enumeration mode and the verification gates are skipped with records.
- L2 ruling: the source skill's quick_validate.py quick-path content is deliberately cut from this translation; nothing in this spec references it.
- Invocation form (source): `$kverus-postprocess base="<ref>" target-path="<paths>" verify-command="<cmd> format-command="<cmd>"`; the hyphenated argument-hint names map to underscore-joined spec inputs (target-path to target_paths, verify-command to verify_command, format-command to format_command, rule-repo to rule_repo, blocked-path to blocked_paths, generated-path to generated_paths). All nine inputs are optional; the script's own defaults apply to every empty one.
- Topology ruling (refresh and initial check fanned out): the bounded dynamic-rule refresh and the initial cache-only checker pass run as sibling parallel members inside one container that is the barrier and harvest point (tutorial sibling-parallel form). Each member carries its own in-member completion gate and on-fail absorption, so both members always COMPLETE — the engine invariant that a failed parallel member container does not promote its declared outputs makes this mandatory, not optional. The two members write disjoint variable sets (the refresh pair and the checker pair), satisfying the parallel commitment. Standalone mode runs the members truly concurrently; reuse mode runs them sequentially with identical results — the spec text is identical either way.
- Refresh policy rulings carried from the source: exactly one bounded `--refresh-only` delegation when the cache verdict asks (stale or missing, with a repository configured); rc 1 with a summary line is the graceful GitHub-fallback path (old cache preserved, static seeds still apply) and counts as completed; a crash (no summary line) is absorbed to the -1 sentinel; no retry, no rate-limit wait, no blocking of proof work on refresh; when no repository is configured the refresh machinery is idle and the cache verdict reports unconfigured.
- Checker rc discrimination: exit 0 is clean; exit 1 with a findings summary is the normal findings path (ERROR count drives the fix phase; WARNs pass); exit -1 or a missing summary line is a crash, absorbed to the sentinel, with the fix phase recording evidence only and making no edits — the final checker pass judges the tree (registered interpretation: the source is silent on a crashed checker).
- Phase-cascade honest-stop form: the engine has no goto, so each phase branch carries its runnable case and its skip-record case, and the terminal outcome composes by precedence — simplification_failed (delegated and the callee outcome is not completed) over verify_failed (the verification or re-verification phase red or killed) over format_failed over checker_failed (the final checker found errors or crashed, or the whitespace check is not clean) over completed. An initial-checker red is a normal fix trigger, never terminal. Closing duties (final checker, whitespace check, status capture) ALWAYS run after upstream failures — registered deviation from the source wrapper, whose set -eu dies on a red verification or format command; the spec takes report-duty priority, and the wrapper's exit-code precedence maps to the outcome enum per the knowledge document.
- Verify-empty ruling: an empty verification command does NOT ask — the source skill has no ask for it. The verification and re-verification phases skip with records, and the strip delegation is relayed into enumeration mode via the dry_run input, exactly the source wrapper's --dry-run degradation.
- Wrapper bypass ruling: this spec drives the bundled python CLI directly; the source's run_postprocess.sh (and its Windows .ps1 twin, retained as a human asset) is not executed. The wrapper's env-var-to-flag mapping, its conditional simplify scope, and its exit precedence are disclosed in the knowledge document for operators who invoke the wrapper by hand.
- Constant-surface disclosure: this spec passes only the mapped surface — --base, --target-path, --rule-repo, --blocked-path, --generated-path, --no-refresh-rules, --cache-status, --refresh-only, and the strip callee's own flags. Never passed here: --refresh-rules (synchronous full refresh — the source forbids it by default), --include-skills, --include-commit-context, --recent-prs, --github-timeout, --rule-cache-ttl-hours, --print-rules. The full CLI surface, the env-var fallbacks, and the cache file format live in the knowledge document.
- Caller-relay inputs to the strip callee: modified_only and dry_run ride as line values ("true" or "false") because cross-call boolean transfer is unverified; the callee coerces them with `x == "true"`, which reads an empty relay as false. The modified relay carries this spec's default changed-lines scope unless the simplification-scope input is "all"; the dry relay fires when no verification command exists.
- L6 dynamic-command discipline: user-supplied command strings (the verification command and the format command) are whitespace-split at this layer, no shell metacharacters; the first word of every executed command must be registered in the engine's command whitelist. This spec declares python3 and git; the delegated strip callee declares its own command surface (python3, verus, cargo, rustfmt) and owns its script asset and environment bootstrap. A differently-prefixed verification or formatter wrapper is a deployment prerequisite (the project's hopjit.yaml command registry), not a spec defect.
- Parallel approximation registered: the container barrier approximates the source's "continue the main workflow immediately instead of waiting for GitHub" — the refresh member's tail is bounded (two GitHub GETs at the script's four-second timeout plus its 300-second refresh lock), so the barrier waits at most that tail; the initial checker member consumes the latest available cache either way, matching the source's cache-or-static ruling in both execution modes.
- Provisional values (translation ledger): engine subprocess caps — cache-status and checker-shaped runs 300 seconds, the bounded refresh 300 seconds, verification-shaped runs 900 seconds, formatter 300 seconds, git closing duties 300 seconds. Retry budgets — verify, re-verify, format, and final checker 3 (engine retry=N tolerates N failures, so up to N+1 executions); the refresh arm, the initial checker, and both git duties are single-attempt retry=0 with absorption; case heads hosting catches carry explicit retry=0.
- No commit step (L24 family): the bundled script writes only its own rule cache under its scripts directory; this spec takes no commit step and no delivery verb exists in the source; the exit carries the report and the outcome.
- Call delegation ruling: the step-9 call resolves statically to the same-directory kverus-strip spec (the deployment carries it as a sister spec in this spec's directory); the callee's own declaration covers its script asset, its environment bootstrap prerequisite, and its approved commands. Output lifting uses the standard form; the callee's script exit code and rlimit pair are lifted under caller-side names for the report and the exit.
- Automation boundary carried from the source: the checker and refresh scripts never remove comments, rename functions, or rewrite specifications; simplification removes proof assertions only when verification succeeds; without a verification command the simplification runs in enumeration mode. The policy detail and the nine static seed rules live in the knowledge document.
- Shared-reference discipline: when the fix phase or the report must reason about proof constructs (proof blocks, ghost/tracked values, spec/proof functions, external bodies), read the relevant reference under `../kverus-common/references/` first — for this spec's decision surface, `exec-code-preservation.md`, `ghost-tracked.md`, `lemma-shape.md`, `verus-syntax-quickref.md`, and `unsupported-features/index.md` under the sibling kverus-common references tree.

Inputs:
- base % line  # optional; git base ref for changed-file discovery and diff scoping (e.g. origin/main); empty lets the script default to origin/main
- target_paths % line  # optional; path prefixes restricting the checker's finding scope; empty means all changed paths
- verify_command % line  # optional; full whitespace-split verification command string (no shell metacharacters); empty skips the verification gates and relays the strip delegation into enumeration mode — the source skill never asks for it
- format_command % line  # optional; formatter command string; empty skips the format phase
- rule_repo % line  # optional; trusted dynamic-rule source repository; empty disables the refresh machinery entirely (the cache verdict reports unconfigured and only the static seed rules apply)
- blocked_paths % line  # optional; comma-separated path prefixes whose changes are flagged ERROR as outside the verification scope
- generated_paths % line  # optional; comma-separated path prefixes whose changes are flagged WARN as generated files
- simplify_scope % line  # optional; "all" relays whole-file stripping scope to the delegate, anything else (the default) relays the changed-lines scope
- skip_simplify % line  # optional; "true" skips the simplification delegation entirely

Outputs:
- postprocess_report % markdown  # the five labeled items, labels verbatim from the source Report section
- postprocess_outcome % enum(completed, checker_failed, verify_failed, simplification_failed, format_failed)  # worst-family precedence: simplification_failed over verify_failed over format_failed over checker_failed over completed
- final_checker_rc % int  # exit code of the final cache-only checker pass; -1 when the worker crashed or was killed before printing its findings summary
- strip_report % markdown  # the delegated strip report embedded verbatim; empty when delegation was skipped
- strip_outcome % line  # the delegated strip outcome (completed, script_failed, verify_failed, measurement_failed, or not delegated)
- refresh_rc % int  # bounded refresh pass exit code; 1 with a summary line is the graceful GitHub fallback and counts as completed; -1 when skipped or crashed
- checker_rc % int  # initial cache-only checker pass exit code; -1 when the worker crashed before its findings summary

Config:
  requires_commands: [python3, git]
## 已批准命令
- python3
- git

## Steps
1. [act] Test the invocation inputs, coerce the relays, and pre-provision the failure-hosting verdicts
  - ← base, target_paths, verify_command, format_command, rule_repo, blocked_paths, generated_paths, simplify_scope, skip_simplify
  + → has_base % bool  # true when the baseline-ref input was supplied
  + → has_target_paths % bool  # true when the target-path input was supplied
  + → has_verify % bool  # true when the verification-command input was supplied
  + → has_format % bool  # true when the format-command input was supplied
  + → has_rule_repo % bool  # true when the rule-repository input was supplied
  + → has_blocked % bool  # true when the blocked-path input was supplied
  + → has_generated % bool  # true when the generated-path input was supplied
  + → scope_all % bool  # true when the simplification-scope relay is "all"
  + → skip_simplify_active % bool  # true when the skip-simplification relay is "true"
  + → strip_modified_only % line  # the changed-lines relay passed to the strip callee, "true" unless the scope relay is "all"
  + → strip_dry_run % line  # the enumeration relay passed to the strip callee, "true" when no verification command exists
  + → refresh_rc % int  # -1 preset: refreshed worker killed or crashed before its summary, or the refresh was skipped
  + → refresh_note % line  # empty preset
  + → checker_rc % int  # -1 preset: initial checker worker crashed before its findings summary
  + → checker_report % line  # empty preset
  + → verify_rc % int  # -1 preset: verification run killed or crashed before returning an exit code
  + → verify_report % line  # empty preset
  + → reverify_rc % int  # -1 preset: same residual role for the re-verification phase
  + → reverify_report % line  # empty preset
  + → format_rc % int  # -1 preset: formatter run killed or crashed before returning an exit code
  + → format_report % line  # empty preset
  + → final_checker_rc % int  # -1 preset: final checker worker crashed before its findings summary
  + → final_checker_report % line  # empty preset
  + → git_diff_check_rc % int  # -1 preset: whitespace-check worker killed or crashed
  + → git_diff_check_report % line  # empty preset
  + → git_status_text % line  # empty preset
  > Mechanical presence tests on the nine invocation inputs, coercion of the two callee relays and the scope/skip relays, and pre-provisioning of every failure-hosting verdict with safe sentinels. Engine failure semantics leave prior values intact when a worker is killed by a cap mid-flight, so each later absorber and classifier reads a valid value on every path — timeouts, hard errors, and exhausted retries alike. The relays ride as lines because cross-call boolean transfer is unverified; the callee coerces them itself.
  > ```hop_python
  > has_base = len(base) > 0
  > has_target_paths = len(target_paths) > 0
  > has_verify = len(verify_command) > 0
  > has_format = len(format_command) > 0
  > has_rule_repo = len(rule_repo) > 0
  > has_blocked = len(blocked_paths) > 0
  > has_generated = len(generated_paths) > 0
  > scope_all = simplify_scope == "all"
  > skip_simplify_active = skip_simplify == "true"
  > strip_modified_only = "false" if scope_all else "true"
  > strip_dry_run = "true" if has_verify == false else "false"
  > refresh_rc = -1
  > refresh_note = ""
  > checker_rc = -1
  > checker_report = ""
  > verify_rc = -1
  > verify_report = ""
  > reverify_rc = -1
  > reverify_report = ""
  > format_rc = -1
  > format_report = ""
  > final_checker_rc = -1
  > final_checker_report = ""
  > git_diff_check_rc = -1
  > git_diff_check_report = ""
  > git_status_text = ""
  > ```
2. [act] Compose the cache-only checker argument vector
  - ← has_base, base, has_target_paths, target_paths, has_rule_repo, rule_repo, has_blocked, blocked_paths, has_generated, generated_paths
  + → checker_argv % [line]  # argument vector shared by the initial and final checker passes, cache-only by construction
  > Deterministic assembly of the checker argument vector, reused verbatim by the initial pass and the final closing pass so both are cache-only by construction — the source's no-synchronous-refresh-by-default ruling and its final-check-from-cache-only ruling ride in the one --no-refresh-rules flag. Conditional appends follow the supplied inputs; empty inputs omit their flags and let the script apply its own defaults and env fallbacks. The env-var-to-flag mapping of the source wrapper is disclosed in the knowledge document.
  > ```hop_python
  > checker_argv = ["--no-refresh-rules"]
  > checker_argv = checker_argv + (["--base", base] if has_base else [])
  > checker_argv = checker_argv + (["--target-path", target_paths] if has_target_paths else [])
  > checker_argv = checker_argv + (["--rule-repo", rule_repo] if has_rule_repo else [])
  > checker_argv = checker_argv + (["--blocked-path", blocked_paths] if has_blocked else [])
  > checker_argv = checker_argv + (["--generated-path", generated_paths] if has_generated else [])
  > ```
3. [act] Inspect the rule cache status without any network access
  - ← has_rule_repo, rule_repo
  + → cache_status_raw % line  # the one-line sorted-key JSON the script prints
  + → cache_status % line  # fresh, stale, missing, unconfigured, or unknown when no status token was recognized
  + → needs_refresh % bool  # true when the verdict is stale or missing and a repository is configured
  > Deterministic inspection: the cache-status mode prints one line of sorted-key JSON and touches neither the network nor git. The status token is read with the proven substring-count idiom over the four documented status words; anything unrecognized reads as unknown and never requests a refresh. The refresh need couples the stale-or-missing verdict to a configured repository — an unconfigured repository leaves the refresh machinery idle.
  > ```hop_python
  > argv = ["python3", spec_dir("scripts/kverus_postprocess.py"), "--cache-status"]
  > argv = argv + (["--rule-repo", rule_repo] if has_rule_repo else [])
  > r = subprocess.run(argv, cwd: ".", timeout: 300)
  > cache_status_raw = r.stdout + r.stderr
  > fresh_seen = len(split(cache_status_raw, '"status": "fresh"')) > 1
  > stale_seen = len(split(cache_status_raw, '"status": "stale"')) > 1
  > missing_seen = len(split(cache_status_raw, '"status": "missing"')) > 1
  > unconfigured_seen = len(split(cache_status_raw, '"status": "unconfigured"')) > 1
  > cache_status = "fresh" if fresh_seen else ("stale" if stale_seen else ("missing" if missing_seen else ("unconfigured" if unconfigured_seen else "unknown")))
  > needs_refresh = ((cache_status == "stale") or (cache_status == "missing")) and has_rule_repo
  > ```
4. [subtask] Refresh delegation and the initial cache-only check, fanned out as siblings
  - ← needs_refresh, cache_status, has_rule_repo, rule_repo, checker_argv
  + → refresh_rc, refresh_note, checker_rc, checker_report
  > Barrier and harvest point for the two sibling parallel members (tutorial sibling-parallel form): the refresh member runs the bounded refresh-only pass when the cache verdict asks, and the checker member runs the initial cache-only findings pass on the latest available cache. The members write disjoint variable sets, so the parallel commitment holds. Each member carries its own in-member completion gate and on-fail absorption — the engine invariant that a failed parallel member container does not promote its declared outputs makes this mandatory — so both members always COMPLETE and the barrier always harvests. Standalone mode dispatches the members truly concurrently; reuse mode runs them sequentially with identical results. The barrier approximates the source's continue-immediately ruling: the refresh tail is bounded, and the checker member consumes the latest available cache in either order.
  4.1. [subtask parallel] Refresh member — the bounded dynamic-rule cache pass
    + → refresh_rc, refresh_note
    4.1.1. [branch] Gate the bounded refresh on the cache verdict
      - ← needs_refresh, has_rule_repo, rule_repo, cache_status
      + → refresh_rc, refresh_note
      4.1.1.1. [case(needs_refresh) retry=0] Run the bounded refresh-only pass
        + → refresh_rc, refresh_note
        > Catch-hosting case marked single-attempt: the source's refresh ruling is one bounded pass with no retry, no rate-limit wait, and no blocking of proof work.
        4.1.1.1.1. [subtask retry=0] One bounded synchronous refresh pass
          + → refresh_rc, refresh_note
          > Run the bundled script in refresh-only mode under the engine subprocess cap — the source's bounded delegation form. The script's own guard (its 300-second refresh lock) and its per-request GitHub timeout bound the tail; a failed refresh preserves the old cache and falls back to it gracefully, which the completion gate below reads as completed.
          4.1.1.1.1.1. [act] Run the bounded refresh-only pass
            - ← has_rule_repo, rule_repo
            + → refresh_rc, refresh_note
            > Assemble the refresh-only invocation — the repository flag when configured — run it under the engine subprocess cap, and merge the streams. The script pulls trusted dynamic rules from the configured repository and atomically writes its rule cache; it never edits proof sources.
            > ```hop_python
            > argv = ["python3", spec_dir("scripts/kverus_postprocess.py")]
            > argv = argv + (["--rule-repo", rule_repo] if has_rule_repo else [])
            > argv = argv + ["--refresh-only"]
            > r = subprocess.run(argv, cwd: ".", timeout: 300)
            > refresh_rc = r.returncode
            > refresh_note = r.stdout + r.stderr
            > ```
          4.1.1.1.1.2. [check final] Gate the refresh completion
            - ← refresh_rc, refresh_note
            + → ok % bool  # true when the worker printed its refresh summary line
            + → note % text  # failure explanation naming the refresh completion gate
            > Completion gate, not a green gate: exit 1 with a summary line is the graceful GitHub-fallback path (old cache preserved, static seeds still apply) and completes; only a missing summary line — a kill or a crash before printing — fails the gate.
            > ```hop_python
            > ok = len(split(refresh_note, "Refresh-only summary:")) > 1
            > note = "" if ok else "refresh-only worker produced no summary line (exit code " + str(refresh_rc) + ")"
            > ```
          4.1.1.1.1.3. [on fail] Absorb the crashed refresh worker
            4.1.1.1.1.3.1. [act] Record the crash honestly
              - ← refresh_rc, refresh_note
              + → refresh_rc, refresh_note
              > Absorption: the crash narrative preserves the captured exit code and output as evidence, then reaffirms the sentinel so downstream consumers read a valid value. The source's refresh rulings apply verbatim — no retry, no rate-limit wait, no block on proof work; the old cache stands and the checker member consumed the latest available cache independently.
              > ```hop_python
              > refresh_note = "refresh worker crashed or was killed before its summary line (captured exit code " + str(refresh_rc) + "): " + refresh_note + " — no retry, no rate-limit wait, no block on proof work; the old cache stands"
              > refresh_rc = -1
              > ```
      4.1.1.2. [case(needs_refresh == false)] Record the refresh skip
        + → refresh_rc, refresh_note
        4.1.1.2.1. [act] Record the skip
          - ← has_rule_repo, cache_status
          + → refresh_rc, refresh_note
          > Deterministic skip record covering the no-refresh routes: no repository configured (the machinery is idle and the cache verdict reports unconfigured), a fresh cache, or a verdict that did not request a refresh.
          > ```hop_python
          > refresh_rc = -1
          > refresh_note = ("refresh skipped: no repository configured for dynamic rules" if has_rule_repo == false else ("refresh skipped: cached dynamic rules are fresh" if cache_status == "fresh" else "refresh skipped: the cache verdict did not request a refresh"))
          > ```
    4.2. [subtask parallel] Checker member — the initial cache-only findings pass
      + → checker_rc, checker_report
      4.2.1. [subtask retry=0] Initial checker pass on the latest available cache
        + → checker_rc, checker_report
        > Single attempt by ruling: the initial pass is a read-only findings pass whose crash path is absorbed and judged later by the final checker. The cache-only flag rides inside the shared argument vector from step 2, so this pass consumes the latest available cache — refreshed in parallel by the sibling member, or the old cache, or the static seeds — exactly the source's cache-or-static ruling.
        4.2.1.1. [act] Run the initial checker pass
          - ← checker_argv
          + → checker_rc, checker_report
          > Deterministic invocation of the bundled checker against the shared cache-only argument vector, under the engine subprocess cap, streams merged. The script folds blocked-path, generated-path, untracked, and added-line findings; its own git diff --check failure surfaces as an ERROR finding inside the report.
          > ```hop_python
          > argv = ["python3", spec_dir("scripts/kverus_postprocess.py")] + checker_argv
          > r = subprocess.run(argv, cwd: ".", timeout: 300)
          > checker_rc = r.returncode
          > checker_report = r.stdout + r.stderr
          > ```
        4.2.1.2. [check final] Gate the checker completion
          - ← checker_rc, checker_report
          + → ok % bool  # true when the worker printed its findings summary line
          + → note % text  # failure explanation naming the checker completion gate
          > Completion gate, not a green gate: exit 1 with a summary line is the normal findings path (ERROR count drives the fix phase; WARNs pass), and only a missing summary line — a kill or a crash before printing — fails the gate.
          > ```hop_python
          > ok = len(split(checker_report, "INFO: Summary:")) > 1
          > note = "" if ok else "initial checker worker produced no findings summary (exit code " + str(checker_rc) + ")"
          > ```
        4.2.1.3. [on fail] Absorb the crashed checker worker
          4.2.1.3.1. [act] Record the crash honestly
            - ← checker_rc, checker_report
            + → checker_rc, checker_report
            > Absorption: the crash narrative preserves the captured exit code and output as evidence, then reaffirms the sentinel. The fix phase downstream records evidence only and makes no edits; the final checker pass judges the tree (registered interpretation: the source is silent on a crashed initial checker).
            > ```hop_python
            > checker_report = "initial checker worker crashed or was killed before its findings summary (captured exit code " + str(checker_rc) + "): " + checker_report + " — the fix phase records evidence only and the final checker pass judges the tree"
            > checker_rc = -1
            > ```
5. [act] Classify the initial checker verdict
  - ← checker_rc, checker_report
  + → checker_state % enum(clean, errors_found, crashed)  # clean: exit 0; errors_found: exit 1 with a summary; crashed: sentinel exit or missing summary
  > Deterministic discrimination from the exit code and the summary anchor. A crashing worker is classified, not fatal — the absorbed member always completes, and the crash route is recorded here so the fix phase knows to make no edits.
  > ```hop_python
  > summary_found = len(split(checker_report, "INFO: Summary:")) > 1
  > crashed_flag = (checker_rc == -1) or (summary_found == false)
  > checker_state = "crashed" if crashed_flag else ("errors_found" if checker_rc == 1 else "clean")
  > ```
6. [act free] Fix every checker ERROR and review every WARN
  - ← checker_state, checker_report, cache_status
  + → fix_note % line  # what was fixed, what was reviewed and kept, and what was recorded as evidence on the crash route
  > The fix phase. When the verdict is errors_found, fix every ERROR finding and review every WARN finding unless there is a clear reason to keep it — the finding catalogue and the severity definitions live in the knowledge document, and the nine static seed rules plus any fresh dynamic rules shape the fixes. INFO findings are context only. When the verdict is crashed, make no edits and record the evidence: the crash narrative and the captured partial output, with the final checker pass named as the judge. When the verdict is clean, record that no fixes were needed. The automation boundary applies throughout: this phase edits proof files through the executing agent, and no script ever removes comments, renames functions, or rewrites specifications.
  > [[kverus-postprocess-knowledge#Checker finding catalogue]]
  > [[kverus-postprocess-knowledge#Severity definitions]]
  > [[kverus-postprocess-knowledge#Static seed rules]]
7. [branch] Gate the verification phase
  - ← has_verify, verify_command, verify_rc, verify_report
  + → verify_state, verify_rc, verify_report
  > Route: a supplied verification command runs and is judged; an empty one skips with a record — the source never asks for the command, and the degradation relay to the simplification delegate was already fixed at step 1. The gate inside the run subtask is a completion gate (the run returned an exit code), not a green gate: a red verification is a normal recorded outcome that the phase cascade composes, never an instance termination.
  7.1. [case(has_verify)] Run and judge the verification command
    + → verify_state, verify_rc, verify_report
    7.1.1. [subtask retry=3] Run the verification command
      + → verify_rc, verify_report
      > The full verification command as supplied, whitespace-split at this layer with no shell metacharacters, streams merged because Verus diagnostics typically land on stderr, nine-minute cap. Three tolerated failures; a kill or crash mid-run is absorbed by the tail handler below.
      7.1.1.1. [act] Run the verification command
        - ← verify_command
        + → verify_rc, verify_report
        > Deterministic invocation of the supplied command under the engine subprocess cap.
        > ```hop_python
        > argv = split(verify_command, " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > verify_rc = r.returncode
        > verify_report = r.stdout + r.stderr
        > ```
      7.1.1.2. [check final] Gate the verification run completion
        - ← verify_rc
        + → ok % bool  # true when the run returned an exit code (the preset sentinel means it never did)
        + → note % text  # failure explanation naming the verification completion gate
        > Completion gate: any returned exit code completes the run — green, red, or killed-before-return is distinguished by the sentinel. A red verification is the normal failure signal the phase cascade composes; only the never-returned kill fails this gate.
        > ```hop_python
        > ok = verify_rc != -1
        > note = "" if ok else "verification run was killed or crashed before returning an exit code"
        > ```
      7.1.1.3. [on fail] Absorb the killed verification run
        7.1.1.3.1. [act] Mark the killed run in the captured report
          - ← verify_report
          + → verify_report
          > Absorption: the exit code keeps its preset sentinel (the run never returned one), and the report gains an explicit marker so the report step cannot present a kill as a green or red run. The phase cascade treats the sentinel as not-green.
          > ```hop_python
          > verify_report = verify_report + "\n[postprocess] verification run was killed or crashed before returning an exit code; treated as not green"
          > ```
    7.1.2. [act] Classify the verification verdict
      - ← verify_rc
      + → verify_state % enum(green, red, skipped)
      > Deterministic verdict from the exit code; the sentinel reads as red, honestly naming a killed run as not green.
      > ```hop_python
      > verify_state = "red" if verify_rc != 0 else "green"
      > ```
  7.2. [case(has_verify == false)] Record the verify-empty degradation
    + → verify_state, verify_rc, verify_report
    7.2.1. [act] Record the skip
      + → verify_state, verify_rc, verify_report
      > Deterministic skip record: no verification command was supplied, so the verification and re-verification gates are skipped with records, and the strip delegation already carries the enumeration relay from step 1 — the source wrapper's --dry-run degradation, never an ask.
      > ```hop_python
      > verify_state = "skipped"
      > verify_rc = -1
      > verify_report = "verification gates skipped: no verification command was supplied; the simplification delegate was relayed into enumeration mode"
      > ```
8. [act] Compute the simplification delegation route
  - ← verify_state, skip_simplify_active
  + → simplification_runnable % bool  # true when the cascade reaches the delegation: verification not red and the skip relay unset
  > Deterministic route computation for the phase cascade. The delegation runs when the verification phase is not red (green or skipped both qualify — an empty command degrades to enumeration, it does not block) and the caller did not set the skip relay. An initial-checker red is a fix trigger handled above and never terminates the run, so it does not appear here.
  > ```hop_python
  > simplification_runnable = (verify_state != "red") and (skip_simplify_active == false)
  > ```
9. [branch] Delegate the assert simplification or record the skip
  - ← simplification_runnable, skip_simplify_active, verify_state, verify_command, target_paths, base, strip_modified_only, strip_dry_run
  + → strip_report, strip_outcome, strip_script_rc, pre_rlimit, post_rlimit
  > Route: when the cascade reaches delegation, call the strip spec with the mapped inputs and lift its report, outcome, script exit code, and rlimit pair; otherwise record the skip with its cause. The callee owns its script asset, its environment bootstrap, its whole-run rlimit guard, and its own approved-commands declaration.
  9.1. [case(simplification_runnable)] Delegate to the strip spec
    - ← verify_command, target_paths, base, strip_modified_only, strip_dry_run
    + → strip_report, strip_outcome, strip_script_rc, pre_rlimit, post_rlimit
    9.1.1. [call kverus-strip(verify: verify_command, target_dirs: target_paths, base, modified_only: strip_modified_only, dry_run: strip_dry_run)] Delegate the assert simplification
      + → strip_report, strip_outcome, strip_script_rc: script_rc, pre_rlimit, post_rlimit
      > Static call to the same-directory kverus-strip spec. Input mapping: the verification command, the changed-path scope, and the baseline ref pass through; the scope relay carries the changed-lines default unless the simplification-scope input was "all"; the enumeration relay fires when no verification command exists, which degrades the callee to candidate listing without edits, without its baseline and closing measurements, and without its whole-tree check. Output lifting: the callee's report and outcome arrive under their own names, its script exit code is lifted under a caller-side name to keep the flat namespace unambiguous, and its rlimit pair lifts for the report and the exit.
  9.2. [case(simplification_runnable == false)] Record the delegation skip
    - ← skip_simplify_active, verify_state
    + → strip_report, strip_outcome, strip_script_rc, pre_rlimit, post_rlimit
    9.2.1. [act] Record the skip with its cause
      - ← skip_simplify_active, verify_state
      + → strip_report, strip_outcome, strip_script_rc, pre_rlimit, post_rlimit
      > Deterministic skip record with the two-route cause discrimination (the route computation made the predicate binary): the caller disabled the delegation, or the verification phase failed and the cascade skips no-op simplification. Sentinels reaffirmed for the unlifted callee outputs so the report and the exit read valid values on this route.
      > ```hop_python
      > strip_report = ("assert simplification not delegated: the caller disabled it via the skip input" if skip_simplify_active else "assert simplification not delegated: the verification phase failed and the phase cascade skips no-op simplification")
      > strip_outcome = "not delegated"
      > strip_script_rc = -1
      > pre_rlimit = -1
      > post_rlimit = -1
      > ```

10. [act] Compute the re-verification continuation flag
  - ← simplification_runnable, strip_outcome, has_verify
  + → reverify_needed % bool  # true when delegation completed cleanly and the verification command still exists
  > Deterministic continuation gate for the cascade: the re-verification phase runs when delegation actually happened and completed cleanly, and when a verification command exists to re-run. A skipped delegation, a non-completed delegation, or an empty command each routes to the skip record below with its own cause.
  > ```hop_python
  > reverify_needed = (simplification_runnable == true) and (strip_outcome == "completed") and has_verify
  > ```
11. [branch] Gate the post-simplification re-verification
  - ← reverify_needed, simplification_runnable, strip_outcome, verify_command
  + → reverify_state, reverify_rc, reverify_report
  > Route: the continuation flag runs the verification command again and judges it; otherwise a skip record names the cause (delegation not reached, delegation not completed cleanly, or no command to re-run). The run subtask's gate is a completion gate, mirroring the first verification phase: red is a normal recorded outcome composed by the cascade, never a termination.
  11.1. [case(reverify_needed)] Re-run the verification command
    + → reverify_state, reverify_rc, reverify_report
    11.1.1. [subtask retry=3] Re-run the verification command
      + → reverify_rc, reverify_report
      > Same shape as the first verification phase: full supplied command, whitespace-split, streams merged, nine-minute cap, three tolerated failures. Simplification may have removed proof assertions, so this pass is the first green evidence for the simplified tree.
      11.1.1.1. [act] Re-run the verification command
        - ← verify_command
        + → reverify_rc, reverify_report
        > Deterministic invocation of the supplied command under the engine subprocess cap.
        > ```hop_python
        > argv = split(verify_command, " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > reverify_rc = r.returncode
        > reverify_report = r.stdout + r.stderr
        > ```
      11.1.1.2. [check final] Gate the re-verification run completion
        - ← reverify_rc
        + → ok % bool  # true when the run returned an exit code (the preset sentinel means it never did)
        + → note % text  # failure explanation naming the re-verification completion gate
        > Completion gate: any returned exit code completes the run; only a kill or crash before return fails it.
        > ```hop_python
        > ok = reverify_rc != -1
        > note = "" if ok else "re-verification run was killed or crashed before returning an exit code"
        > ```
      11.1.1.3. [on fail] Absorb the killed re-verification run
        11.1.1.3.1. [act] Mark the killed run in the captured report
          - ← reverify_report
          + → reverify_report
          > Absorption: the sentinel keeps the not-green semantics honest and the report gains an explicit marker so the report step cannot present a kill as a green run.
          > ```hop_python
          > reverify_report = reverify_report + "\n[postprocess] re-verification run was killed or crashed before returning an exit code; treated as not green"
          > ```
    11.1.2. [act] Classify the re-verification verdict
      - ← reverify_rc
      + → reverify_state % enum(green, red, skipped)
      > Deterministic verdict from the exit code; the sentinel reads as red.
      > ```hop_python
      > reverify_state = "red" if reverify_rc != 0 else "green"
      > ```
  11.2. [case(reverify_needed == false)] Record the re-verification skip
    + → reverify_state, reverify_rc, reverify_report
    11.2.1. [act] Record the skip with its cause
      - ← simplification_runnable, strip_outcome
      + → reverify_state, reverify_rc, reverify_report
      > Deterministic skip record with the three-route cause discrimination fixed by the continuation computation: delegation was not reached, delegation did not complete cleanly (its outcome names the cause), or no verification command exists to re-run.
      > ```hop_python
      > reverify_state = "skipped"
      > reverify_rc = -1
      > reverify_report = ("re-verification skipped: simplification was not delegated — nothing was simplified to re-verify" if simplification_runnable == false else ("re-verification skipped: delegation outcome is " + strip_outcome + " — the final checker pass judges the tree" if strip_outcome != "completed" else "re-verification skipped: no verification command was supplied"))
      > ```
12. [branch] Gate the formatter phase
  - ← has_format, format_command
  + → format_state, format_rc, format_report
  > Route: a supplied formatter command runs and is judged; an empty one skips with a record. The formatter is the only non-gating phase — a red or killed formatter is recorded honestly and the closing duties still run, registered as the source-wrapper's hard-death deviation; the report and the outcome precedence carry the red family. The gate inside the run subtask is a completion gate, mirroring the verification phases.
  12.1. [case(has_format)] Run and judge the formatter command
    + → format_state, format_rc, format_report
    12.1.1. [subtask retry=3] Run the formatter command
      + → format_rc, format_report
      > The full formatter command as supplied, whitespace-split at this layer, streams merged, five-minute cap. Formatting is idempotent over already-formatted sources, so the absorbed-first-attempt shape is safe.
      12.1.1.1. [act] Run the formatter command
        - ← format_command
        + → format_rc, format_report
        > Deterministic invocation of the supplied formatter under the engine subprocess cap.
        > ```hop_python
        > argv = split(format_command, " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 300)
        > format_rc = r.returncode
        > format_report = r.stdout + r.stderr
        > ```
      12.1.1.2. [check final] Gate the formatter run completion
        - ← format_rc
        + → ok % bool  # true when the run returned an exit code (the preset sentinel means it never did)
        + → note % text  # failure explanation naming the formatter completion gate
        > Completion gate: any returned exit code completes the run; only a kill or crash before return fails it.
        > ```hop_python
        > ok = format_rc != -1
        > note = "" if ok else "formatter run was killed or crashed before returning an exit code"
        > ```
      12.1.1.3. [on fail] Absorb the killed formatter run
        12.1.1.3.1. [act] Mark the killed run in the captured report
          - ← format_report
          + → format_report
          > Absorption: the sentinel keeps the not-green semantics honest and the report gains an explicit marker. The phase is non-gating, so the cascade proceeds to the closing duties.
          > ```hop_python
          > format_report = format_report + "\n[postprocess] formatter run was killed or crashed before returning an exit code; treated as not green"
          > ```
    12.1.2. [act] Classify the formatter verdict
      - ← format_rc
      + → format_state % enum(green, red, skipped)
      > Deterministic verdict from the exit code; the sentinel reads as red.
      > ```hop_python
      > format_state = "red" if format_rc != 0 else "green"
      > ```
  12.2. [case(has_format == false)] Record the formatter skip
    + → format_state, format_rc, format_report
    12.2.1. [act] Record the skip
      + → format_state, format_rc, format_report
      > Deterministic skip record: no formatter command was supplied, so the format phase is skipped with a record and the closing duties judge the tree as it stands.
      > ```hop_python
      > format_state = "skipped"
      > format_rc = -1
      > format_report = "formatter phase skipped: no format command was supplied"
      > ```
13. [subtask retry=3] Final cache-only checker pass — closing duty, always runs
  - ← checker_argv
  + → final_checker_rc, final_checker_report
  > The source's closing duty: a final check from the cache only, never a synchronous re-refresh — the shared cache-only argument vector from step 2 carries that ruling. This subtask always runs regardless of upstream phase outcomes, registered as the report-duty-priority deviation from the source wrapper's set -eu hard deaths. Exit 1 with a summary line is the normal findings path and feeds the checker_failed family; a kill or crash before the summary line is absorbed to the sentinel and the marker below says so.
  13.1. [act] Run the final cache-only checker pass
    - ← checker_argv
    + → final_checker_rc, final_checker_report
    > Deterministic invocation of the bundled checker under the same cache-only argument vector, engine subprocess cap, streams merged.
    > ```hop_python
    > argv = ["python3", spec_dir("scripts/kverus_postprocess.py")] + checker_argv
    > r = subprocess.run(argv, cwd: ".", timeout: 300)
    > final_checker_rc = r.returncode
    > final_checker_report = r.stdout + r.stderr
    > ```
  13.2. [check final] Gate the final checker completion
    - ← final_checker_rc, final_checker_report
    + → ok % bool  # true when the worker printed its findings summary line
    + → note % text  # failure explanation naming the final checker completion gate
    > Completion gate, not a green gate: exit 1 with a summary line is the normal findings path; only a missing summary line fails the gate.
    > ```hop_python
    > ok = len(split(final_checker_report, "INFO: Summary:")) > 1
    > note = "" if ok else "final checker worker produced no findings summary (exit code " + str(final_checker_rc) + ")"
    > ```
  13.3. [on fail] Absorb the crashed final checker
    13.3.1. [act] Record the crash honestly
      - ← final_checker_rc, final_checker_report
      + → final_checker_rc, final_checker_report
      > Absorption: the sentinel is reaffirmed so the classifier reads a crash unambiguously (any returned exit code with a summary completed the gate above), and the captured output stands as evidence.
      > ```hop_python
      > final_checker_rc = -1
      > final_checker_report = "final checker worker crashed or was killed before its findings summary: " + final_checker_report + " — the tree is judged not clean in the outcome precedence"
      > ```
14. [act] Classify the final checker verdict
  - ← final_checker_rc, final_checker_report
  + → final_checker_state % enum(clean, errors_found, crashed)  # clean: exit 0; errors_found: exit 1 with a summary; crashed: sentinel exit or missing summary
  > Deterministic discrimination mirroring the initial verdict: a red final checker is the terminal family signal composed at the outcome step, and a crash is classified honestly rather than being quietly read as clean.
  > ```hop_python
  > final_summary_found = len(split(final_checker_report, "INFO: Summary:")) > 1
  > final_crashed = (final_checker_rc == -1) or (final_summary_found == false)
  > final_checker_state = "crashed" if final_crashed else ("errors_found" if final_checker_rc == 1 else "clean")
  > ```
15. [subtask retry=0] Run the git whitespace check — closing duty, always runs
  + → git_diff_check_rc, git_diff_check_report
  > The source's closing whitespace duty. Both returned codes are normal terminals — exit 0 clean, exit 1 whitespace errors found (findings feed the checker_failed family through the outcome precedence); only a kill or crash before return is absorbed to the sentinel. Single attempt by ruling: the command is read-only.
  15.1. [act] Run the whitespace check
    + → git_diff_check_rc, git_diff_check_report
    > Deterministic invocation of the whitespace check, streams merged.
    > ```hop_python
    > argv = ["git", "diff", "--check"]
    > r = subprocess.run(argv, cwd: ".", timeout: 300)
    > git_diff_check_rc = r.returncode
    > git_diff_check_report = r.stdout + r.stderr
    > ```
  15.2. [on fail] Absorb the killed whitespace check
    15.2.1. [act] Reaffirm the sentinel with its narrative
      + → git_diff_check_rc, git_diff_check_report
      > Absorption: the sentinel reads as not clean in the outcome precedence — an unknown whitespace state is not a pass.
      > ```hop_python
      > git_diff_check_rc = -1
      > git_diff_check_report = "git diff --check worker killed or crashed; whitespace state unknown (treated as not clean in the outcome precedence)"
      > ```
16. [subtask retry=0] Capture the tree status — closing duty, always runs
  + → git_status_text % line
  > The source's closing capture of the short branch-aware status for the report. Single attempt by ruling; a kill or crash is absorbed to the unknown marker.
  16.1. [act] Capture the tree status
    + → git_status_text
    > Deterministic status capture, streams merged.
    > ```hop_python
    > argv = ["git", "status", "--short", "--branch"]
    > r = subprocess.run(argv, cwd: ".", timeout: 300)
    > git_status_text = r.stdout + r.stderr
    > ```
  16.2. [on fail] Absorb the killed status capture
    16.2.1. [act] Record the unknown status
      + → git_status_text
      > Absorption: the report slot says the status is unknown rather than implying a clean tree.
      > ```hop_python
      > git_status_text = "git status worker killed or crashed; tree status unknown"
      > ```
17. [act] Compose the outcome family by precedence
  - ← simplification_runnable, strip_outcome, verify_state, reverify_state, format_state, final_checker_state, git_diff_check_rc
  + → simplify_fail_family % bool  # delegation ran and the callee outcome is not completed
  + → verify_fail_family % bool  # the verification or re-verification phase ended red or killed
  + → format_fail_family % bool  # the formatter phase ended red or killed
  + → checker_fail_family % bool  # the final checker found errors or crashed, or the whitespace state is not clean
  + → postprocess_outcome % enum(completed, checker_failed, verify_failed, simplification_failed, format_failed)  # worst-family precedence
  > Deterministic family composition, registered deviations and all: a delegated-but-not-completed simplification is its own family (a skip is not a failure); the verification families fold both phases and treat the killed sentinel as not green; the final checker family folds the judge verdict and the whitespace sentinel; and the worst family wins by the precedence simplification over verification over formatting over checker over completed. The family flags avoid the enum member names so the conditional literals stay unambiguous.
  > ```hop_python
  > simplify_fail_family = (simplification_runnable == true) and (strip_outcome != "completed")
  > verify_fail_family = (verify_state == "red") or (reverify_state == "red")
  > format_fail_family = format_state == "red"
  > checker_fail_family = (final_checker_state != "clean") or (git_diff_check_rc != 0)
  > postprocess_outcome = "simplification_failed" if simplify_fail_family else ("verify_failed" if verify_fail_family else ("format_failed" if format_fail_family else ("checker_failed" if checker_fail_family else "completed")))
  > ```
18. [reason] Compose the five-element postprocess report
  - ← cache_status, refresh_rc, refresh_note, checker_state, checker_report, fix_note, verify_command, verify_state, verify_rc, reverify_state, reverify_rc, strip_report, strip_outcome, strip_script_rc, pre_rlimit, post_rlimit, format_state, format_rc, format_report, final_checker_state, final_checker_rc, final_checker_report, git_diff_check_rc, git_diff_check_report, git_status_text
  + → postprocess_report % markdown  # the labeled five-element report, labels verbatim from the source Report section
  > Compose the report from exactly the source's five elements, labels verbatim: (1) the dynamic rule refresh/check result — cache verdict, bounded refresh outcome with its rc and captured summary, initial checker verdict with its findings report, and the fix-phase record; (2) the verification command(s) — the supplied command and both phases' verdicts with exit codes, or the skip records; (3) the assert simplification result — the delegated report embedded verbatim with the callee outcome, script exit code, and rlimit pair, or the skip record with its cause; (4) the formatter result — verdict, exit code, and captured output, or the skip record; (5) the final git diff --check result — rc, captured output, the final checker verdict with its rc and findings report, and the tree status capture. Every slot reports what the phases actually produced, sentinels included and marked as such; nothing is fabricated, and a killed worker is never presented as a green or red run.
  > [[kverus-postprocess-knowledge#Report]]
19. [act] Soft gate the five required report labels
  - ← postprocess_report
  + → report_labels_ok % bool  # true when all five label phrases appear in the composed report
  + → postprocess_report
  > Soft gate over the five verbatim label phrases; a missing label appends an explicit defect line to the report rather than failing the run — the report duty is honesty-first, matching the source's report discipline.
  > ```hop_python
  > has_refresh_label = len(split(postprocess_report, "dynamic rule")) > 1
  > has_verify_label = len(split(postprocess_report, "verification command")) > 1
  > has_strip_label = len(split(postprocess_report, "assert simplification")) > 1
  > has_format_label = len(split(postprocess_report, "formatter")) > 1
  > has_git_label = len(split(postprocess_report, "git diff --check")) > 1
  > report_labels_ok = has_refresh_label and has_verify_label and has_strip_label and has_format_label and has_git_label
  > postprocess_report = postprocess_report if report_labels_ok else postprocess_report + "\nlabel defect: one or more of the five required report labels is missing"
  > ```
20. [exit] Carry the postprocess report, outcome, and evidence exports
  + → postprocess_report, postprocess_outcome, final_checker_rc, strip_report, strip_outcome, refresh_rc, checker_rc
  > Terminal exit. The seven declared exports carry the five-element report, the worst-family outcome, the final checker exit code, the delegated strip report and outcome, the bounded refresh exit code (1 with a summary line is the graceful fallback and counts as completed; -1 is skipped or crashed), and the initial checker exit code — everything a caller needs to judge the run without re-reading this spec's internals.
