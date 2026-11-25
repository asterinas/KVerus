#!/bin/sh
set -eu

BASE="${1:-${KVERUS_POSTPROCESS_BASE:-origin/main}}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CHECKER="$SCRIPT_DIR/kverus_postprocess.py"
SIMPLIFIER="$SCRIPT_DIR/../../kverus-strip/scripts/simplify_proof.py"

RULE_REPO="${KVERUS_POSTPROCESS_RULE_REPO:-}"
TARGET_PATHS="${KVERUS_POSTPROCESS_TARGET_PATHS:-}"
VERIFY_CMD="${KVERUS_POSTPROCESS_VERIFY_CMD:-}"
FORMAT_CMD="${KVERUS_POSTPROCESS_FORMAT_CMD:-}"
INCLUDE_SKILLS="${KVERUS_POSTPROCESS_INCLUDE_SKILLS:-0}"
BLOCKED_PATHS="${KVERUS_POSTPROCESS_BLOCKED_PATHS:-}"
GENERATED_PATHS="${KVERUS_POSTPROCESS_GENERATED_PATHS:-}"
SIMPLIFY_SCOPE="${KVERUS_POSTPROCESS_SIMPLIFY_SCOPE:-modified}"
REFRESH_RULES="${KVERUS_POSTPROCESS_REFRESH_RULES:-0}"
ENABLE_SIMPLIFY="${KVERUS_POSTPROCESS_ENABLE_SIMPLIFY:-0}"

run_checker() {
    refresh_mode="$1"
    shift
    set -- "$CHECKER" --base "$BASE" --rule-repo "$RULE_REPO"
    if [ -n "$TARGET_PATHS" ]; then
        set -- "$@" --target-path "$TARGET_PATHS"
    fi
    if [ "$INCLUDE_SKILLS" = "1" ]; then
        set -- "$@" --include-skills
    fi
    if [ -n "$BLOCKED_PATHS" ]; then
        set -- "$@" --blocked-path "$BLOCKED_PATHS"
    fi
    if [ -n "$GENERATED_PATHS" ]; then
        set -- "$@" --generated-path "$GENERATED_PATHS"
    fi
    if [ "$refresh_mode" = "refresh" ]; then
        set -- "$@" --refresh-rules
    else
        set -- "$@" --no-refresh-rules
    fi
    python3 "$@"
}

run_simplifier() {
    set -- python3 "$SIMPLIFIER" --base "$BASE"
    case "$SIMPLIFY_SCOPE" in
        all) ;;  # simplify every function in the targeted files/dirs
        *)   set -- "$@" --modified-only ;;  # default: only newly modified functions
    esac
    if [ -n "$TARGET_PATHS" ]; then
        set -- "$@" --target-dir "$TARGET_PATHS"
    fi
    if [ -n "$VERIFY_CMD" ]; then
        set -- "$@" --verify-command "$VERIFY_CMD"
    else
        set -- "$@" --dry-run
    fi
    "$@"
}

if [ "$REFRESH_RULES" = "1" ]; then
    echo "== kverus-postprocess: refresh rules and check =="
    run_checker refresh || FIRST_STATUS=$?
fi
: "${FIRST_STATUS:=0}"

if [ "$ENABLE_SIMPLIFY" = "1" ] && [ "${KVERUS_POSTPROCESS_SKIP_SIMPLIFY:-0}" != "1" ]; then
    if [ -n "$VERIFY_CMD" ]; then
        echo "== kverus-postprocess: verify before simplification =="
        sh -c "$VERIFY_CMD"
    fi
    echo "== kverus-postprocess: simplify redundant asserts =="
    run_simplifier
    if [ -z "$VERIFY_CMD" ]; then
        echo "Assert simplification ran in dry-run mode; set KVERUS_POSTPROCESS_VERIFY_CMD to enable removals."
    fi
fi

if [ -n "$FORMAT_CMD" ]; then
    echo "== kverus-postprocess: format =="
    sh -c "$FORMAT_CMD"
else
    echo "== kverus-postprocess: format skipped; set KVERUS_POSTPROCESS_FORMAT_CMD =="
fi

if [ -n "$VERIFY_CMD" ]; then
    echo "== kverus-postprocess: final verify =="
    sh -c "$VERIFY_CMD"
else
    echo "== kverus-postprocess: verify skipped; set KVERUS_POSTPROCESS_VERIFY_CMD =="
fi

echo "== kverus-postprocess: final check =="
run_checker cache || FINAL_STATUS=$?
: "${FINAL_STATUS:=0}"

echo "== kverus-postprocess: git diff --check =="
git diff --check || DIFF_CHECK_STATUS=$?
: "${DIFF_CHECK_STATUS:=0}"

echo "== kverus-postprocess: git status =="
git status --short --branch

if [ "$FIRST_STATUS" -ne 0 ]; then
    echo "Initial postprocess reported errors before final checks; final status was $FINAL_STATUS."
fi

if [ "$FINAL_STATUS" -ne 0 ]; then
    exit "$FINAL_STATUS"
fi
exit "$DIFF_CHECK_STATUS"
