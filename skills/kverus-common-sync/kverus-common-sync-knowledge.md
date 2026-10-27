# kverus-common-sync knowledge

Companion knowledge for the kverus-common-sync spec and its repair callee. Mirrors the source skill's "What It Checks", "Interpreting Results", and "Repair Policy" sections; nothing here adds to or contradicts the source.

## What the checker verifies

1. `$AGENT_DIR/skills/kverus-common` exists and has reference files, and a Verus root was provided or discovered.
2. Every `Sources:` path in `kverus-common/references/*.md` is Verus-root-relative (`source/...` or `examples/...`, optionally with a `:LINE` or `:LINE-LINE` suffix). Reference files that are not guide-derived must declare `Source scope: ...` instead of a `Sources:` block.
3. Every referenced source file resolves under the Verus root and exists.
4. Every inline Markdown cross-reference resolves: `references/...` against the skill directory, bare sibling filenames or `../`/subdirectory paths against the referring file, and guide citations against the Verus root. Workspace-policy citations (`AGENTS.md`, `docs/...`) are exempt.
5. Whether any referenced guide source is newer than the `kverus-common` reference that cites it.

## Exit code semantics

- `0`: synchronized enough for the structural checks.
- `2`: no blocking errors, but warnings such as newer guide files exist. Warnings about newer guide files mean the reference may be stale. Inspect the listed guide file and update the corresponding `kverus-common` reference if the changed content matters.
- `1`: one or more blocking errors, or no Verus root could be provided or discovered.

## Repair policy

When a check fails:

1. Fix structural errors first: a missing Verus root, missing files, or invalid source paths. (The missing-root case is provisioned by the caller before the repair transaction starts.)
2. Fix unresolvable cross-references: point them at the file they intend, using `references/...`, a sibling filename, or a Verus-root-relative guide path.
3. For stale-source warnings, compare the cited guide source with the current reference and update only relevant summaries.
4. Re-run the checker.
