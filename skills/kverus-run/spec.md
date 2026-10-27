# Spec: Run the full Rust-to-Verus pipeline end to end — migrate, stage, scaffold, repair, evaluate, audit, postprocess, report
Id: kverus-run
Goal: Drive the six-phase KVerus pipeline over one Rust entry file or a whole directory — discover and snapshot the originals, convert each file through kverus-migrate, stage the migration layer, scaffold contracts through kverus-spec with a machine-captured scaffold diff, safety-net the scaffolding verification through kverus-fix, score the spec layer per file through kverus-eval with a bounded two-ticket repair loop and an accept-or-stop quality gate, pause at high-severity semantic findings from kverus-semantic-audit with a continue-or-restore abort gate, close with the kverus-postprocess bookends, and always compose the nine-section pipeline summary — with every terminal route (completed, manual stop, audit abort, honest halt) carrying the full record set through the exit and never silently dropping a file.

Constraints:
- Compact translation of the kverus-run skill; this spec owns the pipeline routing, the phase cascade, the discovery/snapshot/staging machine duties, the per-file delegation wrappers with crash absorption, the two quality gates, the reduced stop reports, and the always-composed summary; the per-skill transformation rules, hard constraints, scoring rubrics, classification heuristics, review-rule catalogues, and CLI surfaces live in the six callee specs and their knowledge documents; the pipeline-level objective, the phase map, the walker and copier CLI contracts, the cache warm-up policy, the relay decoding table, and the deviation register live in the companion knowledge document [[kverus-run-knowledge]].
- Shared Verus references carried from the source skill: every phase that edits Verus code inherits `../kverus-common/references/exec-code-preservation.md` — before any permitted addition, removal, or rewrite of executable Rust, read and follow its reason-first `Origin Rust:` block-comment format; the edit-phase callees (migrate, spec, fix) carry their own copies of that ruling, and this spec never weakens it. When the pipeline report or a gate narrative must reason about proof constructs, read the relevant reference under `../kverus-common/references/` first — `verus-syntax-quickref.md`, `ghost-tracked.md`, `lemma-shape.md`, and `unsupported-features/index.md` under the sibling kverus-common references tree.
- Global Verus guide rules carried verbatim from the kverus-common skill; they govern every edit the delegated phases make:
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
- Invocation form (source): `$kverus-run target=<file-or-dir> verify="<command>" [out_dir=<reports-dir>]`; the three inputs map one-to-one to the spec inputs; out_dir defaults to `.kverus-run-output/` under the workspace root when empty.
- L1 environment bootstrap: the three bundled scripts (the directory walker, the snapshot copier, and the byte-identical postprocess checker copy this spec drives for the phase-0 cache probe and warm-up) self-source `kverus.env` at entry by the repo's pinned bootstrap; this spec invokes them as `python3` plus `spec_dir("scripts/<name>")` and never sources env files itself; the deployment prerequisite list in the knowledge document carries the env-file presence duty.
- Discovery approximation registered: the pinned walker emits the directory-mode work list in alphabetical order; the source's "sort by dependency order when possible (leaf modules first), otherwise alphabetical" is executor cognition the machine walker does not attempt — per-file dependency handling stays with the migrate callee's own inspection duty.
- L6 dynamic-command discipline: the user-supplied verification command is relayed whole to the migration, scaffolding, repair, and evaluation callees (each splits it itself); this spec's own subprocess channels use only fixed argv lists (python3 script forms, git, mktemp, rm); the first word of the user's verification command must be registered in the engine's command whitelist at deployment — a differently-prefixed verifier wrapper is a deployment prerequisite, not a spec defect.
- Staging breadth ruling (source-faithful): phase 2 stages the discovered file list flat (`git add -- <file_list>`), exactly the source's `git add <files in FILE_LIST>` — blocked files whose callee stopped mid-edit therefore stage their partial edits too; the honest-disclosure duty is the per-file migration record and the report tables, not a staging filter.
- Verus-directory derivation for the audit: machine-computed at phase 6 — the target directory itself in directory mode, the target file's parent directory in file mode — matching the source's verus_dir ruling; the rust half of the audit pair is the pre-edit snapshot root.
- Eval quality-gate fidelity: the threshold is 7/10 per file; a failing file gets at most two automatic repair tickets (re-scaffold, re-repair, re-evaluate — the source's "up to 2 retries"); the exhausted gate offers exactly the source's two dispositions, accept or manual stop; the manual stop preserves the tree (migration staged, spec edits unstaged) for the user's own editing and commits the reduced stop report; the accept route records the raw answer and continues.
- Audit abort fidelity: the audit gate offers continue or abort; the abort route runs the full restore duty chain — copier restore of every snapshotted file, unstage of the staged migration layer, snapshot-root removal — then composes and commits the reduced stop report and exits aborted; the continue route records the raw answer and proceeds.
- Unstage coupling (source Cleanup §2): the closing unstage duty belongs to the audit-abort route only; the completed pipeline and the manual stop deliberately leave the migration layer staged so the user reviews the staged migration against the unstaged spec work, exactly the separation phase 2 created.
- Completion-gate discipline for machine duties (the L36 family): user-shaped commands (git add, git restore --staged, git diff capture is read-only but still rc-checked, mktemp, rm) get completion gates (`rc != -1`, any returned code completes) rather than green gates, with kill/crash absorbed to the -1 sentinel and narrated; only the bundled-script warm-up uses the anchor-substring completion gate the script's own output contract guarantees.
- Report-duty priority on every terminal route: completed, manual stop, audit abort, and every honest halt compose their report text from the always-produced record sets before exiting; routes with a provisioned output tree commit their report file (the completion summary and the two reduced stop reports), and pre-provisioning halts exit with the note in the exit payload only — the source never silently drops a file, and neither does this spec.
- Reduced stop reports registered: the manual-stop and audit-abort tails commit a reduced machine summary (configuration, per-file tables for the records collected so far, disposition, cleanup states) rather than the full nine-section completion skeleton; the completion path composes all nine sections from the source's Phase 8 list, with the narrative sections 8 and 9 (Blockers & Warnings, Suggested Next Steps) expressed as machine-consolidated per-file rows and outcome-routed next-step lines, so the committed file is fully deterministic; the free-form narrative judgment lives in this instance's reason steps and the callee reports embedded in the record tables.
- Callee commit surfacing (rule 17): the repair callee and the audit callee carry their own commit steps (blocker summary writes, audit report writes); static calls into commit-carrying callees were probe-validated clean, and at runtime every commit — this spec's own summary write and each callee-instance write — surfaces through the engine's universal commit-approval pause cards, with callee commits governed by their own instance-level pauses; this spec adds no confirm gates of its own.
- Callee enum relays: migration_outcome, repair_outcome, postprocess_outcome, and audit_outcome ride as line values ("converted"/"blocked"/"crashed" and friends, plus the run-added "crashed" crash marker and "skipped-empty" skip word); the callee-side enums stay in the callee specs, and this spec's report tables and gate words decode the relayed strings.
- Repair hint chaining: the safety-net repair pairs the freshest context first — the file's scaffolding verification report when the scaffolding round produced one, else the migration final report; re-repair rounds re-pair from the fresh re-scaffold report, matching the source's use of the current failure context.
- Mode relay to the repair callee: "explicit" — this pipeline owns target discovery and never lets the repair callee auto-discover; the discovery-mode and discoverability decisions are machine-made upstream.
- Blocker-path leaf naming: per-file blocker summaries relay to `<effective_out_dir>/fix-blockers/<file-leaf>-blocker-summary.md`; two snapshotted files sharing a leaf name in different directories would collide on one summary path — a pathological workspace shape, disclosed here rather than filtered.
- No shell anywhere: every subprocess is a fixed or comprehension-built argv list; the only string-joining duty is the comma-joined file list handed to the copier (paths containing commas are unsupported and disclosed); hop_python bodies use function forms only (split, join, len, str, parse_json, read, exists, now) with subscript dict access and no method calls.
- Provisional values (translation ledger, the L10 family with the engine retry=N-counts-failures correction): walker, copier, cache probe, git duties, and snapshot removal caps 300 seconds; warm-up refresh 900 seconds; engine subprocess kills read as the rc -1 sentinel; the per-file delegation wrappers are single-attempt retry=0 with on-fail absorption (the retry ladders live inside the callees, which declare their own); the eval repair tickets are exactly the source's two; the whole-run re-verify budget is the callees' own.
- P6-gated halt subtasks: the pure gate subtasks on terminal routes (halt tails, stop tails, the completion gate) run retry=0 with no on-fail — the engine's own validator text marks that shape as the correct "failure stops the instance" form and its warning is sanctioned-with-reason; adding an on-fail there would swallow the gate failure into a continue, which is exactly what a terminal gate must never do.
- L24-family note: this spec edits no proof source itself — every source edit is delegated to the callee specs' executor steps; the only disk writes this spec performs are the machine snapshot/restore copier duty, the cache probe, the report commit, and the snapshot-root removal.
- L13 honest-stop family: each phase's per-file status rides in its record list (migration, spec, repair, evaluation), the two quality gates ask before acting on their exhausted or critical routes, and the exit lifts all sixteen declared outputs on every route so a halted instance still carries the partial records.
- Audit findings coupling: this spec's machine severity gate at the audit relay consumes the callee's findings JSON with the callee's documented per-file field set — entries keyed path, classification, severity — filtering classification "semantic-change" at severity "high"; the kverus-semantic-audit spec owns emitting exactly those keys, and the two specs are co-delivered so the contract holds.
- Report section-5 approximation: the source's average score is machine-dropped — hop_python carries no sum primitive, so section 5 of the committed report composes the per-file scores plus a machine-compiled failing-file list instead of the arithmetic mean; registered deviation.
- Re-spec guidance approximation: repair rounds re-pair the freshest failure context from this spec's own record tables (the file's scaffolding verification report when one exists, else its migration final report) and re-read the tree state directly; the source's eval-rationale handoff into the re-scaffold callee is approximated because the eval callee's report is not a re-scaffold input — the rationale rides the record tables and the repair log instead.
- Postprocess relay ruling: phase 7 relays target_paths as the discovered directory itself in directory mode and the comma-joined discovered list in file mode — the source's "FILE_LIST or the target directory"; the other eight optional postprocess parameters relay as the empty defaults the callee documents, so the delegated bookend behaves exactly as its own spec's defaults prescribe.

Inputs:
- target % line  # Rust entry: a .rs file path (single-file mode) or a directory path (directory mode); empty routes to the ask gate, and a path that neither exists as file nor directory halts honestly before any mutation
- verify_command % line  # the pipeline verification command string; whitespace-split by each callee; empty routes to the ask gate (the source never defaults it)
- out_dir % line  # optional report root under the workspace; empty defaults to .kverus-run-output/; provisioned by the snapshot duty

Outputs:
- pipeline_outcome % enum(completed, manual_stopped, aborted, halted)  # completed: full cascade and committed summary; manual_stopped: eval-exhausted user stop with tree preserved; aborted: audit-abort restore chain completed; halted: pre-flight or duty failure before any further safe progress
- summary_path % line  # the committed report path on routes that write one; empty on pre-provisioning halts
- migrate_records % [MigrateRecord]  # one record per discovered file, always produced
- spec_records % [SpecRecord]  # one record per converted file, with the machine-captured scaffold diff
- fix_records % [FixRecord]  # one record per file whose scaffolding verification failed or crashed
- eval_records % [EvalRecord]  # one record per converted file, with the per-file repair-round log
- audit_outcome % line  # the audit callee's outcome relay (completed, collector_failed), the run-added crashed marker, or skipped-empty
- audit_report_path % line  # the audit summary path relayed from the callee; empty when skipped or crashed
- audit_findings_path % line  # the machine-readable findings JSON path relayed from the callee
- postprocess_report % markdown  # the postprocess callee's five-element report embedded verbatim
- postprocess_outcome % line  # the postprocess callee's outcome relay, or the run-added skipped-empty word
- pp_final_checker_rc % int  # the postprocess closing checker exit code relay; -1 when skipped or crashed
- strip_report % markdown  # the delegated simplification report relayed from the postprocess callee
- strip_outcome % line  # the delegated simplification outcome relay
- restored_originals % bool  # true only when the audit-abort restore duty completed cleanly
- final_note % markdown  # the route-closing note composed on every terminal path

Types:
MigrateRecord:
  file % line
  edited_target % line
  verify_report % markdown
  verify_rc % int
  migration_outcome % line
  final_report % markdown
SpecRecord:
  file % line
  edited_target % line
  verify_report % markdown
  verify_rc % int
  spec_diff % markdown
  spec_status % line
FixRecord:
  file % line
  repair_outcome % line
  verify_rc % int
  resolution_report % markdown
  final_report % markdown
  blocker_summary_path % line
EvalRecord:
  file % line
  score_num % int
  eval_report % markdown
  gate_choice % line
  repair_rounds % [line]

Config:
  requires_commands: [python3, git, mktemp, rm]
## 已批准命令
- python3  # pinned bundled scripts: scripts/discover_files.py, scripts/snapshot_copy.py, scripts/kverus_postprocess.py via spec_dir
- git  # scoped status probe, phase-2 staging, audit-abort unstage, per-file scaffold diff capture
- mktemp  # pre-edit snapshot root creation (-d)
- rm  # snapshot-root removal on closing and halt duties (-rf, guarded by a nonempty root)

## Steps

1. [act] Pre-provision every carried output and machine variable
  - ← target, verify_command, out_dir
  + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
  + → summary_path % line
  + → migrate_records % [MigrateRecord]
  + → spec_records % [SpecRecord]
  + → fix_records % [FixRecord]
  + → eval_records % [EvalRecord]
  + → audit_outcome % line
  + → audit_report_path % line
  + → audit_findings_path % line
  + → postprocess_report % markdown
  + → postprocess_outcome % line
  + → pp_final_checker_rc % int
  + → strip_report % markdown
  + → strip_outcome % line
  + → restored_originals % bool
  + → final_note % markdown
  + → has_target % bool
  + → has_verify % bool
  + → effective_target % line
  + → effective_verify_command % line
  + → effective_out_dir % line
  + → audit_dir % line
  + → target_answer % line
  + → verify_answer % line
  + → dirty_answer % text
  + → audit_answer % text
  + → e_answer % text
  + → dirty_proceed % bool
  + → audit_choice % line
  + → e_gate_choice % line
  + → discovery_rc % int
  + → discovery_raw % text
  + → discovery_mode % line
  + → file_list % [line]
  + → discovery_note % text
  + → porcelain_rc % int
  + → porcelain_raw % text
  + → dirty_rows % [line]
  + → tree_dirty % bool
  + → mktemp_rc % int
  + → orig_dir % line
  + → snapshot_root_ok % bool
  + → files_csv % line
  + → snapshot_rc % int
  + → snapshot_note % text
  + → cache_rc % int
  + → cache_status_raw % text
  + → cache_status % line
  + → fresh_count % int
  + → stale_count % int
  + → missing_count % int
  + → cache_repo % line
  + → cache_configured % bool
  + → needs_refresh % bool
  + → warm_rc % int
  + → warm_raw % text
  + → warm_failed % bool
  + → warm_note % text
  + → warm_state % line
  + → converted_files % [line]
  + → blocked_files % [line]
  + → crashed_files % [line]
  + → converted_count % int
  + → blocked_count % int
  + → crashed_count % int
  + → migrate_reconciled % bool
  + → staging_state % line
  + → stage_rc % int
  + → stage_note % text
  + → stage_failed % bool
  + → spec_reconciled % bool
  + → fix_files % [line]
  + → fix_count % int
  + → e_score % int
  + → score_word % line
  + → repair_tickets % [int]
  + → repair_log % [line]
  + → verus_dir % line
  + → audit_collector_rc % int
  + → audit_note % markdown
  + → has_high % bool
  + → high_count % int
  + → high_sample % [line]
  + → audit_gate_word % line
  + → target_csv % line
  + → refresh_rc % int
  + → checker_rc % int
  + → restore_rc % int
  + → restore_note % text
  + → restore_failed % bool
  + → restore_ok % bool
  + → unstage_rc % int
  + → unstage_note % text
  + → unstage_failed % bool
  + → rm_rc % int
  + → rm_note % text
  + → rm_failed % bool
  + → rm_state % line
  + → pipeline_report % markdown
  + → written_summary_path % line
  > ```hop_python
  > has_target = len(target) > 0
  > has_verify = len(verify_command) > 0
  > effective_target = target
  > effective_verify_command = verify_command
  > base = out_dir if len(out_dir) > 0 else ".kverus-run-output"
  > effective_out_dir = base + "/"
  > audit_dir = effective_out_dir + "audit/"
  > summary_path = effective_out_dir + "pipeline_summary.md"
  > pipeline_outcome = "halted"
  > final_note = ""
  > restored_originals = false
  > migrate_records = []
  > spec_records = []
  > fix_records = []
  > eval_records = []
  > audit_outcome = ""
  > audit_report_path = ""
  > audit_findings_path = ""
  > postprocess_report = ""
  > postprocess_outcome = ""
  > pp_final_checker_rc = -1
  > strip_report = ""
  > strip_outcome = ""
  > target_answer = ""
  > verify_answer = ""
  > dirty_answer = ""
  > audit_answer = ""
  > e_answer = ""
  > dirty_proceed = false
  > audit_choice = ""
  > e_gate_choice = ""
  > discovery_rc = -1
  > discovery_raw = ""
  > discovery_mode = ""
  > file_list = []
  > discovery_note = ""
  > porcelain_rc = -1
  > porcelain_raw = ""
  > dirty_rows = []
  > tree_dirty = false
  > mktemp_rc = -1
  > orig_dir = ""
  > snapshot_root_ok = false
  > files_csv = ""
  > snapshot_rc = -1
  > snapshot_note = ""
  > cache_rc = -1
  > cache_status_raw = ""
  > cache_status = "unknown"
  > fresh_count = 0
  > stale_count = 0
  > missing_count = 0
  > cache_repo = ""
  > cache_configured = false
  > needs_refresh = false
  > warm_rc = -1
  > warm_raw = ""
  > warm_failed = false
  > warm_note = ""
  > warm_state = "idle"
  > converted_files = []
  > blocked_files = []
  > crashed_files = []
  > converted_count = 0
  > blocked_count = 0
  > crashed_count = 0
  > migrate_reconciled = false
  > staging_state = ""
  > stage_rc = -1
  > stage_note = ""
  > stage_failed = false
  > spec_reconciled = false
  > fix_files = []
  > fix_count = 0
  > e_score = -1
  > score_word = ""
  > repair_tickets = [1, 2]
  > repair_log = []
  > verus_dir = ""
  > audit_collector_rc = -1
  > audit_note = ""
  > has_high = false
  > high_count = 0
  > high_sample = []
  > audit_gate_word = ""
  > target_csv = ""
  > refresh_rc = -1
  > checker_rc = -1
  > restore_rc = -1
  > restore_note = ""
  > restore_failed = false
  > restore_ok = false
  > unstage_rc = -1
  > unstage_note = ""
  > unstage_failed = false
  > rm_rc = -1
  > rm_note = ""
  > rm_failed = false
  > rm_state = ""
  > pipeline_report = ""
  > written_summary_path = ""
  > ```

2. [branch] Target presence ask gate
  - ← has_target
  2.1. [case(has_target)] Carry the spelled entry
    2.1.1. [reason] The caller named the conversion root. Discovery walks it next; a path that exists neither as file nor as directory halts honestly before any mutation.
  2.2. [case(has_target == false)] Ask which Rust entry to convert
    2.2.1. [ask] Name the Rust entry to convert — a .rs file for single-file mode or a directory for directory mode
      + → target_answer % line
    2.2.2. [act] Bind the asked entry
      - ← target_answer
      + → effective_target % line
      > ```hop_python
      > effective_target = target_answer
      > ```
    2.2.3. [reason] The asked entry is bound and discovery will walk it. An empty or nonexistent answer routes through the discovery verdict gate into the pre-mutation halt.

3. [branch] Verification-command ask gate
  - ← has_verify
  3.1. [case(has_verify)] Carry the spelled verification command
    3.1.1. [reason] The caller supplied the verification command. It is relayed whole to the migration, scaffolding, repair, and evaluation callees; each callee splits it itself by the L6 discipline.
  3.2. [case(has_verify == false)] Ask for the verification command
    3.2.1. [ask] Name the verification command the pipeline should run (for example cargo verus or a verus invocation)
      + → verify_answer % line
    3.2.2. [act] Bind the asked verification command
      - ← verify_answer
      + → effective_verify_command % line
      > ```hop_python
      > effective_verify_command = verify_answer
      > ```
    3.2.3. [reason] The asked verification command is bound. Its first word must be registered in the engine command whitelist at deployment, exactly the L6 prerequisite.

4. [act] Walk the entry with the pinned directory walker
  - ← effective_target
  + → discovery_rc % int
  + → discovery_raw % text
  + → discovery_mode % line
  + → file_list % [line]
  + → discovery_note % text
  > ```hop_python
  > argv = ["python3", spec_dir("scripts/discover_files.py"), effective_target]
  > r = subprocess.run(argv, cwd:".", timeout:300)
  > discovery_rc = r.returncode
  > discovery_raw = r.stdout + r.stderr
  > payload = parse_json(discovery_raw) if discovery_raw else {}
  > guarded = payload if payload else {}
  > discovery_mode = guarded["mode"] if "mode" in guarded else "missing"
  > file_list = guarded["files"] if "files" in guarded else []
  > discovery_note = "walker returned mode " + discovery_mode
  > ```

5. [branch] Discovery verdict gate
  - ← discovery_mode, file_list
  5.1. [case(discovery_mode == "missing")] Halt before any mutation — the entry does not exist
    5.1.1. [act] Compose the missing-entry halt
      - ← effective_target
      + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
      + → summary_path % line
      + → final_note % markdown
      > ```hop_python
      > pipeline_outcome = "halted"
      > summary_path = ""
      > final_note = "Discovery found no Rust entry at " + effective_target + ". The pipeline stopped before reading or editing anything. No snapshot was taken, no report tree was provisioned, and the working tree is untouched."
      > ```
    5.1.2. [subtask retry=0] Gate the missing-entry halt
      5.1.2.1. [check final] Seal the pre-mutation halt
        - ← pipeline_outcome, summary_path, final_note
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = pipeline_outcome == "halted" and len(final_note) > 0 and len(summary_path) == 0
        > note = "" if ok else "missing-entry halt gate failed"
        > ```
    5.1.3. [exit] Carry the missing-entry halt
      + → pipeline_outcome
      + → summary_path
      + → migrate_records
      + → spec_records
      + → fix_records
      + → eval_records
      + → audit_outcome
      + → audit_report_path
      + → audit_findings_path
      + → postprocess_report
      + → postprocess_outcome
      + → pp_final_checker_rc
      + → strip_report
      + → strip_outcome
      + → restored_originals
      + → final_note
  5.2. [case(else)] Carry the discovered work list
    5.2.1. [reason] Discovery settled: the mode word, the work-list length, and the report root (defaulting under the workspace when the caller passed none) are the phase-0 summary the source prints. Directory-mode ordering is alphabetical by the pinned walker, the registered approximation of the source's preferred leaf-first dependency ordering.

6. [act] Probe the scoped working-tree cleanliness
  - ← file_list
  + → porcelain_rc % int
  + → porcelain_raw % text
  + → dirty_rows % [line]
  + → tree_dirty % bool
  > ```hop_python
  > argv = ["git", "status", "--porcelain", "--"] + file_list
  > r = subprocess.run(argv, cwd:".", timeout:300)
  > porcelain_rc = r.returncode
  > porcelain_raw = r.stdout + r.stderr
  > dirty_rows = [row for row in split(porcelain_raw, "\n") if len(row) > 0]
  > tree_dirty = (porcelain_rc != 0) or (len(dirty_rows) > 0)
  > ```

7. [branch] Scoped dirty-tree gate
  - ← tree_dirty
  7.1. [case(tree_dirty)] Warn and ask before touching a dirty scope
    7.1.1. [ask] The scoped tree already carries unstaged or untracked changes. Continue anyway, answering continue, or stop the pipeline here with no edits?
      + → dirty_answer % text
    7.1.2. [act] Classify the continue decision
      - ← dirty_answer
      + → dirty_proceed % bool
      > ```hop_python
      > dirty_proceed = dirty_answer == "continue"
      > ```
    7.1.3. [branch] Route the continue decision
      - ← dirty_proceed
      7.1.3.1. [case(dirty_proceed)] Proceed over the dirty scope
        7.1.3.1.1. [reason] The user accepted proceeding. The pre-edit snapshot will capture the current dirty bytes as the baseline, phase 2 stages the discovered list flat exactly the source stages it, and the user's pre-existing edits ride inside that baseline honestly.
      7.1.3.2. [case(dirty_proceed == false)] Decline and halt with no duties
        7.1.3.2.1. [act] Compose the declined halt
          - ← effective_target
          + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
          + → summary_path % line
          + → final_note % markdown
          > ```hop_python
          > pipeline_outcome = "halted"
          > summary_path = ""
          > final_note = "The user declined to proceed over a dirty scoped tree at " + effective_target + ". No snapshot was taken, no report tree was provisioned, and the working tree is untouched."
          > ```
        7.1.3.2.2. [subtask retry=0] Gate the declined halt
          7.1.3.2.2.1. [check final] Seal the declined halt
            - ← pipeline_outcome, summary_path, final_note
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = pipeline_outcome == "halted" and len(final_note) > 0 and len(summary_path) == 0
            > note = "" if ok else "declined halt gate failed"
            > ```
        7.1.3.2.3. [exit] Carry the declined halt
          + → pipeline_outcome
          + → summary_path
          + → migrate_records
          + → spec_records
          + → fix_records
          + → eval_records
          + → audit_outcome
          + → audit_report_path
          + → audit_findings_path
          + → postprocess_report
          + → postprocess_outcome
          + → pp_final_checker_rc
          + → strip_report
          + → strip_outcome
          + → restored_originals
          + → final_note
      7.2. [case(tree_dirty == false)] Carry the clean scope
        7.2.1. [reason] The scoped probe found no rows for the discovered list. The snapshot root is created next, then the copier takes the pre-edit baseline and provisions the report tree.

8. [act] Create the pre-edit snapshot root
  + → mktemp_rc % int
  + → orig_dir % line
  + → snapshot_root_ok % bool
  > ```hop_python
  > argv = ["mktemp", "-d"]
  > r = subprocess.run(argv, cwd:".", timeout:300)
  > mktemp_rc = r.returncode
  > orig_dir = split(r.stdout, "\n")[0] if len(r.stdout) > 0 else ""
  > snapshot_root_ok = (mktemp_rc == 0) and (len(orig_dir) > 0)
  > ```

9. [branch] Snapshot-root verdict gate
  - ← snapshot_root_ok
  9.1. [case(snapshot_root_ok)] Carry the snapshot root
    9.1.1. [reason] A fresh snapshot root exists. The copier now copies every discovered file into it, preserving structure, and provisions the report tree with its audit and fix-blockers subdirectories.
  9.2. [case(snapshot_root_ok == false)] Halt with no duties — the snapshot root could not be created
    9.2.1. [act] Compose the mktemp-failure halt
      - ← mktemp_rc
      + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
      + → summary_path % line
      + → final_note % markdown
      > ```hop_python
      > pipeline_outcome = "halted"
      > summary_path = ""
      > final_note = "The pre-edit snapshot root could not be created (probe code " + str(mktemp_rc) + "). Nothing was read into a baseline and nothing was edited; the pipeline stopped before any mutation."
      > ```
    9.2.2. [subtask retry=0] Gate the mktemp-failure halt
      9.2.2.1. [check final] Seal the mktemp-failure halt
        - ← pipeline_outcome, summary_path, final_note
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = pipeline_outcome == "halted" and len(final_note) > 0 and len(summary_path) == 0
        > note = "" if ok else "mktemp halt gate failed"
        > ```
    9.2.3. [exit] Carry the mktemp-failure halt
      + → pipeline_outcome
      + → summary_path
      + → migrate_records
      + → spec_records
      + → fix_records
      + → eval_records
      + → audit_outcome
      + → audit_report_path
      + → audit_findings_path
      + → postprocess_report
      + → postprocess_outcome
      + → pp_final_checker_rc
      + → strip_report
      + → strip_outcome
      + → restored_originals
      + → final_note

10. [act] Snapshot the originals and provision the report tree
  - ← orig_dir, file_list, effective_out_dir
  + → files_csv % line
  + → snapshot_rc % int
  + → snapshot_note % text
  > ```hop_python
  > files_csv = join(file_list, ",")
  > argv = ["python3", spec_dir("scripts/snapshot_copy.py"), "--snapshot", orig_dir, files_csv, effective_out_dir]
  > r = subprocess.run(argv, cwd:".", timeout:300)
  > snapshot_rc = r.returncode
  > snapshot_note = r.stdout + r.stderr
  > ```

11. [branch] Snapshot duty verdict gate
  - ← snapshot_rc
  11.1. [case(snapshot_rc == 0)] Carry the provisioned baseline
    11.1.1. [reason] The copier copied the discovered list into the snapshot root with structure preserved and provisioned the report tree, including the audit and fix-blockers subdirectories. The cache probe runs next, then the warm-up gate, then the migration cascade.
  11.2. [case(snapshot_rc != 0)] Halt with the snapshot-root removal duty
    11.2.1. [subtask retry=0] Remove the abandoned snapshot root
      - ← orig_dir
      + → rm_rc % int
      + → rm_note % text
      + → rm_failed % bool
      11.2.1.1. [act] Remove the abandoned snapshot root
        - ← orig_dir
        + → rm_rc % int
        + → rm_note % text
        > ```hop_python
        > argv = ["rm", "-rf", orig_dir]
        > r = subprocess.run(argv, cwd:".", timeout:300)
        > rm_rc = r.returncode
        > rm_note = r.stdout + r.stderr
        > ```
      11.2.1.2. [check final] Seal the removal completion
        - ← rm_rc
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = rm_rc != -1
        > note = "" if ok else "snapshot removal did not return"
        > ```
      11.2.1.3. [on fail] Absorb the crashed removal
        11.2.1.3.1. [act] Mark the failed removal
          - ← rm_rc, rm_note
          + → rm_failed % bool
          + → rm_note % text
          > ```hop_python
          > rm_failed = true
          > rm_note = rm_note + " | removal absorbed with code " + str(rm_rc)
          > ```
    11.2.2. [act] Compose the snapshot-failure halt
      - ← snapshot_rc, snapshot_note, rm_failed
      + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
      + → summary_path % line
      + → final_note % markdown
      > ```hop_python
      > pipeline_outcome = "halted"
      > summary_path = ""
      > removal_word = "removed" if rm_failed == false else "removal-failed"
      > final_note = "The pre-edit snapshot copy failed with code " + str(snapshot_rc) + ". The working tree was not edited by this pipeline. Snapshot-root duty: " + removal_word + ". Copier note: " + snapshot_note
      > ```
    11.2.3. [subtask retry=0] Gate the snapshot-failure halt
      11.2.3.1. [check final] Seal the snapshot-failure halt
        - ← pipeline_outcome, summary_path, final_note
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = pipeline_outcome == "halted" and len(final_note) > 0 and len(summary_path) == 0
        > note = "" if ok else "snapshot-failure halt gate failed"
        > ```
    11.2.4. [exit] Carry the snapshot-failure halt
      + → pipeline_outcome
      + → summary_path
      + → migrate_records
      + → spec_records
      + → fix_records
      + → eval_records
      + → audit_outcome
      + → audit_report_path
      + → audit_findings_path
      + → postprocess_report
      + → postprocess_outcome
      + → pp_final_checker_rc
      + → strip_report
      + → strip_outcome
      + → restored_originals
      + → final_note

12. [act] Probe the dynamic-rule cache without network access
  + → cache_rc % int
  + → cache_status_raw % text
  > ```hop_python
  > argv = ["python3", spec_dir("scripts/kverus_postprocess.py"), "--cache-status"]
  > r = subprocess.run(argv, cwd:".", timeout:300)
  > cache_rc = r.returncode
  > cache_status_raw = r.stdout + r.stderr
  > ```

13. [act] Classify the cache freshness
  - ← cache_rc, cache_status_raw
  + → cache_status % line
  + → fresh_count % int
  + → stale_count % int
  + → missing_count % int
  + → cache_repo % line
  + → cache_configured % bool
  + → needs_refresh % bool
  > ```hop_python
  > payload = parse_json(cache_status_raw) if cache_status_raw else {}
  > guarded = payload if payload else {}
  > fresh_count = len(split(cache_status_raw, '"status": "fresh"')) - 1
  > stale_count = len(split(cache_status_raw, '"status": "stale"')) - 1
  > missing_count = len(split(cache_status_raw, '"status": "missing"')) - 1
  > cache_repo = guarded["repo"] if "repo" in guarded else ""
  > cache_configured = len(cache_repo) > 0
  > cache_status = "fresh" if fresh_count > 0 else ("stale" if stale_count > 0 else ("missing" if missing_count > 0 else "unknown"))
  > needs_refresh = cache_configured and (stale_count > 0 or missing_count > 0)
  > ```

14. [branch] Cache warm-up gate
  - ← needs_refresh
  14.1. [case(needs_refresh)] Delegate one bounded refresh-only warm-up pass
    14.1.1. [subtask retry=0] Wrap the bounded refresh-only warm-up
      + → warm_rc % int
      + → warm_raw % text
      + → warm_failed % bool
      + → warm_note % text
      14.1.1.1. [act] Preset the warm-up sentinels
        + → warm_rc % int
        + → warm_raw % text
        + → warm_failed % bool
        + → warm_note % text
        > ```hop_python
        > warm_rc = -1
        > warm_raw = ""
        > warm_failed = false
        > warm_note = ""
        > ```
      14.1.1.2. [act] Run the bounded refresh-only pass
        + → warm_rc % int
        + → warm_raw % text
        > ```hop_python
        > argv = ["python3", spec_dir("scripts/kverus_postprocess.py"), "--refresh-only"]
        > r = subprocess.run(argv, cwd:".", timeout:900)
        > warm_rc = r.returncode
        > warm_raw = r.stdout + r.stderr
        > ```
      14.1.1.3. [check final] Gate the warm-up completion on its summary anchor
        - ← warm_rc, warm_raw
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = warm_rc != -1 and len(split(warm_raw, "Refresh-only summary:")) > 1
        > note = "" if ok else "refresh completion anchor absent or the process died"
        > ```
      14.1.1.4. [on fail] Absorb the crashed warm-up
        14.1.1.4.1. [act] Mark the failed warm-up
          - ← warm_rc
          + → warm_failed % bool
          + → warm_note % text
          > ```hop_python
          > warm_failed = true
          > warm_note = "refresh-only pass did not complete cleanly with code " + str(warm_rc) + "; the pipeline continues on cached or static rules"
          > ```
    14.1.2. [act] Record the warm-up verdict
      - ← warm_failed
      + → warm_state % line
      > ```hop_python
      > warm_state = "crashed" if warm_failed else "refreshed"
      > ```
  14.2. [case(needs_refresh == false)] Record the idle cache
    14.2.1. [act] Mark the cache idle
      + → warm_state % line
      > ```hop_python
      > warm_state = "fresh-or-unconfigured"
      > ```


15. [loop for-each entry in file_list, collect mrec into migrate_records] Migrate each discovered file with crash absorption
  - ← file_list, effective_verify_command
  + → migrate_records % [MigrateRecord]
  15.1. [subtask retry=0] Wrap the delegated migration
    + → m_edited % line
    + → m_verify_report % markdown
    + → m_rc % int
    + → m_outcome % line
    + → m_final_report % markdown
    15.1.1. [act] Preset the migration sentinels
      + → m_edited % line
      + → m_verify_report % markdown
      + → m_rc % int
      + → m_outcome % line
      + → m_final_report % markdown
      > ```hop_python
      > m_edited = ""
      > m_verify_report = ""
      > m_rc = -1
      > m_outcome = ""
      > m_final_report = ""
      > ```
    15.1.2. [call kverus-migrate(target: entry, verify: effective_verify_command)] Delegate the conversion
      + → m_edited: edited_target
      + → m_verify_report: verify_report
      + → m_rc: verify_rc
      + → m_outcome: migration_outcome
      + → m_final_report: final_report
    15.1.3. [check final] Gate the delegated migration
      - ← m_outcome
      + → ok % bool
      + → note % text
      > ```hop_python
      > ok = len(m_outcome) > 0
      > note = "" if ok else "delegated migration returned no outcome word"
      > ```
    15.1.4. [on fail] Absorb the crashed migration
      15.1.4.1. [act] Mark the crashed migration
        + → m_outcome % line
        + → m_final_report % markdown
        > ```hop_python
        > m_outcome = "crashed"
        > m_final_report = "the migration worker crashed or was absorbed before producing a final report"
        > ```
  15.2. [act] Package the migration record
    - ← entry, m_edited, m_verify_report, m_rc, m_outcome, m_final_report
    + → mrec % MigrateRecord
    > ```hop_python
    > mrec = {"file": entry, "edited_target": m_edited, "verify_report": m_verify_report, "verify_rc": m_rc, "migration_outcome": m_outcome, "final_report": m_final_report}
    > ```

16. [act] Reconcile the migrations and classify the per-file sets
  - ← migrate_records, file_list
  + → converted_files % [line]
  + → blocked_files % [line]
  + → crashed_files % [line]
  + → converted_count % int
  + → blocked_count % int
  + → crashed_count % int
  + → migrate_reconciled % bool
  > ```hop_python
  > converted_files = [row["file"] for row in migrate_records if row["migration_outcome"] == "converted"]
  > blocked_files = [row["file"] for row in migrate_records if row["migration_outcome"] == "blocked"]
  > crashed_files = [row["file"] for row in migrate_records if row["migration_outcome"] == "crashed"]
  > converted_count = len(converted_files)
  > blocked_count = len(blocked_files)
  > crashed_count = len(crashed_files)
  > migrate_reconciled = len(migrate_records) == len(file_list)
  > ```

17. [branch] Staging duty gate
  - ← file_list
  17.1. [case(len(file_list) > 0)] Stage the discovered list flat
    17.1.1. [subtask retry=0] Stage the discovered files
      - ← file_list
      + → stage_rc % int
      + → stage_note % text
      + → stage_failed % bool
      17.1.1.1. [act] Stage the discovered list
        - ← file_list
        + → stage_rc % int
        + → stage_note % text
        > ```hop_python
        > argv = ["git", "add", "--"] + file_list
        > r = subprocess.run(argv, cwd:".", timeout:300)
        > stage_rc = r.returncode
        > stage_note = r.stdout + r.stderr
        > ```
      17.1.1.2. [check final] Seal the staging completion
        - ← stage_rc
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = stage_rc != -1
        > note = "" if ok else "staging did not return"
        > ```
      17.1.1.3. [on fail] Absorb the crashed staging
        17.1.1.3.1. [act] Mark the failed staging
          - ← stage_rc, stage_note
          + → stage_failed % bool
          + → stage_note % text
          > ```hop_python
          > stage_failed = true
          > stage_note = stage_note + " | staging absorbed with code " + str(stage_rc)
          > ```
    17.1.2. [act] Classify the staging verdict
      - ← stage_rc, stage_failed
      + → staging_state % line
      > ```hop_python
      > staging_state = "staged" if (stage_rc == 0 and stage_failed == false) else ("stage-red" if stage_failed == false else "stage-crashed")
      > ```
    17.1.3. [branch] Staging verdict route
      - ← staging_state
      17.1.3.1. [case(staging_state == "staged")] Carry the staged separation
        17.1.3.1.1. [reason] The discovered list is staged flat, exactly the source staging breadth, so the next phases evaluate spec quality against a clean separation: staged migration layer beneath the unstaged scaffold and repair edits. Files the migration marked blocked or crashed stage whatever partial state their callee left, and the per-file migration records disclose it.
      17.1.3.2. [case(staging_state != "staged")] Halt with the unstage and removal duties
        17.1.3.2.1. [subtask retry=0] Unstage the partial staging
          - ← file_list
          + → unstage_rc % int
          + → unstage_note % text
          + → unstage_failed % bool
          17.1.3.2.1.1. [act] Unstage the discovered list
            - ← file_list
            + → unstage_rc % int
            + → unstage_note % text
            > ```hop_python
            > argv = ["git", "restore", "--staged", "--"] + file_list
            > r = subprocess.run(argv, cwd:".", timeout:300)
            > unstage_rc = r.returncode
            > unstage_note = r.stdout + r.stderr
            > ```
          17.1.3.2.1.2. [check final] Seal the unstage completion
            - ← unstage_rc
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = unstage_rc != -1
            > note = "" if ok else "unstage did not return"
            > ```
          17.1.3.2.1.3. [on fail] Absorb the crashed unstage
            17.1.3.2.1.3.1. [act] Mark the failed unstage
              - ← unstage_rc, unstage_note
              + → unstage_failed % bool
              + → unstage_note % text
              > ```hop_python
              > unstage_failed = true
              > unstage_note = unstage_note + " | unstage absorbed with code " + str(unstage_rc)
              > ```
        17.1.3.2.2. [subtask retry=0] Remove the snapshot root
          - ← orig_dir
          + → rm_rc % int
          + → rm_note % text
          + → rm_failed % bool
          17.1.3.2.2.1. [act] Remove the snapshot root
            - ← orig_dir
            + → rm_rc % int
            + → rm_note % text
            > ```hop_python
            > argv = ["rm", "-rf", orig_dir]
            > r = subprocess.run(argv, cwd:".", timeout:300)
            > rm_rc = r.returncode
            > rm_note = r.stdout + r.stderr
            > ```
          17.1.3.2.2.2. [check final] Seal the removal completion
            - ← rm_rc
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = rm_rc != -1
            > note = "" if ok else "snapshot removal did not return"
            > ```
          17.1.3.2.2.3. [on fail] Absorb the crashed removal
            17.1.3.2.2.3.1. [act] Mark the failed removal
              - ← rm_rc, rm_note
              + → rm_failed % bool
              + → rm_note % text
              > ```hop_python
              > rm_failed = true
              > rm_note = rm_note + " | removal absorbed with code " + str(rm_rc)
              > ```
        17.1.3.2.3. [act] Compose the staging-failure halt
          - ← staging_state, stage_rc, stage_note, unstage_failed, rm_failed
          + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
          + → summary_path % line
          + → final_note % markdown
          > ```hop_python
          > pipeline_outcome = "halted"
          > summary_path = ""
          > unstage_word = "unstaged" if unstage_failed == false else "unstage-failed"
          > removal_word = "removed" if rm_failed == false else "removal-failed"
          > final_note = "Staging the migrated set failed in state " + staging_state + " with code " + str(stage_rc) + ". No scaffolding ran. Duties: unstage " + unstage_word + ", snapshot root " + removal_word + ". Staging note: " + stage_note
          > ```
        17.1.3.2.4. [subtask retry=0] Gate the staging-failure halt
          17.1.3.2.4.1. [check final] Seal the staging-failure halt
            - ← pipeline_outcome, summary_path, final_note
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = pipeline_outcome == "halted" and len(final_note) > 0 and len(summary_path) == 0
            > note = "" if ok else "staging-failure halt gate failed"
            > ```
        17.1.3.2.5. [exit] Carry the staging-failure halt
          + → pipeline_outcome
          + → summary_path
          + → migrate_records
          + → spec_records
          + → fix_records
          + → eval_records
          + → audit_outcome
          + → audit_report_path
          + → audit_findings_path
          + → postprocess_report
          + → postprocess_outcome
          + → pp_final_checker_rc
          + → strip_report
          + → strip_outcome
          + → restored_originals
          + → final_note
    17.1.4. [reason] The staging gate routed the verdict: a clean staging carries the layered separation forward, a red or crashed staging halts with the unstage and removal duties first, and the report file is deliberately absent on this pre-cascade route.
  17.2. [case(else)] Record the empty staging skip
    17.2.1. [act] Mark the empty skip
      + → staging_state % line
      > ```hop_python
      > staging_state = "nothing-to-stage"
      > ```
    17.2.2. [reason] Discovery produced an empty work list, so the source staging command has nothing to add. The cascade still runs its loops zero times and the report records the empty scope honestly.

18. [loop for-each file in converted_files, collect srec into spec_records] Scaffold contracts on the converted files
  - ← converted_files, effective_verify_command
  + → spec_records % [SpecRecord]
  18.1. [subtask retry=0] Wrap the delegated scaffolding
    + → s_edited % line
    + → s_report % markdown
    + → s_rc % int
    + → s_status % line
    18.1.1. [act] Preset the scaffolding sentinels
      + → s_edited % line
      + → s_report % markdown
      + → s_rc % int
      + → s_status % line
      > ```hop_python
      > s_edited = ""
      > s_report = ""
      > s_rc = -1
      > s_status = "crashed"
      > ```
    18.1.2. [call kverus-spec(target: file, verify: effective_verify_command, knowledge: "")] Delegate the scaffolding
      + → s_edited: edited_target
      + → s_report: verify_report
      + → s_rc: verify_rc
    18.1.3. [act] Mark the delegated success
      + → s_status % line
      > ```hop_python
      > s_status = "delegated"
      > ```
    18.1.4. [check final] Gate the delegated scaffolding
      - ← s_status, s_report
      + → ok % bool
      + → note % text
      > ```hop_python
      > ok = s_status == "delegated" and len(s_report) > 0
      > note = "" if ok else "delegated scaffolding did not produce a verification report"
      > ```
    18.1.5. [on fail] Absorb the crashed scaffolding
      18.1.5.1. [act] Keep the crash markers
        - ← s_status, s_report
        + → s_status % line
        + → s_report % markdown
        > ```hop_python
        > s_status = "crashed"
        > s_report = s_report if len(s_report) > 0 else "the scaffolding worker crashed or was absorbed before producing a verification report"
        > ```
  18.2. [act] Capture the scaffold diff and package the spec record
    - ← file, s_edited, s_report, s_rc, s_status
    + → s_diff % markdown
    + → srec % SpecRecord
    > ```hop_python
    > argv = ["git", "diff", "--", file]
    > r = subprocess.run(argv, cwd:".", timeout:300)
    > s_diff = r.stdout if r.returncode == 0 else ("scaffold diff capture failed with code " + str(r.returncode))
    > srec = {"file": file, "edited_target": s_edited, "verify_report": s_report, "verify_rc": s_rc, "spec_diff": s_diff, "spec_status": s_status}
    > ```

19. [act] Reconcile the scaffolding records
  - ← spec_records, converted_files
  + → spec_reconciled % bool
  > ```hop_python
  > spec_reconciled = len(spec_records) == len(converted_files)
  > ```

20. [act] Select the repair set
  - ← spec_records
  + → fix_files % [line]
  + → fix_count % int
  > ```hop_python
  > fix_files = [row["file"] for row in spec_records if row["verify_rc"] != 0]
  > fix_count = len(fix_files)
  > ```

21. [loop for-each file in fix_files, collect frec into fix_records] Repair the scaffolding verification failures
  - ← fix_files, effective_verify_command, spec_records, migrate_records, effective_out_dir
  + → fix_records % [FixRecord]
  21.1. [act] Pair the freshest failure context and compose the blocker path
    - ← file, spec_records, migrate_records, effective_out_dir
    + → f_hint % markdown
    + → f_blocker_path % line
    > ```hop_python
    > spec_rows = [row["verify_report"] for row in spec_records if row["file"] == file]
    > mig_rows = [row["final_report"] for row in migrate_records if row["file"] == file]
    > f_hint = spec_rows[0] if len(spec_rows) > 0 else (mig_rows[0] if len(mig_rows) > 0 else "")
    > f_blocker_path = effective_out_dir + "fix-blockers/" + split(file, "/")[-1] + "-blocker-summary.md"
    > ```
  21.2. [subtask retry=0] Wrap the delegated repair
    - ← file, effective_verify_command, f_hint, f_blocker_path
    + → f_resolution % markdown
    + → f_report % markdown
    + → f_rc % int
    + → f_outcome % line
    + → f_blocker % line
    + → f_status % line
    21.2.1. [act] Preset the repair sentinels
      + → f_resolution % markdown
      + → f_report % markdown
      + → f_rc % int
      + → f_outcome % line
      + → f_blocker % line
      + → f_status % line
      > ```hop_python
      > f_resolution = ""
      > f_report = ""
      > f_rc = -1
      > f_outcome = ""
      > f_blocker = ""
      > f_status = "crashed"
      > ```
    21.2.2. [call kverus-fix(target: file, verify: effective_verify_command, error_message: f_hint, out_path: f_blocker_path, mode: "explicit")] Delegate the safety-net repair
      + → f_resolution: resolution_report
      + → f_report: final_report
      + → f_rc: verify_rc
      + → f_outcome: repair_outcome
      + → f_blocker: blocker_summary_path
    21.2.3. [act] Mark the delegated success
      + → f_status % line
      > ```hop_python
      > f_status = "delegated"
      > ```
    21.2.4. [check final] Gate the delegated repair
      - ← f_status, f_report
      + → ok % bool
      + → note % text
      > ```hop_python
      > ok = f_status == "delegated" and len(f_report) > 0
      > note = "" if ok else "delegated repair did not produce a final report"
      > ```
    21.2.5. [on fail] Absorb the crashed repair
      21.2.5.1. [act] Keep the crash markers
        - ← f_outcome, f_report
        + → f_status % line
        + → f_outcome % line
        + → f_report % markdown
        > ```hop_python
        > f_status = "crashed"
        > f_outcome = f_outcome if len(f_outcome) > 0 else "crashed"
        > f_report = f_report if len(f_report) > 0 else "the repair worker crashed or was absorbed before producing a final report"
        > ```
  21.3. [act] Package the repair record
    - ← file, f_resolution, f_rc, f_outcome, f_report, f_blocker, f_status
    + → frec % FixRecord
    > ```hop_python
    > outcome_word = f_outcome if len(f_outcome) > 0 else "crashed"
    > frec = {"file": file, "repair_outcome": outcome_word, "verify_rc": f_rc, "resolution_report": f_resolution, "final_report": f_report, "blocker_summary_path": f_blocker}
    > ```

22. [act] Reconcile the repair records
  - ← fix_records, fix_files
  + → fix_reconciled % bool
  > ```hop_python
  > fix_reconciled = len(fix_records) == len(fix_files)
  > ```


23. [loop for-each file in converted_files, collect erec into eval_records] Evaluate each converted file and gate the bounded repairs
  - ← converted_files, effective_verify_command, spec_records, migrate_records, effective_out_dir, repair_tickets, repair_log, f_hint, f_blocker_path
  + → eval_records % [EvalRecord]
  23.1. [act] Re-pair the freshest failure context and the blocker path for this file
    - ← file, spec_records, migrate_records, effective_out_dir
    + → f_hint % markdown
    + → f_blocker_path % line
    > ```hop_python
    > spec_rows = [row["verify_report"] for row in spec_records if row["file"] == file]
    > mig_rows = [row["final_report"] for row in migrate_records if row["file"] == file]
    > f_hint = spec_rows[0] if len(spec_rows) > 0 else (mig_rows[0] if len(mig_rows) > 0 else "")
    > f_blocker_path = effective_out_dir + "fix-blockers/" + split(file, "/")[-1] + "-blocker-summary.md"
    > ```
  23.2. [subtask retry=0] Wrap the delegated evaluation
    - ← file, effective_verify_command
    + → e_report % markdown
    + → e_score % int
    + → e_status % line
    23.2.1. [act] Preset the evaluation sentinels
      + → e_report % markdown
      + → e_score % int
      + → e_status % line
      > ```hop_python
      > e_report = ""
      > e_score = -1
      > e_status = "crashed"
      > ```
    23.2.2. [call kverus-eval(target: file, intent_context: "")] Score this file's unstaged spec layer
      + → e_report: eval_report
      + → e_score: score_num
    23.2.3. [act] Mark the delegated success
      + → e_status % line
      > ```hop_python
      > e_status = "delegated"
      > ```
    23.2.4. [check final] Gate the delegated evaluation
      - ← e_status, e_report
      + → ok % bool
      + → note % text
      > ```hop_python
      > ok = e_status == "delegated" and len(e_report) > 0
      > note = "" if ok else "delegated evaluation did not produce a report"
      > ```
    23.2.5. [on fail] Absorb the crashed evaluation
      23.2.5.1. [act] Keep the crash markers
        - ← e_report
        + → e_status % line
        + → e_report % markdown
        > ```hop_python
        > e_status = "crashed"
        > e_report = e_report if len(e_report) > 0 else "the evaluation worker crashed or was absorbed before producing a report"
        > ```
  23.3. [act] Derive the score word
    - ← e_score
    + → score_word % line
    > ```hop_python
    > score_word = "failing" if e_score < 7 else "passing"
    > ```
  23.4. [loop for-each ticket in repair_tickets] Run the bounded repair rounds while the file fails
    - ← file, effective_verify_command, f_hint, f_blocker_path, repair_log, score_word, e_report, e_score, e_status
    23.4.1. [branch] Continue the repair ladder only while the file fails
      - ← score_word
      23.4.1.1. [case(score_word == "failing")] Run one repair round
        23.4.1.1.1. [subtask retry=0] Re-scaffold the file
          - ← file, effective_verify_command
          + → rs_edited % line
          + → rs_report % markdown
          + → rs_rc % int
          + → rs_status % line
          23.4.1.1.1.1. [act] Preset the re-scaffold sentinels
            + → rs_edited % line
            + → rs_report % markdown
            + → rs_rc % int
            + → rs_status % line
            > ```hop_python
            > rs_edited = ""
            > rs_report = ""
            > rs_rc = -1
            > rs_status = "crashed"
            > ```
          23.4.1.1.1.2. [call kverus-spec(target: file, verify: effective_verify_command, knowledge: "")] Re-run the scaffolding with fresh intent
            + → rs_edited: edited_target
            + → rs_report: verify_report
            + → rs_rc: verify_rc
          23.4.1.1.1.3. [act] Mark the re-scaffold success
            + → rs_status % line
            > ```hop_python
            > rs_status = "delegated"
            > ```
          23.4.1.1.1.4. [check final] Gate the re-scaffold
            - ← rs_status, rs_report
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = rs_status == "delegated" and len(rs_report) > 0
            > note = "" if ok else "re-scaffold did not produce a verification report"
            > ```
          23.4.1.1.1.5. [on fail] Absorb the crashed re-scaffold
            23.4.1.1.1.5.1. [act] Keep the crash markers
              - ← rs_status, rs_report
              + → rs_status % line
              + → rs_report % markdown
              > ```hop_python
              > rs_status = "crashed"
              > rs_report = rs_report if len(rs_report) > 0 else "the re-scaffold worker crashed or was absorbed before producing a verification report"
              > ```
        23.4.1.1.2. [act] Adopt the re-scaffold and refresh the repair pairing
          - ← rs_report, f_hint
          + → f_hint % markdown
          > ```hop_python
          > f_hint = rs_report if len(rs_report) > 0 else f_hint
          > ```
        23.4.1.1.3. [subtask retry=0] Re-run the repair
          - ← file, effective_verify_command, f_hint, f_blocker_path
          + → rf_resolution % markdown
          + → rf_report % markdown
          + → rf_rc % int
          + → rf_outcome % line
          + → rf_blocker % line
          + → rf_status % line
          23.4.1.1.3.1. [act] Preset the re-repair sentinels
            + → rf_resolution % markdown
            + → rf_report % markdown
            + → rf_rc % int
            + → rf_outcome % line
            + → rf_blocker % line
            + → rf_status % line
            > ```hop_python
            > rf_resolution = ""
            > rf_report = ""
            > rf_rc = -1
            > rf_outcome = ""
            > rf_blocker = ""
            > rf_status = "crashed"
            > ```
          23.4.1.1.3.2. [call kverus-fix(target: file, verify: effective_verify_command, error_message: f_hint, out_path: f_blocker_path, mode: "explicit")] Re-run the safety-net repair on the fresh scaffold
            + → rf_resolution: resolution_report
            + → rf_report: final_report
            + → rf_rc: verify_rc
            + → rf_outcome: repair_outcome
            + → rf_blocker: blocker_summary_path
          23.4.1.1.3.3. [act] Mark the re-repair success
            + → rf_status % line
            > ```hop_python
            > rf_status = "delegated"
            > ```
          23.4.1.1.3.4. [check final] Gate the re-repair
            - ← rf_status, rf_report
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = rf_status == "delegated" and len(rf_report) > 0
            > note = "" if ok else "re-repair did not produce a final report"
            > ```
          23.4.1.1.3.5. [on fail] Absorb the crashed re-repair
            23.4.1.1.3.5.1. [act] Keep the crash markers
              - ← rf_outcome, rf_report
              + → rf_status % line
              + → rf_outcome % line
              + → rf_report % markdown
              > ```hop_python
              > rf_status = "crashed"
              > rf_outcome = rf_outcome if len(rf_outcome) > 0 else "crashed"
              > rf_report = rf_report if len(rf_report) > 0 else "the re-repair worker crashed or was absorbed before producing a final report"
              > ```
        23.4.1.1.4. [subtask retry=0] Re-evaluate the file
          - ← file, effective_verify_command
          + → re_report % markdown
          + → re_score % int
          + → re_status % line
          23.4.1.1.4.1. [act] Preset the re-evaluation sentinels
            + → re_report % markdown
            + → re_score % int
            + → re_status % line
            > ```hop_python
            > re_report = ""
            > re_score = -1
            > re_status = "crashed"
            > ```
          23.4.1.1.4.2. [call kverus-eval(target: file, intent_context: "")] Re-score the repaired spec layer
            + → re_report: eval_report
            + → re_score: score_num
          23.4.1.1.4.3. [act] Mark the re-evaluation success
            + → re_status % line
            > ```hop_python
            > re_status = "delegated"
            > ```
          23.4.1.1.4.4. [check final] Gate the re-evaluation
            - ← re_status, re_report
            + → ok % bool
            + → note % text
            > ```hop_python
            > ok = re_status == "delegated" and len(re_report) > 0
            > note = "" if ok else "re-evaluation did not produce a report"
            > ```
          23.4.1.1.4.5. [on fail] Absorb the crashed re-evaluation
            23.4.1.1.4.5.1. [act] Keep the crash markers
              - ← re_report
              + → re_status % line
              + → re_report % markdown
              > ```hop_python
              > re_status = "crashed"
              > re_report = re_report if len(re_report) > 0 else "the re-evaluation worker crashed or was absorbed before producing a report"
              > ```
        23.4.1.1.5. [act] Adopt the re-evaluation and log the round
          - ← file, ticket, re_report, re_score, re_status, rf_status, repair_log
          + → e_report % markdown
          + → e_score % int
          + → e_status % line
          + → score_word % line
          + → repair_log % [line]
          > ```hop_python
          > e_report = re_report
          > e_score = re_score
          > e_status = re_status
          > score_word = "failing" if re_score < 7 else "passing"
          > repair_log = repair_log + [file + ": ticket " + str(ticket) + ": " + rf_status + " score " + str(re_score)]
          > ```
        23.4.1.1.6. [branch] Stop the bounded repairs when the file passes
          - ← score_word
          23.4.1.1.6.1. [case(score_word == "passing")] Stop the repair rounds
            23.4.1.1.6.1.1. [break] The file passed; leave the ticket loop
          23.4.1.1.6.2. [case(else)] Keep the next ticket
            23.4.1.1.6.2.1. [reason] The file still fails after this round. The next ticket runs while tickets remain, exactly the source's bounded retry ladder of at most two automatic rounds; the log line carries this round's repair status and score.
      23.4.1.2. [case(else)] The file already passes
        23.4.1.2.1. [break] The file passed on evaluation; leave the ticket loop
    23.4.2. [reason] The ticket loop closes: either a round lifted the score to the threshold and broke out, or both tickets ran and the file stays failing, routing to the disposition gate below.
  23.5. [branch] The exhausted-score disposition gate
    - ← score_word
    23.5.1. [case(score_word == "failing")] Ask the disposition after the two tickets
      23.5.1.1. [ask] This file's spec score stayed below 7 after the bounded repair rounds. Accept the spec as-is and continue the pipeline, answering accept, or stop the pipeline here so the spec can be edited manually, answering manual?
        + → e_answer % text
      23.5.1.2. [act] Classify the disposition
        - ← e_answer
        + → e_gate_choice % line
        > ```hop_python
        > e_gate_choice = "accept" if e_answer == "accept" else "stop"
        > ```
      23.5.1.3. [branch] Route the disposition
        - ← e_gate_choice
        23.5.1.3.1. [case(e_gate_choice == "accept")] Keep the spec and continue
          23.5.1.3.1.1. [reason] The user accepted this file's spec quality. The eval record carries the accept choice with the score, the repair log lines carry the rounds, and the cascade proceeds; after every converted file is evaluated the audit gate runs.
        23.5.1.3.2. [case(e_gate_choice == "stop")] Stop for manual spec editing
          23.5.1.3.2.1. [subtask retry=0] Run the manual-stop tail
            23.5.1.3.2.1.1. [subtask retry=0] Remove the snapshot root
              - ← orig_dir
              + → rm_rc % int
              + → rm_note % text
              + → rm_failed % bool
              23.5.1.3.2.1.1.1. [act] Remove the snapshot root
                - ← orig_dir
                + → rm_rc % int
                + → rm_note % text
                > ```hop_python
                > argv = ["rm", "-rf", orig_dir]
                > r = subprocess.run(argv, cwd:".", timeout:300)
                > rm_rc = r.returncode
                > rm_note = r.stdout + r.stderr
                > ```
              23.5.1.3.2.1.1.2. [check final] Seal the removal completion
                - ← rm_rc
                + → ok % bool
                + → note % text
                > ```hop_python
                > ok = rm_rc != -1
                > note = "" if ok else "snapshot removal did not return"
                > ```
              23.5.1.3.2.1.1.3. [on fail] Absorb the crashed removal
                23.5.1.3.2.1.1.3.1. [act] Mark the failed removal
                  - ← rm_rc, rm_note
                  + → rm_failed % bool
                  + → rm_note % text
                  > ```hop_python
                  > rm_failed = true
                  > rm_note = rm_note + " | removal absorbed with code " + str(rm_rc)
                  > ```
            23.5.1.3.2.1.2. [act] Mark the manual stop
              - ← file, e_score, converted_count, blocked_count, crashed_count, fix_count
              + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
              + → final_note % markdown
              > ```hop_python
              > pipeline_outcome = "manual_stopped"
              > final_note = "The user stopped the pipeline for manual spec editing on " + file + " (score " + str(e_score) + "). The tree is preserved for manual editing: migration layer staged, spec and repair edits unstaged. Counts at stop: converted " + str(converted_count) + ", blocked " + str(blocked_count) + ", crashed " + str(crashed_count) + ", repair-selected " + str(fix_count) + ". The reduced stop report is committed under the report root."
              > ```
            23.5.1.3.2.1.3. [act] Compose the reduced stop report
              - ← effective_target, discovery_mode, effective_verify_command, effective_out_dir, migrate_records, spec_records, fix_records, eval_records, repair_log, staging_state, warm_state, cache_status, rm_failed
              + → pipeline_report % markdown
              > ```hop_python
              > mig_rows = [row["file"] + ": " + row["migration_outcome"] for row in migrate_records]
              > spec_rows = [row["file"] + ": " + row["spec_status"] for row in spec_records]
              > fix_rows = [row["file"] + ": " + row["repair_outcome"] for row in fix_records]
              > eval_rows = [row["file"] + ": " + str(row["score_num"]) + " gate " + row["gate_choice"] for row in eval_records]
              > removal_word = "removed" if rm_failed == false else "removal-failed"
              > pipeline_report = "KVerus pipeline report\n\nDisposition: manual stop for manual spec editing\n\nTarget: " + effective_target + "\nMode: " + discovery_mode + "\nVerification command: " + effective_verify_command + "\nReport root: " + effective_out_dir + "\nStamp: " + str(now()) + "\n\n## Migration records\n" + join(mig_rows, "\n") + "\n\n## Scaffolding records\n" + join(spec_rows, "\n") + "\n\n## Repair records\n" + join(fix_rows, "\n") + "\n\n## Evaluation records\n" + join(eval_rows, "\n") + "\n\n## Repair log\n" + join(repair_log, "\n") + "\n\n## Cleanup states\nstaging: " + staging_state + "\nwarm-up: " + warm_state + "\ncache: " + cache_status + "\nsnapshot removal: " + removal_word
              > ```
            23.5.1.3.2.1.4. [check final] Seal the manual-stop report
              - ← pipeline_outcome, pipeline_report, summary_path
              + → ok % bool
              + → note % text
              > ```hop_python
              > ok = pipeline_outcome == "manual_stopped" and len(pipeline_report) > 0 and len(summary_path) > 0
              > note = "" if ok else "manual-stop report gate failed"
              > ```
            23.5.1.3.2.1.5. [commit] Write the reduced stop report
              - ← pipeline_report, summary_path
              + → written_summary_path % line
              > ```hop_python
              > written_summary_path = summary_path
              > write(path: summary_path, content: pipeline_report)
              > ```
            23.5.1.3.2.1.6. [exit] Carry the manual stop
              + → pipeline_outcome
              + → summary_path
              + → migrate_records
              + → spec_records
              + → fix_records
              + → eval_records
              + → audit_outcome
              + → audit_report_path
              + → audit_findings_path
              + → postprocess_report
              + → postprocess_outcome
              + → pp_final_checker_rc
              + → strip_report
              + → strip_outcome
              + → restored_originals
              + → final_note
      23.5.1.4. [reason] The disposition routed the file: accept folds the score and the round log into the eval record and the cascade continues; stop runs the manual-stop tail — snapshot removal duty, the marked disposition, the reduced committed report, and the exit with the tree deliberately preserved.
    23.5.2. [case(else)] The score passes
      23.5.2.1. [reason] The file reached the threshold of 7 on the first evaluation or on a repair round. No disposition is asked; the eval record carries the pass and the loop proceeds to the next converted file.
  23.6. [act] Package the evaluation record
    - ← file, e_report, e_score, e_gate_choice, repair_log
    + → erec % EvalRecord
    > ```hop_python
    > rounds = [line for line in repair_log if split(line, ":")[0] == file]
    > erec = {"file": file, "score_num": e_score, "eval_report": e_report, "gate_choice": e_gate_choice, "repair_rounds": rounds}
    > ```

24. [act] Derive the audit topology and the postprocess relay surface
  - ← discovery_mode, effective_target, file_list
  + → verus_dir % line
  + → target_csv % line
  > ```hop_python
  > parts = split(effective_target, "/")
  > n = len(parts)
  > parent = join(parts[0:n-1], "/") if n > 1 else "."
  > verus_dir = effective_target if discovery_mode == "directory" else parent
  > target_csv = effective_target if discovery_mode == "directory" else join(file_list, ",")
  > ```


25. [branch] Audit scope gate
  - ← converted_files
  25.1. [case(len(converted_files) > 0)] Delegate the semantic audit
    25.1.1. [subtask retry=0] Wrap the delegated audit
      - ← orig_dir, verus_dir, audit_dir
      + → a_outcome % line
      + → a_report_path % line
      + → a_findings_path % line
      + → a_rc % int
      + → a_note % markdown
      + → a_status % line
      25.1.1.1. [act] Preset the audit sentinels
        + → a_outcome % line
        + → a_report_path % line
        + → a_findings_path % line
        + → a_rc % int
        + → a_note % markdown
        + → a_status % line
        > ```hop_python
        > a_outcome = ""
        > a_report_path = ""
        > a_findings_path = ""
        > a_rc = -1
        > a_note = ""
        > a_status = "crashed"
        > ```
      25.1.1.2. [call kverus-semantic-audit(rust_dir: orig_dir, verus_dir: verus_dir, out_dir: audit_dir)] Delegate the behavior-preservation audit
        + → a_outcome: audit_outcome
        + → a_report_path: summary_path
        + → a_findings_path: findings_path
        + → a_rc: collector_rc
        + → a_note: audit_note
      25.1.1.3. [act] Mark the delegated success
        + → a_status % line
        > ```hop_python
        > a_status = "delegated"
        > ```
      25.1.1.4. [check final] Gate the delegated audit
        - ← a_status, a_outcome
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = a_status == "delegated" and len(a_outcome) > 0
        > note = "" if ok else "delegated audit returned no outcome word"
        > ```
      25.1.1.5. [on fail] Absorb the crashed audit
        25.1.1.5.1. [act] Keep the crash markers
          - ← a_outcome, a_note
          + → a_outcome % line
          + → a_note % markdown
          > ```hop_python
          > a_outcome = a_outcome if len(a_outcome) > 0 else "crashed"
          > a_note = a_note if len(a_note) > 0 else "the audit worker crashed or was absorbed before producing its report"
          > ```
    25.1.2. [act] Relay the audit outputs and machine-gate the severity
      - ← a_outcome, a_report_path, a_findings_path, a_rc, a_note
      + → audit_outcome % line
      + → audit_report_path % line
      + → audit_findings_path % line
      + → audit_collector_rc % int
      + → audit_note % markdown
      + → has_high % bool
      + → high_count % int
      + → high_sample % [line]
      + → audit_gate_word % line
      > ```hop_python
      > audit_outcome = a_outcome if len(a_outcome) > 0 else "crashed"
      > audit_report_path = a_report_path
      > audit_findings_path = a_findings_path
      > audit_collector_rc = a_rc
      > audit_note = a_note
      > raw = read(path: audit_findings_path) if exists(path: audit_findings_path) else ""
      > entries = parse_json(raw) if raw else []
      > guarded = entries if len(entries) > 0 else []
      > highs = [item for item in guarded if item["classification"] == "semantic-change" and item["severity"] == "high"]
      > has_high = len(highs) > 0
      > high_count = len(highs)
      > high_sample = [item["path"] for item in highs][0:3]
      > audit_gate_word = "completed-high" if (audit_outcome == "completed" and has_high) else ("completed-clean" if audit_outcome == "completed" else audit_outcome)
      > ```
  25.2. [case(else)] Record the empty-scope skip
    25.2.1. [act] Mark the audit skip
      + → audit_outcome % line
      + → audit_gate_word % line
      > ```hop_python
      > audit_outcome = "skipped-empty"
      > audit_gate_word = "skipped"
      > ```
    25.2.2. [reason] No file reached a converted state, so the audit callee has nothing to pair and the run relays the skip word. The cascade proceeds to the postprocess scope gate, which also skips on this route.

26. [branch] Audit quality-gate routing
  - ← audit_gate_word, high_count, high_sample
  26.1. [case(audit_gate_word == "completed-high")] Pause at the critical-findings gate
  26.1.1. [reason] The audit completed and the machine severity gate found high-severity semantic-change findings; the sampled paths are printed here from high_sample for the user's decision.
    26.1.2. [ask] The semantic audit classified high-severity findings as behavior-changing. Continue the pipeline with the findings on record, answering continue, or abort with full restore of the originals, answering abort?
      + → audit_answer % text
    26.1.3. [act] Classify the audit decision
      - ← audit_answer
      + → audit_choice % line
      > ```hop_python
      > audit_choice = "continue" if audit_answer == "continue" else "abort"
      > ```
  26.2. [case(audit_gate_word == "crashed")] Pause at the crashed-audit gate
    26.2.1. [reason] The audit delegation crashed or was absorbed before producing an outcome word. The source's honest-stop form applies: the user decides whether to continue without an audit or to abort with restore.
    26.2.2. [ask] The semantic audit delegation crashed before producing an outcome. Continue without an audit on record, answering continue, or abort with full restore of the originals, answering abort?
      + → audit_answer % text
    26.2.3. [act] Classify the audit decision
      - ← audit_answer
      + → audit_choice % line
      > ```hop_python
      > audit_choice = "continue" if audit_answer == "continue" else "abort"
      > ```
  26.3. [case(audit_gate_word == "collector_failed")] Proceed with the collector failure on record
    26.3.1. [reason] The audit callee completed its classification work while its diff collector failed; its summary and partial findings are relayed, and the pipeline proceeds with the failure disclosed in the report.
  26.4. [case(else)] Proceed with a clean or skipped audit
    26.4.1. [reason] The audit completed with no high-severity semantic change, or the scope was empty and the skip word was relayed. The cascade proceeds to the postprocess bookend.

27. [branch] Audit decision route
  - ← audit_choice
  27.1. [case(audit_choice == "abort")] Restore, unstage, remove, and stop
    27.1.1. [subtask retry=0] Run the audit-abort tail
      27.1.1.1. [subtask retry=0] Restore the snapshotted originals
        - ← orig_dir
        + → restore_rc % int
        + → restore_note % text
        + → restore_failed % bool
        27.1.1.1.1. [act] Restore the originals from the snapshot root
          - ← orig_dir
          + → restore_rc % int
          + → restore_note % text
          > ```hop_python
          > argv = ["python3", spec_dir("scripts/snapshot_copy.py"), "--restore", orig_dir]
          > r = subprocess.run(argv, cwd:".", timeout:300)
          > restore_rc = r.returncode
          > restore_note = r.stdout + r.stderr
          > ```
        27.1.1.1.2. [check final] Seal the restore completion
          - ← restore_rc
          + → ok % bool
          + → note % text
          > ```hop_python
          > ok = restore_rc != -1
          > note = "" if ok else "restore did not return"
          > ```
        27.1.1.1.3. [on fail] Absorb the crashed restore
          27.1.1.1.3.1. [act] Mark the failed restore
            - ← restore_rc, restore_note
            + → restore_failed % bool
            + → restore_note % text
            > ```hop_python
            > restore_failed = true
            > restore_note = restore_note + " | restore absorbed with code " + str(restore_rc)
            > ```
      27.1.1.2. [subtask retry=0] Unstage the staged migration layer
        - ← file_list
        + → unstage_rc % int
        + → unstage_note % text
        + → unstage_failed % bool
        27.1.1.2.1. [act] Unstage the discovered list
          - ← file_list
          + → unstage_rc % int
          + → unstage_note % text
          > ```hop_python
          > argv = ["git", "restore", "--staged", "--"] + file_list
          > r = subprocess.run(argv, cwd:".", timeout:300)
          > unstage_rc = r.returncode
          > unstage_note = r.stdout + r.stderr
          > ```
        27.1.1.2.2. [check final] Seal the unstage completion
          - ← unstage_rc
          + → ok % bool
          + → note % text
          > ```hop_python
          > ok = unstage_rc != -1
          > note = "" if ok else "unstage did not return"
          > ```
        27.1.1.2.3. [on fail] Absorb the crashed unstage
          27.1.1.2.3.1. [act] Mark the failed unstage
            - ← unstage_rc, unstage_note
            + → unstage_failed % bool
            + → unstage_note % text
            > ```hop_python
            > unstage_failed = true
            > unstage_note = unstage_note + " | unstage absorbed with code " + str(unstage_rc)
            > ```
      27.1.1.3. [subtask retry=0] Remove the snapshot root
        - ← orig_dir
        + → rm_rc % int
        + → rm_note % text
        + → rm_failed % bool
        27.1.1.3.1. [act] Remove the snapshot root
          - ← orig_dir
          + → rm_rc % int
          + → rm_note % text
          > ```hop_python
          > argv = ["rm", "-rf", orig_dir]
          > r = subprocess.run(argv, cwd:".", timeout:300)
          > rm_rc = r.returncode
          > rm_note = r.stdout + r.stderr
          > ```
        27.1.1.3.2. [check final] Seal the removal completion
          - ← rm_rc
          + → ok % bool
          + → note % text
          > ```hop_python
          > ok = rm_rc != -1
          > note = "" if ok else "snapshot removal did not return"
          > ```
        27.1.1.3.3. [on fail] Absorb the crashed removal
          27.1.1.3.3.1. [act] Mark the failed removal
            - ← rm_rc, rm_note
            + → rm_failed % bool
            + → rm_note % text
            > ```hop_python
            > rm_failed = true
            > rm_note = rm_note + " | removal absorbed with code " + str(rm_rc)
            > ```
      27.1.1.4. [act] Mark the abort
        - ← restore_failed, unstage_failed, rm_failed, converted_count, blocked_count, crashed_count, fix_count, high_count, high_sample, audit_answer
        + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
        + → restored_originals % bool
        + → final_note % markdown
        > ```hop_python
        > pipeline_outcome = "aborted"
        > restored_originals = restore_failed == false
        > restore_word = "restored" if restore_failed == false else "restore-failed"
        > unstage_word = "unstaged" if unstage_failed == false else "unstage-failed"
        > removal_word = "removed" if rm_failed == false else "removal-failed"
        > final_note = "The user aborted at the audit quality gate (answer: " + audit_answer + "). Duties: originals " + restore_word + ", staged layer " + unstage_word + ", snapshot root " + removal_word + ". Counts at abort: converted " + str(converted_count) + ", blocked " + str(blocked_count) + ", crashed " + str(crashed_count) + ", repair-selected " + str(fix_count) + ", high-severity findings " + str(high_count) + ". Sample: " + join(high_sample, ", ") + ". The reduced stop report is committed under the report root."
        > ```
      27.1.1.5. [act] Compose the reduced stop report
        - ← effective_target, discovery_mode, effective_verify_command, effective_out_dir, migrate_records, spec_records, fix_records, eval_records, repair_log, staging_state, warm_state, cache_status, unstage_failed, rm_failed, audit_outcome, audit_answer, high_count, high_sample, restored_originals
        + → pipeline_report % markdown
        > ```hop_python
        > mig_rows = [row["file"] + ": " + row["migration_outcome"] for row in migrate_records]
        > spec_rows = [row["file"] + ": " + row["spec_status"] for row in spec_records]
        > fix_rows = [row["file"] + ": " + row["repair_outcome"] for row in fix_records]
        > eval_rows = [row["file"] + ": " + str(row["score_num"]) + " gate " + row["gate_choice"] for row in eval_records]
        > unstage_word = "unstaged" if unstage_failed == false else "unstage-failed"
        > removal_word = "removed" if rm_failed == false else "removal-failed"
        > pipeline_report = "KVerus pipeline report\n\nDisposition: aborted at the audit quality gate; originals restored\n\nTarget: " + effective_target + "\nMode: " + discovery_mode + "\nVerification command: " + effective_verify_command + "\nReport root: " + effective_out_dir + "\nStamp: " + str(now()) + "\n\n## Migration records\n" + join(mig_rows, "\n") + "\n\n## Scaffolding records\n" + join(spec_rows, "\n") + "\n\n## Repair records\n" + join(fix_rows, "\n") + "\n\n## Evaluation records\n" + join(eval_rows, "\n") + "\n\n## Repair log\n" + join(repair_log, "\n") + "\n\n## Audit disposition\nanswer: " + audit_answer + "\noutcome: " + audit_outcome + "\nhigh-severity findings: " + str(high_count) + "\nsample: " + join(high_sample, ", ") + "\n\n## Cleanup states\nrestored: " + ("yes" if restored_originals else "no") + "\nunstaged: " + unstage_word + "\nsnapshot removal: " + removal_word + "\nwarm-up: " + warm_state + "\ncache: " + cache_status + "\nstaging: " + staging_state
        > ```
      27.1.1.6. [check final] Seal the abort tail
        - ← pipeline_outcome, pipeline_report, summary_path
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = pipeline_outcome == "aborted" and len(pipeline_report) > 0 and len(summary_path) > 0
        > note = "" if ok else "abort-tail report gate failed"
        > ```
      27.1.1.7. [commit] Write the reduced stop report
        - ← pipeline_report, summary_path
        + → written_summary_path % line
        > ```hop_python
        > written_summary_path = summary_path
        > write(path: summary_path, content: pipeline_report)
        > ```
      27.1.1.8. [exit] Carry the abort
        + → pipeline_outcome
        + → summary_path
        + → migrate_records
        + → spec_records
        + → fix_records
        + → eval_records
        + → audit_outcome
        + → audit_report_path
        + → audit_findings_path
        + → postprocess_report
        + → postprocess_outcome
        + → pp_final_checker_rc
        + → strip_report
        + → strip_outcome
        + → restored_originals
        + → final_note
  27.2. [case(else)] Carry the audit decision forward
    27.2.1. [reason] The audit choice was continue, or no choice was asked (clean, skipped, or collector-failed routes). The pipeline proceeds to the postprocess bookend with the audit relays on record.

28. [branch] Postprocess scope gate
  - ← file_list
  28.1. [case(len(file_list) > 0)] Delegate the closing postprocess
    28.1.1. [subtask retry=0] Wrap the delegated postprocess
      - ← target_csv, effective_verify_command
      + → postprocess_report % markdown
      + → postprocess_outcome % line
      + → pp_final_checker_rc % int
      + → refresh_rc % int
      + → checker_rc % int
      + → strip_report % markdown
      + → strip_outcome % line
      + → pp_status % line
      28.1.1.1. [act] Preset the postprocess sentinels
        + → postprocess_report % markdown
        + → postprocess_outcome % line
        + → pp_final_checker_rc % int
        + → refresh_rc % int
        + → checker_rc % int
        + → strip_report % markdown
        + → strip_outcome % line
        + → pp_status % line
        > ```hop_python
        > postprocess_report = ""
        > postprocess_outcome = ""
        > pp_final_checker_rc = -1
        > refresh_rc = -1
        > checker_rc = -1
        > strip_report = ""
        > strip_outcome = ""
        > pp_status = "crashed"
        > ```
      28.1.1.2. [call kverus-postprocess(base: "", target_paths: target_csv, verify_command: effective_verify_command, format_command: "", rule_repo: "", blocked_paths: "", generated_paths: "", simplify_scope: "", skip_simplify: "")] Delegate the closing bookend pass
        + → postprocess_report: postprocess_report
        + → postprocess_outcome: postprocess_outcome
        + → pp_final_checker_rc: final_checker_rc
        + → refresh_rc: refresh_rc
        + → checker_rc: checker_rc
        + → strip_report: strip_report
        + → strip_outcome: strip_outcome
      28.1.1.3. [act] Mark the delegated success
        + → pp_status % line
        > ```hop_python
        > pp_status = "delegated"
        > ```
      28.1.1.4. [check final] Gate the delegated postprocess
        - ← pp_status, postprocess_report, postprocess_outcome
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = pp_status == "delegated" and len(postprocess_report) > 0 and len(postprocess_outcome) > 0
        > note = "" if ok else "delegated postprocess did not produce its report and outcome"
        > ```
      28.1.1.5. [on fail] Absorb the crashed postprocess
        28.1.1.5.1. [act] Keep the crash markers
          - ← postprocess_report, postprocess_outcome, strip_outcome
          + → postprocess_outcome % line
          + → strip_outcome % line
          + → postprocess_report % markdown
          > ```hop_python
          > postprocess_outcome = postprocess_outcome if len(postprocess_outcome) > 0 else "crashed"
          > strip_outcome = strip_outcome if len(strip_outcome) > 0 else "crashed"
          > postprocess_report = postprocess_report if len(postprocess_report) > 0 else "the postprocess worker crashed or was absorbed before producing its report"
          > ```
    28.1.2. [reason] The bookend callee ran over the relayed target surface — the discovered directory itself in directory mode, the comma-joined discovered list in file mode — with the pipeline verification command and the default empty optional relays. Its five-element report, closing checker code, refresh and checker codes, and strip pair ride as the run's relays.
  28.2. [case(else)] Record the empty-scope skip
    28.2.1. [act] Mark the postprocess skip
      + → postprocess_outcome % line
      > ```hop_python
      > postprocess_outcome = "skipped-empty"
      > ```
    28.2.2. [reason] The work list was empty, so the bookend pass has no target surface; the skip word is relayed and the report composes with the empty-scope disclosure.

29. [branch] Snapshot-root removal gate
  - ← orig_dir
  29.1. [case(len(orig_dir) > 0)] Remove the snapshot root
    29.1.1. [subtask retry=0] Remove the snapshot root
      - ← orig_dir
      + → rm_rc % int
      + → rm_note % text
      + → rm_failed % bool
      29.1.1.1. [act] Remove the snapshot root
        - ← orig_dir
        + → rm_rc % int
        + → rm_note % text
        > ```hop_python
        > argv = ["rm", "-rf", orig_dir]
        > r = subprocess.run(argv, cwd:".", timeout:300)
        > rm_rc = r.returncode
        > rm_note = r.stdout + r.stderr
        > ```
      29.1.1.2. [check final] Seal the removal completion
        - ← rm_rc
        + → ok % bool
        + → note % text
        > ```hop_python
        > ok = rm_rc != -1
        > note = "" if ok else "snapshot removal did not return"
        > ```
      29.1.1.3. [on fail] Absorb the crashed removal
        29.1.1.3.1. [act] Mark the failed removal
          - ← rm_rc, rm_note
          + → rm_failed % bool
          + → rm_note % text
          > ```hop_python
          > rm_failed = true
          > rm_note = rm_note + " | removal absorbed with code " + str(rm_rc)
          > ```
    29.1.2. [act] Record the removal state
      - ← rm_failed
      + → rm_state % line
      > ```hop_python
      > rm_state = "removed" if rm_failed == false else "removal-failed"
      > ```
  29.2. [case(else)] Record the absent snapshot root
    29.2.1. [act] Mark the absent root
      + → rm_state % line
      > ```hop_python
      > rm_state = "absent"
      > ```
    29.2.2. [reason] No snapshot root exists on this route; the removal gate records the absent-root word for the cleanup section.

30. [act] Mark completion and compose the nine-section pipeline report
  - ← effective_target, discovery_mode, effective_verify_command, effective_out_dir, summary_path, file_list, migrate_records, spec_records, fix_records, eval_records, audit_outcome, audit_answer, audit_gate_word, has_high, high_count, high_sample, postprocess_outcome, pp_final_checker_rc, refresh_rc, checker_rc, strip_outcome, strip_report, staging_state, warm_state, cache_status
  + → pipeline_outcome % enum(completed, manual_stopped, aborted, halted)
  + → pipeline_report % markdown
  + → final_note % markdown
  > ```hop_python
  > pipeline_outcome = "completed"
  > mig_rows = [row["file"] + ": " + row["migration_outcome"] + " verify rc " + str(row["verify_rc"]) for row in migrate_records]
  > spec_rows = [row["file"] + ": " + row["spec_status"] + " verify rc " + str(row["verify_rc"]) for row in spec_records]
  > fix_rows = [row["file"] + ": " + row["repair_outcome"] + " verify rc " + str(row["verify_rc"]) for row in fix_records]
  > eval_rows = [row["file"] + ": " + str(row["score_num"]) + " gate " + row["gate_choice"] for row in eval_records]
  > failing_files = [row["file"] for row in eval_records if row["score_num"] < 7]
  > eval_note = "failing files: " + join(failing_files, ", ") if len(failing_files) > 0 else "failing files: none"
  > audit_rows = "outcome " + audit_outcome + "; high-severity findings " + str(high_count) + "; sample " + join(high_sample, ", ") + "; gate " + audit_gate_word + "; answer " + audit_answer
  > mig_bad = [row["file"] + " (" + row["migration_outcome"] + ")" for row in migrate_records if row["migration_outcome"] != "converted"]
  > spec_bad = [row["file"] + " (" + row["spec_status"] + ")" for row in spec_records if row["spec_status"] == "crashed" or row["verify_rc"] != 0]
  > fix_bad = [row["file"] + " (" + row["repair_outcome"] + ")" for row in fix_records if row["repair_outcome"] == "crashed" or row["verify_rc"] != 0]
  > eval_bad = [row["file"] + " (score " + str(row["score_num"]) + ")" for row in eval_records if row["score_num"] < 7]
  > blocker_rows = mig_bad + spec_bad + fix_bad + eval_bad
  > blocked_line = join(blocker_rows, "\n") if len(blocker_rows) > 0 else "none"
  > base_next = ["verify the final tree with the verification command", "review and commit the staged migration layer"]
  > audit_next = ["inspect the audit summary and findings under the report root"] if audit_outcome == "completed" else []
  > high_next = ["triage the high-severity semantic findings before committing anything"] if has_high else []
  > accept_next = ["revisit specs accepted below the quality threshold"] if len([row for row in eval_records if row["gate_choice"] == "accept"]) > 0 else []
  > strip_next = ["review the delegated strip report"] if len(strip_report) > 0 else []
  > next_steps = base_next + audit_next + high_next + accept_next + strip_next
  > pipeline_report = "KVerus pipeline report\n\n## 1. Pipeline Configuration\nTarget: " + effective_target + "\nMode: " + discovery_mode + "\nWork list: " + str(len(file_list)) + " file(s)\nVerification command: " + effective_verify_command + "\nReport root: " + effective_out_dir + "\nStamp: " + str(now()) + "\n\n## 2. Phase 1 Migrate\n" + join(mig_rows, "\n") + "\n\n## 3. Phase 3 Spec\n" + join(spec_rows, "\n") + "\n\n## 4. Phase 4 Fix\n" + join(fix_rows, "\n") + "\n\n## 5. Phase 5 Eval\n" + join(eval_rows, "\n") + "\n" + eval_note + "\n\n## 6. Phase 6 Audit\n" + audit_rows + "\n\n## 7. Phase 7 Postprocess\noutcome " + postprocess_outcome + "; final checker rc " + str(pp_final_checker_rc) + "; refresh rc " + str(refresh_rc) + "; checker rc " + str(checker_rc) + "; strip " + strip_outcome + "\n\n## 8. Blockers and Warnings\n" + blocked_line + "\nwarm-up: " + warm_state + "; cache: " + cache_status + "; staging: " + staging_state + "\n\n## 9. Suggested Next Steps\n" + join(next_steps, "\n")
  > final_note = "pipeline completed; report committed at " + summary_path
  > ```

31. [reason] Close-out narrative — the cascade is complete: how many files were discovered and how the migration, scaffolding, repair, and evaluation records classify them; which audit gate word routed phase 6 and how many high-severity findings were sampled; which postprocess outcome and strip verdict closed the bookends; and where the committed nine-section report lives. The record lists above carry every per-file row verbatim, so nothing the phases produced is dropped from the instance.

32. [subtask retry=0] Gate the completion report
  32.1. [check final] Seal the completion gate
    - ← pipeline_outcome, pipeline_report, summary_path, migrate_records, spec_records, fix_records, eval_records, file_list, converted_files, migrate_reconciled, spec_reconciled, fix_reconciled, fix_count
    + → ok % bool
    + → note % text
    > ```hop_python
    > records_ok = (len(migrate_records) == len(file_list)) and (len(spec_records) == len(converted_files)) and (len(fix_records) == fix_count) and (len(eval_records) == len(converted_files))
    > flags_ok = migrate_reconciled and spec_reconciled and fix_reconciled
    > ok = pipeline_outcome == "completed" and len(pipeline_report) > 0 and len(summary_path) > 0 and records_ok and flags_ok
    > note = "" if ok else "completion gate failed: report or reconciliation incomplete"
    > ```

33. [commit] Write the pipeline summary report
  - ← pipeline_report, summary_path
  + → written_summary_path % line
  > ```hop_python
  > written_summary_path = summary_path
  > write(path: summary_path, content: pipeline_report)
  > ```

34. [exit] Carry the completed pipeline
  + → pipeline_outcome
  + → summary_path
  + → migrate_records
  + → spec_records
  + → fix_records
  + → eval_records
  + → audit_outcome
  + → audit_report_path
  + → audit_findings_path
  + → postprocess_report
  + → postprocess_outcome
  + → pp_final_checker_rc
  + → strip_report
  + → strip_outcome
  + → restored_originals
  + → final_note
