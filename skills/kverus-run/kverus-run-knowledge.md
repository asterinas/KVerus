# Knowledge: kverus-run — pipeline objective, phase map, machine-duty contracts, and the deviation register

Id: kverus-run-knowledge
Spec: kverus-run

## 1. Objective and scope split

The pipeline owns routing and honesty: discovery, snapshotting, staging, delegation wrapping with crash absorption, the two quality gates, the report tree, the committed summary, and the sixteen-output exit. It owns **no** transformation cognition — migrate, scaffold, repair, score, audit, and strip all live in their callee specs. The split rule: if a step edits Rust or Verus, judges a proof, or decides a classification, it belongs to a callee; if it moves bytes, records a word, gates a duty, or composes the report, it belongs here.

## 2. Phase map

| Phase | Owner | Input surface | Relays back | Gate |
|---|---|---|---|---|
| 0 discovery / snapshot / cache | this spec (machine duties) | entered via ask gates | file_list, discovery_mode, orig_dir, warm_state, cache_status | verdict branches 5/7/9/11/14 |
| 1 migrate | kverus-migrate, per file | target, verify | edited_target, verify_report, verify_rc, migration_outcome, final_report | wrapper check final until outcome nonempty |
| 2 stage | this spec (git duty) | file_list | staging_state | verdict branch 17 |
| 3 scaffold | kverus-spec, per converted file | target, verify, knowledge="" | edited_target, verify_report, verify_rc | wrapper gate report nonempty |
| 4 repair | kverus-fix, per failing file | target, verify, error_message, out_path, mode="explicit" | resolution_report, final_report, verify_rc, repair_outcome, blocker_summary_path | wrapper gate report nonempty |
| 5 evaluate | kverus-eval, per converted file | target, intent_context="" | eval_report, score_num | score threshold 7, two tickets, accept/manual gate |
| 6 audit | kverus-semantic-audit (once) | rust_dir, verus_dir, out_dir | summary_path, findings_path, audit_outcome, collector_rc, audit_note | machine severity gate + continue/abort ask |
| 7 postprocess | kverus-postprocess (once) | base, target_paths, verify_command, 6 defaults | postprocess_report, postprocess_outcome, final_checker_rc, refresh_rc, checker_rc, strip_report, strip_outcome | wrapper gate report+outcome |
| 8 report | this spec | record tables | committed summary or reduced stop report | completion gate + commit |

## 3. Phase-0 machine contracts

**discover_files.py** (bundled): `python3 scripts/discover_files.py <target>`. Never crashes: file mode emits `{"mode": "file", "files": ["<target>"]}`; directory mode walks recursively in alphabetical order and emits `{"mode": "directory", "files": [...]}`; a missing entry emits `{"mode": "missing", "files": []}`. Exit code 0; anomalies land in the JSON, not in a crash. The spec gates on `discovery_mode == "missing"` and halts before any mutation. Directory-mode ordering is alphabetical — the registered approximation of the source's leaf-first dependency ordering (see section 9).

**snapshot_copy.py** (bundled): `python3 scripts/snapshot_copy.py --snapshot <orig_dir> <files-csv> <out_dir>` copies every listed file into the snapshot root preserving relative structure, then provisions `<out_dir>` with its `audit/` and `fix-blockers/` subdirectories; exit 0 on completion. `python3 scripts/snapshot_copy.py --restore <orig_dir>` copies every snapshotted file back over the working tree; exit 1 when the root is missing (isdir guard), 0 on restore. The comma-joined csv is the only string-joining duty — paths containing commas are unsupported (disclosed deviation).

**kverus_postprocess.py copy** (byte-identical, cmp-verified against the postprocess callee's own script): the phase-0 cache probe `--cache-status` and the bounded warm-up `--refresh-only` drive this spec's bundled copy directly, so phase 0 needs no network and no delegation. Later phases run the real callee, which bundles the same checker.

All three bundled scripts self-source `kverus.env` at entry by the repository's pinned L1 bootstrap; the spec and its hop_python bodies never source env files themselves.

## 4. Cache probe and warm-up policy

The cache probe classifies the dynamic-rule cache as fresh / stale / missing by counting the script's status anchors, and reads the configured repo key. Warm-up runs only when a repo is configured AND the probe shows stale or missing entries; it is one bounded `--refresh-only` pass (timeout 900s, the provisional refresh budget) gated on the script's own "Refresh-only summary:" output anchor. A crashed warm-up is absorbed to `warm_state = "crashed"` and the pipeline continues on static seed rules — cache warmth is a speed optimization, never a correctness gate. When nothing needs refresh, `warm_state = "fresh-or-unconfigured"`.

## 5. Relay decoding table

| Relay | Set carrier | Words |
|---|---|---|
| migration_outcome | MigrateRecord.migration_outcome | converted / blocked / crashed (run-added crash marker) |
| spec_status | SpecRecord.spec_status | delegated (green wrapper) / crashed |
| repair_outcome | FixRecord.repair_outcome | verified / blocked / no_failing_target / declined_no_edits (callee enum) / crashed |
| EvalRecord.score_num | eval_records | int in [0,10]; -1 sentinel from the callee |
| gate_choice | EvalRecord.gate_choice | accept / stop / "" (passing files ask no gate) |
| audit_outcome | audit_outcome output | completed / collector_failed (callee enum) / crashed / skipped-empty |
| audit_gate_word (run-internal) | routing | completed-high / completed-clean / collector_failed / crashed / skipped |
| postprocess_outcome | postprocess_outcome | completed / checker_failed / verify_failed / simplification_failed / format_failed (callee enum) / crashed / skipped-empty |
| strip_outcome | strip_outcome | callee words / crashed |
| staging_state | run-internal | staged / stage-red / stage-crashed / nothing-to-stage |
| warm_state / cache_status / rm_state / restore duties | run-internal | refreshed / crashed / idle forms; fresh / stale / missing / unknown; removed / removal-failed / absent; restored / restore-failed |

Words the run adds itself — "crashed" (wrapper absorption), "skipped-empty" (empty-scope skips), "nothing-to-stage", "fresh-or-unconfigured" — are disclosed here and in the spec constraints.

## 6. Machine severity gate at the audit relay

The audit callee writes `semantic_audit_findings.json` with one entry per reviewed file carrying the documented field set: path, rust_path, verus_path, classification, severity, comment_status, summary, evidence, key_token_changes, recommended_action. The run's relay gate parses that JSON (guarded read via the existence probe), filters entries with `classification == "semantic-change"` and `severity == "high"`, and routes: completed + any high → `completed-high` (ask the user); completed + none → `completed-clean`; collector_failed and crashed pass through; empty scope → skipped. The coupling contract: callee emits exactly these keys; the two specs are co-delivered.

## 7. Repair-loop protocol (phase 5)

Per converted file: evaluate; score < 7 is failing. Failing files get at most **two** automatic repair tickets (the source's "up to 2 retries") — ticket 1 then ticket 2, each ticket = re-scaffold (fresh kverus-spec over the file) → adopt the fresh scaffold report as the repair hint → re-repair (kverus-fix, same five-param surface) → re-evaluate. The hint chain rule: the pairing act always reads the freshest available context — first round from the file's spec_records row (verify report) else its migrate_records row (final report); later rounds from the re-scaffold report when nonempty else keep the previous hint. The ladder stops early when a round lifts the score to the threshold (`[break]` on passing). Exhausted-failing files hit the disposition gate with exactly the source's two options: accept (record + continue) or stop (manual spec editing; tree preserved). Green files never enter the repair selection — fix_files is spec_records where verify_rc != 0.

The repair_log line grammar is `"<file>: ticket <n>: <repair_status> score <score>"`, and EvalRecord.repair_rounds filters the log back to the file's rows by first-colon prefix.

## 8. Report catalogue and write duties

The committed completion report has nine sections composed purely from the record tables: 1 configuration (target, mode, work-list length, verification command, report root, stamp); 2 migration records; 3 scaffolding records; 4 repair records; 5 evaluation records plus the machine-compiled failing-file list (the average score is dropped — section 9); 6 audit disposition (outcome, high count, sample paths, gate word, raw answer); 7 postprocess five-element result (outcome, final checker rc, refresh rc, checker rc, strip verdict); 8 blockers and warnings (machine-consolidated rows for anything not converted/delegated/passing, plus warm-up/cache/staging states); 9 suggested next steps (machine-routed lines: always verify-and-review, plus conditional audit/findings/accepted-below-threshold/strip lines).

Write duties by route: completion commits the nine-section file; manual stop and audit abort commit the reduced stop report (configuration, the record tables collected so far, disposition, cleanup states — deliberately omitting phases that never ran); the three pre-provisioning halt tails and the two post-mktemp duty-failure halts commit nothing (summary_path relayed empty, note carried in the exit payload). Every route's narrative beyond the machine skeleton lives in the instance's reason steps and the callee reports embedded in the record tables.

## 9. Deviation and approximation register

- **Alphabetical walk** vs the source's dependency-preferred ordering — executor cognition the machine walker does not attempt; per-file dependency handling stays with the migrate callee.
- **Average score dropped** — hop_python carries no sum primitive; report section 5 carries per-file scores plus the failing-file list.
- **Re-spec guidance approximated** — re-scaffold rounds re-read tree state and re-pair from record tables; the eval rationale is not relayed into the scaffold callee (it has no such input).
- **Postprocess relay surface** — target_paths as directory (directory mode) or comma-joined list (file mode); eight other optional parameters relayed as documented empty defaults.
- **Copier comma caveat** — join(file_list, ",") cannot carry paths containing commas.
- **Completion-gate discipline** — user-shaped duty commands gate on `rc != -1` (any returned code completes the duty, failure narrated); only bundled-script warm-up uses the output-anchor gate.
- **No verify pre-probe** — the pipeline never runs the user's verification command itself; a broken command surfaces through the callee relays (migration crashes absorbed per file, records classified, report consolidated).
- **Sequential warm-up barrier** — phase 0 completes the refresh before any delegation starts, instead of the source's implied laziness; a bounded, one-shot interpretation.
- **First-round record standing** — repair rounds do not overwrite the first spec_records row; rounds ride repair_log lines and EvalRecord.repair_rounds.
- **s_* adoption dropped** — the repair selection stands on first-round records (cheaper, source-faithful: green files skip repair).
- **Verus-dir derivation** — machine formula: directory mode takes the target itself, file mode takes the target's parent; the rust half of the audit pair is the snapshot root.
- **Tie-naming collision** — two files sharing a leaf name would collide on one fix-blocker summary path; pathological shape, disclosed.

## 10. Provisional values (translation ledger; engine retry=N-counts-failures correction applied)

Subprocess timeouts: 300s for walker, copier, cache probe, git duties, snapshot removal; 900s for the warm-up refresh. Delegation wrappers are single-attempt (retry=0) with on-fail absorption; retry ladders live inside the callees. Eval repair tickets: exactly two. Loop bounds inherit the source's lists (no synthetic max). All provisional numbers route to the ledger for the final review.

## 11. Deployment prerequisites

- Seven sister specs resolvable from this spec's directory: staging ships them as same-flat-name symlinks (kverus-migrate.md, kverus-spec.md, kverus-fix.md, kverus-eval.md, kverus-semantic-audit.md, kverus-postprocess.md, kverus-strip.md); a real deployment re-points them to the delivered `../<id>/spec.md` layout. The seventh rides for the delegated kverus-postprocess → kverus-strip static call: the engine resolves transitive call targets against the root instance's spec directory (L41), and an instance directory lacking the strip sister fails INIT_FAILED at dependency check.
- `kverus.env` present at the repository root (or the KVERUS_ENV_FILE override) for the three bundled scripts' L1 self-bootstrap.
- Engine command whitelist: python3, git (status/add/restore/diff forms as scoped in the spec), mktemp, rm — plus the **first word** of any user-shaped verification command, which cannot be known statically.
- hopjit.yaml registry entries for every delivered spec of the family — this spec's six direct callees, their transitive kverus-strip, and the remaining delivered specs (requires_commands not statically cross-checked — deployment duty).
- `hopjit ant pack --assets` must carry `scripts/` (three bundled tools) alongside the spec and this knowledge doc.

## 12. Shared-reference reading order

Any phase that edits Verus code inherits `exec-code-preservation.md` first — the reason-first `Origin Rust:` block-comment format. When a gate or report narrative must reason about proof constructs, read from the sibling kverus-common references tree: `verus-syntax-quickref.md`, `ghost-tracked.md`, `lemma-shape.md`, `unsupported-features/index.md`. The per-file transformation cognition itself lives in the callee specs' knowledge documents.

## 13. L6 dynamic-command discipline

The user's verification command is relayed whole to every callee that runs it; each callee splits it itself. This spec's own subprocess channels use fixed argv lists only. The first word of the user's command must be whitelisted at deployment; a differently-prefixed verifier wrapper is a deployment prerequisite, not a spec defect.

## 14. Fidelity rulings quick-index

Staging breadth is the flat discovered list (blocked files' partial edits stage; disclosed). Unstage couples to the audit-abort route only — completion and manual stop preserve the staged/unstaged separation for user review. The manual-stop word is manual_stopped with the tree deliberately preserved (migration staged, spec unstaged) and a reduced committed report. The eval gate offers exactly accept or manual stop — no abort. Repair tickets are exactly two. All sixteen outputs lift on every exit, including the halts. The exit payload is the only honest channel on pre-provisioning halt routes; reduced reports commit only when an output tree exists.
