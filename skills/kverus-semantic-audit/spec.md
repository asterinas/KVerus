# Spec: Audit a Rust-to-Verus migration for executable-semantics differences and write the audit reports
Id: kverus-semantic-audit
Goal: Compare each original Rust source file with its migrated Verus counterpart, classify every executable-code difference as semantic-change, likely-equivalent, or uncertain — conservatively and concretely — and write the required summary and machine-readable findings files into the output directory, with optional per-file detail reports for the serious classifications.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they are the background against which executable-semantics differences are judged:
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
- Scope: this is a semantic audit of a completed migration — compare paired Rust and Verus files and report where executable behavior appears to differ. It is not a style review and not a proof review; ignore differences that only affect Verus specifications, proofs, ghost state, attributes, wrappers, or verifier annotations unless they also change executable behavior.
- Invocation form (from the source skill): `$kverus-semantic-audit rust_dir=<path> verus_dir=<path> out_dir=<path>`. All three inputs are required — when any is missing, ask for the missing value and stop, which the engine expresses as the three blocking ask gates below (asked sequentially; the run stops at the first unmet one).
- Collector invocation (source workflow step 1, engine-mapped): the source runs `. "$AGENT_DIR/kverus.env" && "$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-semantic-audit/scripts/collect_exec_diffs.py" --rust-dir <rust_dir> --verus-dir <verus_dir> --out-dir <out_dir>`; this spec's deterministic channel runs the same bundled script with the same three flags via the whitelisted python3 prefix and `spec_dir("scripts/collect_exec_diffs.py")` with the three resolved directories — the env sourcing and interpreter selection are the deployed script's own entry bootstrap (L1 ruling), so the spec passes no environment itself. The deployed skills tree must carry the script, and the env file with its tree-sitter-verus venv must exist at deploy time (deployment prerequisite).
- Compatibility precondition (source frontmatter): a local workspace containing paired Rust and Verus .rs files is required. Files missing on one side surface as `missing-rust` / `missing-verus` reports — never silent skips — so unpaired workspaces yield findings, not crashes.
- Collector run timeout is 300 seconds (temporary value: the source skill gives no bound; recorded in the translation ledger). The spec's deterministic command surface is exactly python3 (the collector); requires_commands declares it.
- File-writing ruling (L33 family): the two required audit reports land via the [commit] step with paths pinned from the resolved output directory; the optional per-file detail reports (a dynamic, classification-driven set under semantic_reports/) are written executor-side in an act-free step — a commit body cannot hold a dynamic file set. The collector's own intermediate writes (audit_index.json, file_diffs/) are the bundled tool's internal business, presented as a plain deterministic act.
- Ambiguity inspection uses executor-side exploration (rg, sed, nearby dependencies) inside the cognitive act-free steps — this is the reviewing executor's own tool use, not a command through this spec's deterministic subprocess channel, so those tools are not in the approved-commands list.
- Pairing policy (from the source skill): default pairing is by relative path under the two directories; a file missing on either side is reported as `missing-rust` or `missing-verus`, never silently ignored; when the migration changed file names or layout, infer likely pairs only when obvious and record the inference in the report.
- Conservative classification: `uncertain` instead of guessing whenever macro expansion, cfg flags, external dependencies, or large helper rewrites block a confident judgment; and a difference is never marked safe merely because the Verus code verifies.
- Report discipline (from the source skill): the summary file carries, in order, input paths and timestamp; totals (matched, missing, exec-diff, semantic-change, likely-equivalent, uncertain); token-diff totals when present in the index; the findings table with relative path, classification, severity, comment status, and short reason (comment status required for removed or stubbed functions/impls); the missing-file list; skipped generated/vendor notes. The findings JSON carries the per-file field set including severity (`high`/`medium`/`low`/`none`) and comment_status semantics (`commented`/`deleted`/`partial`, omit-or-null when nothing was removed or stubbed). Detail reports are written for each semantic-change or uncertain file.
- Failure honesty: when the bundled collector exits non-zero, the run stops with the collector's own output in the exit note and empty path sentinels — no reports are fabricated and the output directory is not invented (L13 family).

Inputs:
- rust_dir % line  # directory holding the original Rust sources; empty means missing and triggers the ask gate
- verus_dir % line  # directory holding the migrated Verus counterpart files; empty means missing and triggers the ask gate
- out_dir % line  # directory the collector and this spec write audit artifacts into; empty means missing and triggers the ask gate

Outputs:
- summary_path % line  # path of the written semantic_audit_summary.md; empty sentinel when the collector failed
- findings_path % line  # path of the written semantic_audit_findings.json; empty sentinel when the collector failed
- audit_outcome % enum(completed, collector_failed)  # completed: reports written; collector_failed: the bundled collector exited non-zero
- collector_rc % int  # exit code of the bundled collector run
- audit_note % text  # collector-failure notice carrying the collector output; empty on the completed path

Config:
  requires_commands: [python3]
## 已批准命令
- python3

## Steps
1. [act] Test which invocation inputs are present
  - ← rust_dir, verus_dir, out_dir
  + → has_rust_dir % bool  # true when the Rust source directory input was supplied
  + → has_verus_dir % bool  # true when the Verus counterpart directory input was supplied
  + → has_out_dir % bool  # true when the output directory input was supplied
  > Mechanical presence tests on the three required invocation inputs.
  > ```hop_python
  > has_rust_dir = len(rust_dir) > 0
  > has_verus_dir = len(verus_dir) > 0
  > has_out_dir = len(out_dir) > 0
  > ```
2. [branch] Resolve the Rust source directory
  - ← has_rust_dir
  + → effective_rust_dir % line  # the Rust source directory the audit runs against, supplied or asked
  2.1. [case(has_rust_dir)] Carry the given directory
    - ← rust_dir
    + → effective_rust_dir
    2.1.1. [act] Carry the Rust source directory through
      - ← rust_dir
      + → effective_rust_dir
      > ```hop_python
      > effective_rust_dir = rust_dir
      > ```
  2.2. [case(has_rust_dir == false)] Ask for the directory and stop until answered
    2.2.1. [ask] Supply the Rust source directory
      + → rust_dir_answer % line  # user-supplied path to the original Rust sources folder
      > The invocation is missing its required Rust source directory. Ask for the path to the folder holding the original Rust sources. Execution resumes only with the answer — the source skill's ask-and-stop.
    2.2.2. [act] Record the asked directory
      - ← rust_dir_answer
      + → effective_rust_dir
      > ```hop_python
      > effective_rust_dir = rust_dir_answer
      > ```
3. [branch] Resolve the Verus counterpart directory
  - ← has_verus_dir
  + → effective_verus_dir % line  # the Verus counterpart directory the audit runs against, supplied or asked
  3.1. [case(has_verus_dir)] Carry the given directory
    - ← verus_dir
    + → effective_verus_dir
    3.1.1. [act] Carry the Verus directory through
      - ← verus_dir
      + → effective_verus_dir
      > ```hop_python
      > effective_verus_dir = verus_dir
      > ```
  3.2. [case(has_verus_dir == false)] Ask for the directory and stop until answered
    3.2.1. [ask] Supply the Verus counterpart directory
      + → verus_dir_answer % line  # user-supplied path to the migrated Verus counterparts folder
      > The invocation is missing its required Verus counterpart directory. Ask for the path to the folder holding the migrated Verus files. Execution resumes only with the answer — the source skill's ask-and-stop.
    3.2.2. [act] Record the asked directory
      - ← verus_dir_answer
      + → effective_verus_dir
      > ```hop_python
      > effective_verus_dir = verus_dir_answer
      > ```
4. [branch] Resolve the output directory
  - ← has_out_dir
  + → effective_out_dir % line  # the audit output directory artifacts are written under, supplied or asked
  4.1. [case(has_out_dir)] Carry the given directory
    - ← out_dir
    + → effective_out_dir
    4.1.1. [act] Carry the output directory through
      - ← out_dir
      + → effective_out_dir
      > ```hop_python
      > effective_out_dir = out_dir
      > ```
  4.2. [case(has_out_dir == false)] Ask for the directory and stop until answered
    4.2.1. [ask] Supply the audit output directory
      + → out_dir_answer % line  # user-supplied path for audit artifacts
      > The invocation is missing its required output directory. Ask for the directory the audit artifacts should be written under. Execution resumes only with the answer — the source skill's ask-and-stop.
    4.2.2. [act] Record the asked directory
      - ← out_dir_answer
      + → effective_out_dir
      > ```hop_python
      > effective_out_dir = out_dir_answer
      > ```
5. [act] Run the bundled diff collector
  - ← effective_rust_dir, effective_verus_dir, effective_out_dir
  + → collector_rc % int  # exit code of the collector run
  + → collector_report % text  # merged stdout and stderr of the collector run
  > Deterministic collection: run the bundled collector once with the three resolved directories, through the whitelisted python3 prefix. The script self-bootstraps its environment (see Constraints); streams merge; the exit code is the collector verdict that the next step routes on.
  > ```hop_python
  > argv = ["python3", spec_dir("scripts/collect_exec_diffs.py"), "--rust-dir", effective_rust_dir, "--verus-dir", effective_verus_dir, "--out-dir", effective_out_dir]
  > r = subprocess.run(argv, cwd: ".", timeout: 300)
  > collector_rc = r.returncode
  > collector_report = r.stdout + r.stderr
  > ```
6. [branch] Route by the collector verdict
  - ← collector_rc
  + → summary_path % line  # path of the written semantic_audit_summary.md, or the empty sentinel
  + → findings_path % line  # path of the written semantic_audit_findings.json, or the empty sentinel
  + → audit_outcome % enum(completed, collector_failed)
  + → audit_note % text  # collector-failure notice; empty on the completed path
  6.1. [case(collector_rc == 0)] Audit the paired files
    - ← effective_out_dir
    + → summary_path
    + → findings_path
    + → audit_outcome
    + → audit_note
    6.1.1. [subtask] Audit matched pairs and compose the reports
      + → findings_json % yaml  # the per-file findings records, one entry per reviewed file with the full field set
      + → audit_summary % markdown  # the six-item audit summary document
      6.1.1.1. [act free] Read the audit index and triage key tokens
        + → index_digest % yaml  # matched files, missing-rust and missing-verus lists, per-file key_token_changes and has_exec_diff flags, pairing inferences, skipped-files notes
        > Read the audit index in the output directory first — it lists matched files, missing files, files with normalized executable-code diffs, and files with critical declaration-token diffs. Enumerate those four sets. Pair by relative path by default; record any obvious layout-change pair inferences; note skipped generated/vendor files. Before any full diff is read, capture each entry's key-token changes — critical API and safety tokens such as unsafe, visibility modifiers, public modules and re-exports, async, const fn, extern, ABI strings, static mut.
        > [[kverus-semantic-audit-knowledge#Paired-file collection and index reading]]
      6.1.1.2. [act free] Classify the executable differences per file
        - ← index_digest
        + → findings_json % yaml  # one record per reviewed file: path, rust_path, verus_path, classification, severity, comment_status, summary, evidence, key_token_changes, recommended_action
        > For each file the index flags with an executable diff, read the generated markdown diff under the output directory's file_diffs folder, including its Key Token Changes section when present. Inspect the original files directly whenever a diff is ambiguous. Classify every executable difference conservatively per the scope lists and heuristics — semantic-change, likely-equivalent, or uncertain — never assuming a token change is safe merely because the verified code proves, and never guessing past macro expansion, cfg flags, external dependencies, or large helper rewrites. Judge comment status for removed or stubbed functions and impls (commented, deleted, partial, or absent). Build the machine-readable per-file records with the full field set.
        > [[kverus-semantic-audit-knowledge#What counts as executable semantics]]
        > [[kverus-semantic-audit-knowledge#Semantic review heuristics]]
        > [[kverus-semantic-audit-knowledge#Report requirements]]
      6.1.1.3. [act free] Write the optional per-file detail reports
        - ← findings_json
        > For each file classified semantic-change or uncertain, write its detail report markdown under the output directory's semantic_reports folder, laid out by relative path, with the concrete evidence and reasoning behind the classification. This is the optional, classification-driven dynamic set — written executor-side per the file-writing ruling in Constraints.
        > [[kverus-semantic-audit-knowledge#Report requirements]]
      6.1.1.4. [reason] Compose the audit summary
        - ← index_digest, findings_json
        + → audit_summary % markdown  # the six-item summary document, conservative and behavior-led
        > Assemble the summary document with its six required items in order: input paths and timestamp; totals for matched files, missing files, executable-diff files, semantic changes, likely-equivalent, and uncertain; token-diff totals when the index carries them; the findings table with relative path, classification, severity, comment status, and a short reason that mentions key token changes when they drive the classification; the missing-file list; notes on skipped generated or vendor files. Follow the output style — conservative, concrete, leading with behavior rather than syntax.
        > [[kverus-semantic-audit-knowledge#Report requirements]]
        > [[kverus-semantic-audit-knowledge#Output style]]
      6.1.1.5. [check final] Gate the composed reports
        - ← audit_summary
        + → ok % bool  # true when the composed summary is non-empty
        + → note % text  # gap note when the summary is empty
        > Mechanical completeness gate on the composed summary. The findings records may legitimately be empty — a workspace with no executable-code differences still yields a complete six-item summary — so only the summary's non-emptiness is gated; field discipline inside the findings records is the cognitive duty of the classification step above.
        > ```hop_python
        > ok = len(audit_summary) > 0
        > note = "" if ok else "composed summary is empty: expected the six-item summary document"
        > ```
    6.1.2. [act] Record the completed outcome
      + → audit_outcome
      + → audit_note
      > Deterministic record of the completed terminal state for this audit run.
      > ```hop_python
      > audit_outcome = "completed"
      > audit_note = ""
      > ```
    6.1.3. [commit] Write the two required audit reports
      - ← effective_out_dir, audit_summary, findings_json
      + → summary_path
      + → findings_path
      > Pinned-path writes of the two required deliverables under the resolved output directory, immediately after the compose gate passed. Paths and contents are fully determined at this point — no executor discretion in this body. The optional per-file detail reports were already written executor-side in the audit subtask per the file-writing ruling.
      > ```hop_python
      > summary_path = effective_out_dir + "/semantic_audit_summary.md"
      > findings_path = effective_out_dir + "/semantic_audit_findings.json"
      > write(path: summary_path, content: audit_summary)
      > write(path: findings_path, content: findings_json)
      > ```
  6.2. [case(collector_rc != 0)] Report the collector failure honestly
    + → summary_path
    + → findings_path
    + → audit_outcome
    + → audit_note
    6.2.1. [act] Build the collector-failure notice
      - ← collector_rc, collector_report
      + → summary_path
      + → findings_path
      + → audit_outcome
      + → audit_note
      > Deterministic notice: the collector could not produce the index or diffs, so no audit runs and no report files are written. The empty path sentinels and the outcome enum say so plainly, and the terminal notice carries the collector's own output.
      > ```hop_python
      > summary_path = ""
      > findings_path = ""
      > audit_outcome = "collector_failed"
      > audit_note = "Audit aborted: the bundled diff collector exited with code " + str(collector_rc) + ". Stdout/stderr: " + collector_report + " The collector needs an existing paired Rust/Verus workspace and a writable output directory; verify the three directory inputs and rerun."
      > ```
7. [exit] Deliver the audit
  + → summary_path, findings_path, audit_outcome, collector_rc, audit_note
