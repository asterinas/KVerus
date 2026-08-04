# KVerus Skills

KVerus is a skill-based workflow for migrating Rust code to formally verified [Verus](https://github.com/verus-lang/verus/), adding specifications and proofs, repairing verification failures, and auditing the result. Use the skills individually or run the full pipeline with `kverus-run`.

The workflow-based version presented in the ASE 2026 paper *KVerus: Scalable and Resilient Formal Verification Proof Generation for Rust Code* is available on the [`ase-26` branch](../../tree/ase-26).

## Setup Environment

#### 0. Clone the Repo

```shell
$ git clone --recursive https://github.com/asterinas/KVerus.git
```

#### 1. Prepare the python environment

If you don't have uv installed, please follow the [official instructions](https://docs.astral.sh/uv/getting-started/installation/).

```shell
# sync python environment
$ uv sync
```

#### 2. Install Verus

KVerus depends on the [Verus](https://github.com/verus-lang/verus/) command-line tool. See the official [installation guide](https://github.com/verus-lang/verus/blob/main/INSTALL.md).

## Setup Skills

KVerus ships a set of agent skills (under `skills/`) that can be installed into any target project for use with Codex or Claude Code.

```bash
# Install all skills into a target project (symlink mode, agent target by default)
$ ./scripts/install-skills.sh ~/my-project

# Or on Windows PowerShell:
> .\scripts\install-skills.ps1 ~\my-project
```

The installer supports copy or symlink mode, Codex and Claude Code targets, selective skill installation, and overwriting existing installations. Run it with `--help` for details.

## Verification Workflow

The recommended entrypoint is the end-to-end pipeline:

```text
$kverus-run target=path/to/file_or_dir verify="<verification command>"
```

`target` can be a single `.rs` file or a directory of Rust files. `verify` should be the exact command used by the target project to run Verus verification, for example a project-specific `cargo verus ...` or wrapper command. If `out_dir` is not provided, `kverus-run` writes reports under `.kverus-run-output/`.

### Full Pipeline

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

The pipeline migrates Rust to Verus, adds and repairs proofs, evaluates their quality, audits executable semantics, and performs final cleanup. See the [skills reference](skills/README.md#skills) for details. The final report is written to `<out_dir>/pipeline_summary.md`.

### Running Individual Skills

Individual stages can also be invoked for targeted work. See the [skills reference](skills/README.md#skills) and the corresponding SKILL.md for their inputs and constraints.

## Quick Example

The [verified insertion sort](docs/examples/insertion-sort/README.md) is an end-to-end example from Rust code to verified Verus code, including source files, generated proofs, reproduction commands, and verification results.

## Showcase

KVerus has been used in [VOSTD](https://github.com/asterinas/vostd), the Asterinas system verification project. The [VOSTD pull requests labeled `AI-assist`](https://github.com/asterinas/vostd/pulls?q=is%3Apr+label%3AAI-assist+) were developed using KVerus, with some implemented entirely by KVerus.

### Verifying `RwMutex`

[asterinas/vostd#395](https://github.com/asterinas/vostd/pull/395) demonstrates the core KVerus workflow on `sync::rwmutex`, taking the implementation from Rust code to fully verified Verus code. The following commits capture the intermediate migration and verification results:

| Transition                                                                            | Skill                        | Reference result                                                                                                               |
| ------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| [`3e90e5a` → `1baaab0`](https://github.com/asterinas/vostd/compare/3e90e5a...1baaab0) | `kverus-migrate`             | [`1baaab0`](https://github.com/asterinas/vostd/commit/1baaab0) converts `sync::rwmutex` into a Verus-compatible baseline.      |
| [`1baaab0` → `6ae195e`](https://github.com/asterinas/vostd/compare/1baaab0...6ae195e) | `kverus-spec` + `kverus-fix` | [`6ae195e`](https://github.com/asterinas/vostd/commit/6ae195e) adds the specifications and completes the corresponding proofs. |

This case focuses on the three core stages: migration, specification, and verification repair. The commits are reference outputs for demonstrating the skills rather than boundaries for the full `kverus-run` pipeline.

### Stripping Redundant Proof Code

[asterinas/vostd#633](https://github.com/asterinas/vostd/pull/633) demonstrates `kverus-strip` on `specs::mm::page_table::cursor::cursor_steps`. The skill simplified a single Rust source file, removing 1,075 lines of redundant proof code while keeping verification passing.

This showcase uses `tree-sitter-verus` for full proof-call discovery. Before starting the agent, install the repository's Python dependencies.

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
