#!/usr/bin/env python3
"""Original-snapshot copier for the kverus-run pipeline (pinned machine asset).

Two modes,-selected by the first argument:

  --snapshot <orig_dir> <files_csv> <out_dir>
      Copy every listed workspace-relative file into <orig_dir> preserving
      relative structure (makedirs + copy2), then provision the output tree
      <out_dir> with its audit/ and fix-blockers/ subdirectories. The file
      list is captured BEFORE any pipeline edits, so the snapshot is the
      exact pre-pipeline byte state, including any pre-existing dirty user
      edits to the same files.

  --restore <orig_dir>
      Copy every snapshotted file back to its workspace-relative path,
      overwriting the pipeline's edits. Inverse of --snapshot by
      construction: same relative keys, same bytes. Files the pipeline may
      have newly created (a constraint violation by any callee) are not in
      the snapshot and are left for the unstage duty to surface as untracked.

Prints one summary line on stdout; exit code 0 on success, 1 with an error
line on stderr on failure. The calling spec gates both modes with completion
checks (any returned code completes; the sentinel -1 means killed).
"""
import os
import shutil
import sys


def snapshot(orig_dir: str, files_csv: str, out_dir: str) -> int:
    copied = 0
    for rel in [p for p in files_csv.split(",") if p]:
        src = rel
        dst = os.path.join(orig_dir, rel)
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    for sub in ("", "audit", "fix-blockers"):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
    print("snapshot: copied=%d out_dir=%s provisioned" % (copied, out_dir))
    return 0


def restore(orig_dir: str) -> int:
    if not os.path.isdir(orig_dir):
        sys.stderr.write(
            "snapshot_copy restore: orig_dir does not exist: %s\n" % orig_dir
        )
        return 1
    restored = 0
    for root, dirs, names in os.walk(orig_dir):
        dirs.sort()
        for name in sorted(names):
            abs_path = os.path.join(root, name)
            rel = os.path.relpath(abs_path, orig_dir)
            os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
            shutil.copy2(abs_path, rel)
            restored += 1
    print("restore: restored=%d" % restored)
    return 0


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(
            "usage: snapshot_copy.py --snapshot <orig> <csv> <out> | --restore <orig>\n"
        )
        return 1
    mode = argv[1]
    try:
        if mode == "--snapshot" and len(argv) == 5:
            return snapshot(argv[2], argv[3], argv[4])
        if mode == "--restore" and len(argv) == 3:
            return restore(argv[2])
    except Exception as exc:
        sys.stderr.write("snapshot_copy failed: %s\n" % exc)
        return 1
    sys.stderr.write(
        "usage: snapshot_copy.py --snapshot <orig> <csv> <out> | --restore <orig>\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
