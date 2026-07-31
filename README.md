# KVerus Skills

KVerus is a skill-based workflow for migrating Rust code to [Verus](https://github.com/verus-lang/verus/), adding proof-oriented specifications, repairing verification failures, and auditing the result. It can be used stage by stage through individual skills or end to end with `kverus-run`, which combines migration, specification, fixing, evaluation, semantic audit, and postprocessing into one verification pipeline.

The workflow-based version presented in the ASE '26 paper *KVerus: Scalable and Resilient Formal Verification Proof Generation for Rust Code* is available on the [`ase-26` branch](../../tree/ase-26).

## Setup Environment

#### 0. Clone the Repo

```shell
$ git clone --recursive https://github.com/asterinas/KVerus.git
```

#### 1. Prepare the python environment

If you don't have uv installed, please follow the [official instructions](https://docs.astral.sh/uv/getting-started/installation/).

```shell
# sync python environment
uv sync
```

#### 2. Install Verus

KVerus depends on the [Verus](https://github.com/verus-lang/verus/) command-line tool. See the official [installation guide](https://github.com/verus-lang/verus/blob/main/INSTALL.md).

## Setup Skills

KVerus ships a set of agent skills (under `skills/`) that can be installed into any target project for use with Codex or Claude Code.

```bash
# Install all skills into a target project (symlink mode, agent target by default)
$ ./scripts/install-skills.sh ~/my-project
```

On Windows (PowerShell):

```powershell
# Install all skills into a target project (symlink mode, agent target by default)
> .\scripts\install-skills.ps1 ~\my-project
```

Run `./scripts/install-skills.sh --help` (or `.\scripts\install-skills.ps1 --help` on Windows) for the full set of options. Common ones:

| Option          | Description                                   |
| --------------- | --------------------------------------------- |
| `-m, --mode`    | `symlink` (default) or `copy`                 |
| `-t, --targets` | `agent`, `claude`, or both (default: `agent`) |
| `-s, --skills`  | Comma-separated skill names (default: all)    |
| `-f, --force`   | Overwrite existing installations              |

## Verification Workflow

KVerus is organized as a set of composable skills for turning Rust code into verified Verus code. The recommended entrypoint is `kverus-run`, which orchestrates the full pipeline:

```text
$kverus-run target=path/to/file_or_dir verify="<verification command>"
```

`target` can be a single `.rs` file or a directory of Rust files. `verify` should be the exact command used by the target project to run Verus verification, for example a project-specific `cargo verus ...` or wrapper command. If `out_dir` is not provided, `kverus-run` writes reports under `.kverus-run-output/`.

### Full Pipeline

`kverus-run` combines the following skills:

```text
Rust code
  -> kverus-migrate
  -> kverus-spec
  -> kverus-fix
  -> kverus-eval
  -> kverus-semantic-audit
  -> kverus-postprocess
       -> kverus-strip
  -> verified Verus code + reports
```

The pipeline first snapshots the original Rust files, migrates them to Verus-compatible code, stages the migration changes, adds specifications, fixes verification failures, evaluates spec quality, audits executable semantics against the original Rust, and finally runs cleanup and formatting.

### Pipeline Stages

| Stage | Skill                   | Role                                                      |
| ----- | ----------------------- | --------------------------------------------------------- |
| 1     | `kverus-migrate`        | Create a verification-passing Verus-compatible baseline.  |
| 2     | `kverus-spec`           | Add proof-ready specifications and invariants.            |
| 3     | `kverus-fix`            | Repair verification failures without weakening the specs. |
| 4     | `kverus-eval`           | Evaluate spec quality and intent preservation.            |
| 5     | `kverus-semantic-audit` | Check executable behavior against the original Rust.      |
| 6     | `kverus-postprocess`    | Run final cleanup, verification, formatting, and checks.  |

See the [skills reference](skills/README.md#skills) for detailed stage responsibilities, constraints, and supporting skills. `kverus-strip` is a postprocessing helper rather than a separate pipeline stage.

The final `kverus-run` report is written to:

```text
<out_dir>/pipeline_summary.md
```

It records the target, verification command, per-stage status, evaluation scores, semantic-audit findings, postprocess results, blockers, and suggested next steps.

### Running Individual Skills

Each pipeline stage can also be invoked independently when only one part of the workflow is needed:

```text
$kverus-migrate target=path/to/file.rs verify="<verification command>"
$kverus-spec target=path/to/file.rs verify="<verification command>" knowledge="<optional context>"
$kverus-fix target=path/to/file.rs verify="<verification command>" error_message="<optional error>"
$kverus-eval target=path/to/file.rs context="<optional original spec intent>"
$kverus-semantic-audit rust_dir=path/to/original verus_dir=path/to/migrated out_dir=path/to/audit
$kverus-postprocess
$kverus-strip verify="<verification command>" target-dirs="src/,specs/"
```

Use the individual skills for targeted work, and use `kverus-run` when you want the complete Rust-to-Verus verification pipeline with quality gates and reports.

## Showcase

KVerus has been used in [VOSTD](https://github.com/asterinas/vostd), the Asterinas system verification project. The [VOSTD pull requests labeled `AI-assist`](https://github.com/asterinas/vostd/pulls?q=is%3Apr+label%3AAI-assist+) were developed using KVerus, with some implemented entirely by KVerus.

### Verifying `RwMutex`

[asterinas/vostd#395](https://github.com/asterinas/vostd/pull/395) demonstrates the core KVerus workflow on `sync::rwmutex`, taking the implementation from pure Rust code to fully verified Verus code. The following commits capture the intermediate migration and verification results:

| Transition                                                                            | Skill                        | Reference result                                                                                                               |
| ------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| [`3e90e5a` → `1baaab0`](https://github.com/asterinas/vostd/compare/3e90e5a...1baaab0) | `kverus-migrate`             | [`1baaab0`](https://github.com/asterinas/vostd/commit/1baaab0) converts `sync::rwmutex` into a Verus-compatible baseline.      |
| [`1baaab0` → `6ae195e`](https://github.com/asterinas/vostd/compare/1baaab0...6ae195e) | `kverus-spec` + `kverus-fix` | [`6ae195e`](https://github.com/asterinas/vostd/commit/6ae195e) adds the specifications and completes the corresponding proofs. |

This case focuses on the three core stages: migration, specification, and verification repair. The commits are reference outputs for demonstrating the skills rather than boundaries for the full `kverus-run` pipeline.

### Stripping Redundant Proof Code

[asterinas/vostd#633](https://github.com/asterinas/vostd/pull/633) demonstrates `kverus-strip` on `specs::mm::page_table::cursor::cursor_steps`. The skill simplified a single Rust source file, removing 1,075 lines of redundant proof code while keeping verification passing.

This showcase uses `tree-sitter-verus` for full proof-call discovery. Before starting the agent, install the repository's Python dependencies and, when invoking the skill, give the Python virtual environment path to the LLM, for example `.venv/bin`.

## Cite
If you find KVerus useful in your research, please consider citing our ASE 2026 paper:
```
@article{liu2026kverus,
  title={KVerus: Scalable and Resilient Formal Verification Proof Generation for Rust Code},
  author={Liu, Yuwei and Wan, Xinyi and Wang, Yanhao and Wang, Minghua and Huang, Lin and Wei, Tao},
  journal={arXiv preprint arXiv:2605.03822},
  year={2026}
}
```
