#!/usr/bin/env python3
"""Remove redundant Verus proof statements when verification still succeeds."""

from __future__ import annotations

from abc import ABC, abstractmethod
import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from tree_sitter import Language, Parser, Node
    import tree_sitter_verus
    from loguru import logger

    VERUS_LANGUAGE = Language(tree_sitter_verus.language())

    class _BaseParser(ABC):
        """Minimal tree-sitter base parser shared by the inlined Verus parsers."""

        def __init__(self, verus_code: str, language):
            self.parser = Parser(language)
            tree = self.parser.parse(verus_code.encode())
            self.root_node = tree.root_node
            self.filename = "<unknown>"
            self.depth = 0

        def parse(self):
            self._traverse(self.root_node)

        @abstractmethod
        def _traverse(self, node: Node):
            pass

        @staticmethod
        def _get_name(node) -> str:
            """Extract the name from the node."""
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode()
            return ""

        def _get_start(self, node) -> str:
            start_byte, start_point = node.start_byte, node.start_point
            return f"{self.filename}:{start_point[0]+1}:{start_point[1]+1}"

        def _get_end(self, node) -> str:
            end_byte, end_point = node.end_byte, node.end_point
            return f"{self.filename}:{end_point[0]+1}:{end_point[1]+1}"

    class SimplifyParser(_BaseParser):
        """
        A simple AST Parser for Verus code using tree_sitter
        """

        def __init__(self, verus_code: str):
            self.asserts = list()
            self._seen_assert_ranges = set()
            self.calls = list()
            self._seen_call_ranges = set()
            self.attributes = list()
            self.admits = list()
            self.assumes = list()
            super().__init__(verus_code, VERUS_LANGUAGE)

        @classmethod
        def from_code(cls, code: str):
            return cls(code)

        @classmethod
        def from_file(cls, path_file: Path):
            verus_code = path_file.read_text(encoding="utf-8")
            instance = cls(verus_code)
            instance.filename = str(path_file)
            return instance

        def _extract_assert(
            self,
            node: Node,
            *,
            start_byte: int | None = None,
            end_byte: int | None = None,
            text_override: str | None = None,
        ) -> dict:
            # Safely obtain text from the node: handle None, bytes, and str,
            # and fall back to reading the file slice if text is not available.
            text = (
                text_override
                if text_override is not None
                else getattr(node, "text", None)
            )
            if text is None:
                logger.warning("Node text is None, attempting to read from file.")
                try:
                    file_bytes = Path(self.filename).read_bytes()
                    actual_start = node.start_byte if start_byte is None else start_byte
                    actual_end = node.end_byte if end_byte is None else end_byte
                    text = file_bytes[actual_start:actual_end].decode()
                except Exception:
                    text = ""
            elif isinstance(text, bytes):
                text = text.decode()
            elif not isinstance(text, str):
                text = str(text)
            actual_start = node.start_byte if start_byte is None else start_byte
            actual_end = node.end_byte if end_byte is None else end_byte
            return {"assert": text, "start": actual_start, "end": actual_end}

        @staticmethod
        def _decode_node_text(node: Node) -> str:
            text = getattr(node, "text", None)
            if isinstance(text, bytes):
                return text.decode()
            if isinstance(text, str):
                return text
            if text is None:
                return ""
            return str(text)

        def _append_assert(self, node: Node, **kwargs):
            dict_assert = self._extract_assert(node, **kwargs)
            location = (dict_assert["start"], dict_assert["end"])
            if location not in self._seen_assert_ranges:
                self._seen_assert_ranges.add(location)
                self.asserts.append(dict_assert)

        @classmethod
        def _is_proof_context(cls, node: Node) -> bool:
            current = node.parent
            while current is not None:
                if current.type in {
                    "proof_block",
                    "assert_by_expression",
                    "assert_by_block_expression",
                    "assert_forall_expression",
                }:
                    return True
                if current.type == "function_item":
                    return any(
                        child.type == "function_mode"
                        and cls._decode_node_text(child).strip() == "proof"
                        for child in current.children
                    )
                current = current.parent
            return False

        def _append_call_statement(
            self,
            node: Node,
            *,
            start_byte: int | None = None,
            end_byte: int | None = None,
            text_override: str | None = None,
        ):
            statement = node.parent
            if statement is None or statement.type != "expression_statement":
                return
            actual_start = statement.start_byte if start_byte is None else start_byte
            actual_end = statement.end_byte if end_byte is None else end_byte
            location = (actual_start, actual_end)
            if location in self._seen_call_ranges:
                return
            text = (
                self._decode_node_text(statement)
                if text_override is None
                else text_override
            )
            self._seen_call_ranges.add(location)
            self.calls.append(
                {
                    "call": text,
                    "start": actual_start,
                    "end": actual_end,
                    "is_proof": self._is_proof_context(node),
                }
            )

        def _parse_macro_token_tree(
            self, token_tree: Node, original_start_byte: int | None = None
        ):
            token_text = self._decode_node_text(token_tree)
            if len(token_text) < 2:
                return

            inner_text = token_text[1:-1]
            token_start = (
                token_tree.start_byte
                if original_start_byte is None
                else original_start_byte
            )
            prefix = "verus! { fn __kverus_macro_probe() {"
            suffix = "} }"
            wrapped_source = f"{prefix}{inner_text}{suffix}"
            wrapped_tree = self.parser.parse(wrapped_source.encode())
            self._traverse_macro_tree(
                wrapped_tree.root_node,
                token_start + 1,
                len(prefix.encode()),
            )

            for child in token_tree.children:
                if child.type == "token_tree":
                    nested_original_start = token_start + (
                        child.start_byte - token_tree.start_byte
                    )
                    self._parse_macro_token_tree(child, nested_original_start)

        def _traverse_macro_tree(
            self, node: Node, original_base: int, wrapped_prefix_len: int
        ):
            for child in node.children:
                if child.type in {
                    "assert_expression",
                    "assert_by_expression",
                    "assert_by_block_expression",
                    "assert_forall_expression",
                    "assert_macro_call",
                }:
                    mapped_start = original_base + child.start_byte - wrapped_prefix_len
                    mapped_end = original_base + child.end_byte - wrapped_prefix_len
                    self._append_assert(
                        child,
                        start_byte=mapped_start,
                        end_byte=mapped_end,
                        text_override=self._decode_node_text(child),
                    )
                elif child.type == "call_expression":
                    statement = child.parent
                    if (
                        statement is not None
                        and statement.type == "expression_statement"
                    ):
                        mapped_start = (
                            original_base + statement.start_byte - wrapped_prefix_len
                        )
                        mapped_end = (
                            original_base + statement.end_byte - wrapped_prefix_len
                        )
                        self._append_call_statement(
                            child,
                            start_byte=mapped_start,
                            end_byte=mapped_end,
                            text_override=self._decode_node_text(statement),
                        )
                elif child.type == "macro_invocation":
                    for macro_child in child.children:
                        if macro_child.type == "token_tree":
                            mapped_start = (
                                original_base
                                + macro_child.start_byte
                                - wrapped_prefix_len
                            )
                            self._parse_macro_token_tree(macro_child, mapped_start)
                self._traverse_macro_tree(child, original_base, wrapped_prefix_len)

        def _extract_attribute(self, node: Node) -> dict:
            # Safely obtain text from the node: handle None, bytes, and str,
            # and fall back to reading the file slice if text is not available.
            text = getattr(node, "text", None)
            if text is None:
                logger.warning("Node text is None, attempting to read from file.")
                try:
                    file_bytes = Path(self.filename).read_bytes()
                    text = file_bytes[node.start_byte : node.end_byte].decode()
                except Exception:
                    text = ""
            elif isinstance(text, bytes):
                text = text.decode()
            elif not isinstance(text, str):
                text = str(text)
            return {"attribute": text, "start": node.start_byte, "end": node.end_byte}

        def _extract_admit(self, node: Node) -> dict:
            text = getattr(node, "text", None)
            if text is None:
                logger.warning("Node text is None, attempting to read from file.")
                try:
                    file_bytes = Path(self.filename).read_bytes()
                    text = file_bytes[node.start_byte : node.end_byte].decode()
                except Exception:
                    text = ""
            elif isinstance(text, bytes):
                text = text.decode()
            elif not isinstance(text, str):
                text = str(text)
            return {"admit": text, "start": node.start_byte, "end": node.end_byte}

        def _extract_assume(self, node: Node) -> dict:
            text = getattr(node, "text", None)
            if text is None:
                logger.warning("Node text is None, attempting to read from file.")
                try:
                    file_bytes = Path(self.filename).read_bytes()
                    text = file_bytes[node.start_byte : node.end_byte].decode()
                except Exception:
                    text = ""
            elif isinstance(text, bytes):
                text = text.decode()
            elif not isinstance(text, str):
                text = str(text)
            return {"assume": text, "start": node.start_byte, "end": node.end_byte}

        def _traverse(self, node: Node):
            for child in node.children:
                if child.type in {
                    "assert_expression",
                    "assert_by_expression",
                    "assert_by_block_expression",
                    "assert_forall_expression",
                    "assert_macro_call",
                }:
                    self._append_assert(child)
                elif child.type == "call_expression":
                    self._append_call_statement(child)
                elif child.type == "attribute":
                    dict_attribute = self._extract_attribute(child)
                    self.attributes.append(dict_attribute)
                elif child.type == "call_expression":
                    if self._get_name(child) == "admit":
                        dict_admit = self._extract_admit(child)
                        self.admits.append(dict_admit)
                elif child.type == "assume_expression":
                    dict_assume = self._extract_assume(child)
                    self.assumes.append(dict_assume)
                elif child.type == "macro_invocation":
                    for macro_child in child.children:
                        if macro_child.type == "token_tree":
                            self._parse_macro_token_tree(macro_child)

                self.depth += 1
                self._traverse(child)
            self.depth -= 1

    class FunctionRangeParser(_BaseParser):
        """Extract function impl_range boundaries using tree-sitter.

        A slimmed-down inlined tree-sitter function-range parser: it only collects
        each function's impl_range (start including preceding doc comments, end at
        the function_item), which is all simplify_proof.py needs for function
        scoping. Struct/enum/trait/impl extraction is intentionally omitted.
        """

        def __init__(self, verus_code: str):
            super().__init__(verus_code, VERUS_LANGUAGE)
            self.map_func_info: dict[str, dict] = {}

        @classmethod
        def from_file(cls, path_file: Path):
            verus_code = path_file.read_text(encoding="utf-8")
            instance = cls(verus_code)
            instance.filename = str(path_file)
            return instance

        def _get_declaration_start(self, node: Node) -> Node:
            """Get the start node of a declaration, including preceding doc comments.

            Doc comments (///) are sibling nodes that appear before declaration_with_attrs,
            so we need to look at the parent's children to find them.
            Regular comments (//) are ignored.
            """
            if not node.parent:
                return node

            # Find the index of the current node in parent's children
            parent = node.parent
            node_index = None
            for i, child in enumerate(parent.children):
                if child == node:
                    node_index = i
                    break

            if node_index is None:
                return node

            # Look backwards for doc comments
            start_index = node_index
            for i in range(node_index - 1, -1, -1):
                child = parent.children[i]
                # Check if this is a doc comment (has outer_doc_comment_marker child)
                is_doc_comment = False
                if child.type == "line_comment":
                    for grandchild in child.children:
                        if grandchild.type == "outer_doc_comment_marker":
                            is_doc_comment = True
                            break
                elif child.type == "block_comment":
                    # Block doc comments also exist
                    for grandchild in child.children:
                        if grandchild.type in [
                            "outer_doc_comment_marker",
                            "inner_doc_comment_marker",
                        ]:
                            is_doc_comment = True
                            break

                if is_doc_comment:
                    start_index = i
                else:
                    # Stop if we hit a non-doc-comment node
                    break

            # Return the first doc comment node if found, otherwise the original node
            return parent.children[start_index] if start_index < node_index else node

        def _extract_function_range(self, node: Node):
            """Record impl_range for a declaration_with_attrs wrapping a function_item."""
            func_node = None
            for child in node.children:
                if child.type == "function_item":
                    func_node = child
                    break

            if not func_node:
                return

            start_node = self._get_declaration_start(node)
            location = self._get_start(start_node)
            impl_range = [self._get_start(start_node), self._get_end(func_node)]
            self.map_func_info[location] = {"impl_range": impl_range}

        def _traverse(self, node: Node):
            if node.type == "declaration_with_attrs":
                for child in node.children:
                    if child.type == "function_item":
                        self._extract_function_range(node)
            for child in node.children:
                self._traverse(child)

        def get(self) -> dict:
            return {"functions": self.map_func_info}

except ImportError:
    # Default mode requires tree-sitter-verus; main() errors out if it is missing
    # unless --text-only was passed. Keep SimplifyParser/FunctionRangeParser as None
    # so --text-only mode (CompatSimplifyParser + fallback ranges) still works.
    SimplifyParser = None
    FunctionRangeParser = None


@dataclass(frozen=True)
class CandidateRange:
    start: int
    end: int
    line: int
    preview: str
    kind: str


@dataclass(frozen=True)
class FunctionRange:
    start: int
    end: int
    label: str


@dataclass
class SimplifyStats:
    files_processed: int = 0
    functions_processed: int = 0
    functions_skipped_unproven: int = 0
    attempted: int = 0
    removed: int = 0
    restored: int = 0
    assert_attempted: int = 0
    assert_removed: int = 0
    call_attempted: int = 0
    call_removed: int = 0
    verification_runs: int = 0

    def add(self, other: "SimplifyStats") -> None:
        self.files_processed += other.files_processed
        self.functions_processed += other.functions_processed
        self.functions_skipped_unproven += other.functions_skipped_unproven
        self.attempted += other.attempted
        self.removed += other.removed
        self.restored += other.restored
        self.assert_attempted += other.assert_attempted
        self.assert_removed += other.assert_removed
        self.call_attempted += other.call_attempted
        self.call_removed += other.call_removed
        self.verification_runs += other.verification_runs


class CompatSimplifyParser:
    """Compatibility parser with the subset used by src.refiner.simplifier."""

    def __init__(self, code: str):
        self.code = code
        self.asserts: list[dict[str, int]] = []
        self.calls: list[dict[str, int | bool]] = []
        self.admits: list[dict[str, int]] = []
        self.assumes: list[dict[str, int]] = []
        self.attributes: list[str] = []

    @classmethod
    def from_code(cls, code: str) -> "CompatSimplifyParser":
        return cls(code)

    def parse(self) -> None:
        masked = mask_comments_and_strings(self.code)
        self.attributes = (
            ["verifier::external_body"] if "verifier::external_body" in masked else []
        )
        self.admits = discover_calls(masked, self.code, "admit")
        self.assumes = discover_calls(masked, self.code, "assume")
        self.asserts = discover_asserts(masked, self.code)


def simplify_parser_from_code(code: str, text_only: bool = False):
    parser_type = CompatSimplifyParser if text_only else SimplifyParser
    parser = parser_type.from_code(code)
    parser.parse()
    return parser


def run_git(
    repo_root: Path,
    args: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        encoding="utf-8",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        encoding="utf-8",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return Path.cwd().resolve()


def split_path_args(values: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        for item in value.split(","):
            stripped = item.strip()
            if stripped:
                paths.append(Path(stripped))
    return paths


def normalize_path(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return repo_root / path


def relative_to_repo(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def changed_rs_files(repo_root: Path, base: str | None) -> list[Path]:
    names: list[str] = []
    if base:
        result = run_git(
            repo_root, ["diff", "--name-only", f"{base}...HEAD"], check=False
        )
        if result.returncode != 0:
            result = run_git(repo_root, ["diff", "--name-only", base], check=False)
        if result.returncode == 0:
            names.extend(
                line.strip() for line in result.stdout.splitlines() if line.strip()
            )
        else:
            detail = (result.stderr or result.stdout).strip()
            print(
                f"INFO: could not discover changed files from base {base!r}: {detail}"
            )

    worktree = run_git(repo_root, ["diff", "--name-only"], check=False)
    if worktree.returncode == 0:
        names.extend(
            line.strip() for line in worktree.stdout.splitlines() if line.strip()
        )

    seen: set[Path] = set()
    files: list[Path] = []
    for name in names:
        path = normalize_path(repo_root, Path(name))
        if path.suffix == ".rs" and path.exists() and path not in seen:
            files.append(path)
            seen.add(path)
    return files


def modified_hunks(
    repo_root: Path, base: str | None
) -> dict[Path, list[tuple[int, int]]]:
    """Return added-line ranges (1-based, inclusive) per file from `git diff`.

    Combines committed-diff (`base...HEAD`) and worktree diff. A function range
    counts as modified when any added line lands inside it. Only NEW (added)
    lines are considered — context lines that simply fall within an unchanged
    function do not mark it modified when the user only edited somewhere else.
    """
    hunks: dict[Path, list[tuple[int, int]]] = {}

    def add_ranges(diff_args: list[str]) -> None:
        result = run_git(repo_root, diff_args, check=False)
        if result.returncode != 0 or not result.stdout:
            return
        current_path: Path | None = None
        for line in result.stdout.splitlines():
            if line.startswith("+++ b/"):
                rel = line[len("+++ b/") :]
                current_path = normalize_path(repo_root, Path(rel)).resolve()
                hunks.setdefault(current_path, [])
            elif line.startswith("@@"):
                # Format: @@ -l,s +l,s @@ — we want the new-file side.
                match = re.search(r"\+(\d+)(?:,(\d+))?", line)
                if match and current_path is not None:
                    start = int(match.group(1))
                    count = int(match.group(2)) if match.group(2) else 1
                    if count > 0:
                        hunks[current_path].append((start, start + count - 1))

    if base:
        add_ranges(["diff", "-U0", "--no-color", f"{base}...HEAD"])
    add_ranges(["diff", "-U0", "--no-color"])
    return hunks


def range_line_span(text: str, byte_start: int, byte_end: int) -> tuple[int, int]:
    """Return the (first, last) 1-based line numbers spanned by a byte range."""
    start_line = byte_to_line_col(text, byte_start)[0]
    end_line = byte_to_line_col(text, max(byte_start, byte_end - 1))[0]
    return start_line, end_line


def collect_files(args: argparse.Namespace, repo_root: Path) -> list[Path]:
    explicit_files = split_path_args(args.file)
    if explicit_files:
        files = [normalize_path(repo_root, path) for path in explicit_files]
    else:
        target_dirs = split_path_args(args.target_dir)
        if target_dirs:
            files = []
            for target_dir in target_dirs:
                root = normalize_path(repo_root, target_dir)
                if root.is_file() and root.suffix == ".rs":
                    files.append(root)
                elif root.is_dir():
                    files.extend(sorted(root.rglob("*.rs")))
                else:
                    print(
                        f"WARN: target path does not exist or is not Rust: {target_dir}"
                    )
        else:
            files = changed_rs_files(repo_root, args.base)

    seen: set[Path] = set()
    result: list[Path] = []
    for path in files:
        path = path.resolve()
        if path.suffix == ".rs" and path.exists() and path not in seen:
            result.append(path)
            seen.add(path)
    return result


def byte_offset(text: str, offset: int) -> int:
    return len(text[:offset].encode("utf-8"))


def text_index_from_byte_offset(text: str, offset: int) -> int:
    return len(text.encode("utf-8")[:offset].decode("utf-8"))


def line_number(text: str, byte_start: int) -> int:
    return text.count("\n", 0, text_index_from_byte_offset(text, byte_start)) + 1


def byte_to_line_col(text: str, byte_start: int) -> tuple[int, int]:
    index = text_index_from_byte_offset(text, byte_start)
    line = text.count("\n", 0, index) + 1
    line_start = text.rfind("\n", 0, index)
    if line_start < 0:
        col = index + 1
    else:
        col = index - line_start
    return line, col


def line_col_to_byte(text: str, line: int, col: int) -> int | None:
    if line <= 0 or col <= 0:
        return None
    current_line = 1
    index = 0
    while current_line < line:
        next_index = text.find("\n", index)
        if next_index == -1:
            return None
        index = next_index + 1
        current_line += 1
    return byte_offset(text, index + col - 1)


def is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def is_rust_lifetime_start(text: str, index: int) -> bool:
    """Return whether the apostrophe at index starts a Rust lifetime."""
    if index + 1 >= len(text):
        return False
    first = text[index + 1]
    if not (first.isalpha() or first == "_"):
        return False

    end = index + 2
    while end < len(text) and is_ident_char(text[end]):
        end += 1

    # `'a'` is a character literal; `'a`, `'_`, and `'static` are lifetimes.
    return end >= len(text) or text[end] != "'"


def mask_comments_and_strings(text: str) -> str:
    chars = list(text)
    i = 0
    state = "code"
    block_depth = 0
    while i < len(chars):
        c = chars[i]
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if state == "code":
            if c == "/" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "line_comment"
                continue
            if c == "/" and nxt == "*":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "block_comment"
                block_depth = 1
                continue
            if c == '"':
                chars[i] = " "
                i += 1
                state = "string"
                continue
            if c == "'" and not is_rust_lifetime_start(text, i):
                chars[i] = " "
                i += 1
                state = "char"
                continue
        elif state == "line_comment":
            if c == "\n":
                state = "code"
            else:
                chars[i] = " "
        elif state == "block_comment":
            if c == "/" and nxt == "*":
                chars[i] = chars[i + 1] = " "
                block_depth += 1
                i += 2
                continue
            if c == "*" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                block_depth -= 1
                i += 2
                if block_depth == 0:
                    state = "code"
                continue
            if c != "\n":
                chars[i] = " "
        elif state == "string":
            if c == "\\":
                chars[i] = " "
                if i + 1 < len(chars):
                    chars[i + 1] = " "
                    i += 2
                    continue
            if c == '"':
                chars[i] = " "
                state = "code"
            elif c != "\n":
                chars[i] = " "
        elif state == "char":
            if c == "\\":
                chars[i] = " "
                if i + 1 < len(chars):
                    chars[i + 1] = " "
                    i += 2
                    continue
            if c == "'":
                chars[i] = " "
                state = "code"
            elif c != "\n":
                chars[i] = " "
        i += 1
    return "".join(chars)


def find_matching(text: str, start: int, open_ch: str, close_ch: str) -> int | None:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def find_statement_end(masked: str, start: int) -> int | None:
    i = start
    while i < len(masked):
        c = masked[i]
        if c in "({[":
            match = find_matching(masked, i, c, {"(": ")", "{": "}", "[": "]"}[c])
            if match is None:
                return None
            i = match + 1
            continue
        if c == ";":
            return i + 1
        i += 1
    return None


def discover_calls(masked: str, source: str, name: str) -> list[dict[str, int]]:
    calls = []
    idx = 0
    while True:
        idx = masked.find(name, idx)
        if idx == -1:
            break
        before = masked[idx - 1] if idx > 0 else " "
        after_idx = idx + len(name)
        after = masked[after_idx] if after_idx < len(masked) else " "
        if is_ident_char(before) or is_ident_char(after):
            idx = after_idx
            continue
        j = after_idx
        while j < len(masked) and masked[j].isspace():
            j += 1
        if j < len(masked) and masked[j] == "!":
            j += 1
            while j < len(masked) and masked[j].isspace():
                j += 1
        if j < len(masked) and masked[j] == "(":
            end = find_statement_end(masked, idx)
            if end is not None:
                calls.append(
                    {"start": byte_offset(source, idx), "end": byte_offset(source, end)}
                )
                idx = end
                continue
        idx = after_idx
    return calls


def discover_asserts(masked: str, source: str) -> list[dict[str, int]]:
    asserts = []
    idx = 0
    while True:
        idx = masked.find("assert", idx)
        if idx == -1:
            break
        before = masked[idx - 1] if idx > 0 else " "
        after_idx = idx + len("assert")
        after = masked[after_idx] if after_idx < len(masked) else " "
        if is_ident_char(before) or is_ident_char(after):
            idx = after_idx
            continue
        j = after_idx
        while j < len(masked) and masked[j].isspace():
            j += 1
        # Keep Rust runtime assert! calls. Verus proof asserts use assert(...).
        if j < len(masked) and masked[j] == "!":
            idx = j + 1
            continue
        if not (
            j < len(masked)
            and (
                masked[j] == "("
                or masked.startswith("forall", j)
                or masked.startswith("exists", j)
            )
        ):
            idx = j + 1
            continue
        end = find_statement_end(masked, idx)
        if end is None:
            idx = after_idx
            continue
        asserts.append(
            {"start": byte_offset(source, idx), "end": byte_offset(source, end)}
        )
        # Continue immediately after the keyword rather than after the whole
        # statement.  An assertion's `by` block may contain further assertions,
        # all of which must be considered independently.
        idx = after_idx
    return asserts


def is_assert_false(segment: str) -> bool:
    masked = mask_comments_and_strings(segment)
    return re.match(r"\s*assert\s*\(\s*false\s*\)", masked) is not None


def range_start_with_attributes(text: str, index: int) -> int:
    line_start = text.rfind("\n", 0, index) + 1
    start = line_start
    while start > 0:
        prev_end = start - 1
        prev_start = text.rfind("\n", 0, prev_end) + 1
        prev_line = text[prev_start:prev_end].strip()
        if not prev_line or prev_line.startswith("#["):
            start = prev_start
            continue
        break
    return byte_offset(text, start)


def fallback_function_ranges(path: Path, text: str) -> list[FunctionRange]:
    masked = mask_comments_and_strings(text)
    ranges: list[FunctionRange] = []
    idx = 0
    while True:
        idx = masked.find("fn", idx)
        if idx == -1:
            break
        before = masked[idx - 1] if idx > 0 else " "
        after_idx = idx + 2
        after = masked[after_idx] if after_idx < len(masked) else " "
        if is_ident_char(before) or is_ident_char(after):
            idx = after_idx
            continue

        scan = after_idx
        while scan < len(masked):
            char = masked[scan]
            if char == ";":
                break
            if char == "{":
                end = find_matching(masked, scan, "{", "}")
                if end is not None:
                    start_byte = range_start_with_attributes(text, idx)
                    end_byte = byte_offset(text, end + 1)
                    line, col = byte_to_line_col(text, byte_offset(text, idx))
                    ranges.append(
                        FunctionRange(
                            start=start_byte,
                            end=end_byte,
                            label=f"{path}:{line}:{col}",
                        )
                    )
                    idx = end + 1
                    break
                idx = after_idx
                break
            scan += 1
        else:
            idx = after_idx
            continue
        if idx < scan:
            idx = scan + 1
    return dedupe_ranges(ranges)


def parse_location_line(location: str) -> tuple[str | None, int, int]:
    match = re.match(r"^(.*):(\d+):(\d+)$", location)
    if not match:
        return None, -1, -1
    return match.group(1), int(match.group(2)), int(match.group(3))


def treesitter_function_ranges(path: Path, text: str) -> list[FunctionRange]:
    if FunctionRangeParser is None:
        return []

    try:
        parser = FunctionRangeParser.from_file(path.resolve())
        parser.parse()
        result = parser.get()
    except (
        Exception
    ) as err:  # pragma: no cover - parser availability is environment-specific.
        print(
            f"INFO: tree-sitter-verus could not parse {path}: {err}; using fallback parser."
        )
        return []

    ranges: list[FunctionRange] = []
    for loc, func in result.get("functions", {}).items():
        impl_range = func.get("impl_range") or []
        if len(impl_range) != 2:
            continue
        start_file, start_line, start_col = parse_location_line(impl_range[0])
        _, end_line, end_col = parse_location_line(impl_range[1])
        if start_file and Path(start_file).resolve() != path.resolve():
            continue
        start = line_col_to_byte(text, start_line, start_col)
        end = line_col_to_byte(text, end_line, end_col)
        if start is None or end is None or end <= start:
            continue
        start = range_start_with_attributes(
            text, text_index_from_byte_offset(text, start)
        )
        end = min(len(text.encode("utf-8")), end + 1)
        ranges.append(FunctionRange(start=start, end=end, label=loc))
    return dedupe_ranges(ranges)


def dedupe_ranges(ranges: list[FunctionRange]) -> list[FunctionRange]:
    seen: set[tuple[int, int]] = set()
    out: list[FunctionRange] = []
    for item in sorted(ranges, key=lambda r: (r.start, r.end)):
        key = (item.start, item.end)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def discover_function_ranges(
    path: Path, text: str, text_only: bool = False
) -> list[FunctionRange]:
    ranges: list[FunctionRange] = []
    if not text_only:
        ranges = treesitter_function_ranges(path, text)
    if ranges:
        return ranges
    ranges = fallback_function_ranges(path, text)
    if ranges:
        return ranges
    return [FunctionRange(0, len(text.encode("utf-8")), f"{path}:whole-file")]


def function_name_from_label(label: str) -> str:
    """Best-effort short function name from a FunctionRange label.

    tree-sitter labels are file:line:col locations, while the fallback parser uses
    the same shape. Neither carries the bare name, so callers that need a name
    use `function_name_from_slice` on the code instead.
    """
    return label.rsplit(":", 2)[0] if ":" in label else label


_DEF_NAME_RE = re.compile(
    r"\b(?:pub\s+)?(?:broadcast\s+)?(?:proof\s+|spec\s+|exec\s+)?"
    r"(?:const\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)"
)


def function_name_from_slice(code: str) -> str | None:
    """Extract the short name of the function defined by `code`."""
    masked = mask_comments_and_strings(code)
    for match in _DEF_NAME_RE.finditer(masked):
        # Skip the `fn` keyword when it appears inside a type/where clause by
        # requiring the match to be near the start of the slice.
        if match.start() < len(masked) * 0.75:
            return match.group(1)
    # Fall back to the first matching fn definition anywhere in the slice.
    match = _DEF_NAME_RE.search(masked)
    return match.group(1) if match else None


def match_function_filter(
    function_range: FunctionRange,
    code: str,
    needles: list[str],
) -> bool:
    """Return whether `function_range` should be processed given `needles`.

    A needle matches if it equals the function's short name, or appears as a
    path segment in the location label (so qualified names like
    `Impl::lemma_foo` also work).
    """
    if not needles:
        return True
    name = function_name_from_slice(code)
    label = function_range.label
    label_segments = label.split("::")
    for needle in needles:
        needle = needle.strip()
        if not needle:
            continue
        if name is not None and needle == name:
            return True
        # Allow needle to be a qualified path (`Mod::fn`); check trailing segments.
        needle_segments = needle.split("::")
        if any(seg and seg == name for seg in needle_segments) and name:
            return True
        if needle in label_segments:
            return True
    return False


def candidate_ranges_from_code(
    code: str,
    source_text: str,
    range_start: int,
    deep_clean: bool,
    text_only: bool = False,
) -> tuple[list[CandidateRange], bool]:
    parser = simplify_parser_from_code(code, text_only=text_only)
    has_external_body = any(
        "verifier::external_body"
        in (
            item
            if isinstance(item, str)
            else str(item.get("attribute", "")) if isinstance(item, dict) else str(item)
        )
        for item in parser.attributes
    )
    if not deep_clean and (parser.admits or parser.assumes or has_external_body):
        return [], True

    code_bytes = code.encode("utf-8")
    candidates: list[CandidateRange] = []
    for item in parser.asserts:
        start = int(item["start"])
        end = int(item["end"])
        semicolon = end
        while semicolon < len(code_bytes) and code_bytes[semicolon] in b" \t\r\n":
            semicolon += 1
        if semicolon < len(code_bytes) and code_bytes[semicolon] == ord(";"):
            end = semicolon + 1
        segment = code_bytes[start:end].decode("utf-8")
        if is_assert_false(segment):
            continue
        preview = " ".join(segment.strip().split())[:120]
        candidates.append(
            CandidateRange(
                start=range_start + start,
                end=range_start + end,
                line=line_number(source_text, range_start + start),
                preview=preview,
                kind="assert",
            )
        )
    for item in getattr(parser, "calls", []):
        if not bool(item.get("is_proof", False)):
            continue
        start = int(item["start"])
        end = int(item["end"])
        segment = code_bytes[start:end].decode("utf-8")
        preview = " ".join(segment.strip().split())[:120]
        candidates.append(
            CandidateRange(
                start=range_start + start,
                end=range_start + end,
                line=line_number(source_text, range_start + start),
                preview=preview,
                kind="call",
            )
        )
    # Process nested assertions before their containing assertion.  This keeps
    # every original byte range valid while simplify_file incrementally blanks
    # candidates from the same function.
    candidates.sort(key=lambda item: (item.end - item.start, item.start))
    return candidates, False


def run_shell(
    command: str, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        encoding="utf-8",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout if timeout > 0 else None,
    )


def run_verify(command: str, cwd: Path, timeout: int) -> bool:
    result = run_shell(command, cwd, timeout)
    return result.returncode == 0


def simplify_file(
    repo_root: Path,
    path: Path,
    verify_command: str,
    timeout: int,
    dry_run: bool,
    deep_clean: bool,
    batch: bool,
    functions: list[str] | None = None,
    modified_hunks_map: dict[Path, list[tuple[int, int]]] | None = None,
    text_only: bool = False,
) -> SimplifyStats:
    stats = SimplifyStats(files_processed=1)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"WARN: skipping non-UTF-8 file: {relative_to_repo(repo_root, path)}")
        return stats

    ranges = discover_function_ranges(path, text, text_only=text_only)
    if functions:
        ranges = [
            fn_range
            for fn_range in ranges
            if match_function_filter(
                fn_range,
                text.encode("utf-8")[fn_range.start : fn_range.end].decode("utf-8"),
                functions,
            )
        ]
        display_path = relative_to_repo(repo_root, path)
        names = ", ".join(n for n in functions if n)
        print(
            f"INFO: function filter '{names}' matched {len(ranges)} function(s) "
            f"in {display_path}."
        )
    if modified_hunks_map is not None:
        hunks = modified_hunks_map.get(path.resolve(), [])
        display_path = relative_to_repo(repo_root, path)
        if not hunks:
            print(
                f"INFO: --modified-only: no added lines in {display_path}; "
                f"skipping all functions."
            )
            ranges = []
        else:
            kept: list[FunctionRange] = []
            for fn_range in ranges:
                first, last = range_line_span(text, fn_range.start, fn_range.end)
                if any(
                    not (hunk_last < first or hunk_first > last)
                    for hunk_first, hunk_last in hunks
                ):
                    kept.append(fn_range)
            print(
                f"INFO: --modified-only: {len(kept)}/{len(ranges)} function(s) "
                f"overlap added diff hunks in {display_path}."
            )
            ranges = kept
    current_bytes = text.encode("utf-8")
    for function_range in ranges:
        stats.functions_processed += 1
        code = current_bytes[function_range.start : function_range.end].decode("utf-8")
        candidates, skipped_unproven = candidate_ranges_from_code(
            code,
            text,
            function_range.start,
            deep_clean,
            text_only=text_only,
        )
        if skipped_unproven:
            stats.functions_skipped_unproven += 1
            continue

        def record_attempt(item: CandidateRange, removed: bool) -> None:
            stats.attempted += 1
            if item.kind == "assert":
                stats.assert_attempted += 1
                if removed:
                    stats.assert_removed += 1
            else:
                stats.call_attempted += 1
                if removed:
                    stats.call_removed += 1
            if removed:
                stats.removed += 1
            else:
                stats.restored += 1

        display_path = relative_to_repo(repo_root, path)
        if dry_run:
            for item in candidates:
                stats.attempted += 1
                if item.kind == "assert":
                    stats.assert_attempted += 1
                else:
                    stats.call_attempted += 1
                print(
                    f"INFO: trying {item.kind} {display_path}:{item.line}: "
                    f"{item.preview}"
                )
            continue

        def blank_items(base: bytes, items: list[CandidateRange]) -> bytes:
            result = bytearray(base)
            for item in items:
                result[item.start : item.end] = b" " * (item.end - item.start)
            return bytes(result)

        def verify_candidate_bytes(candidate_bytes: bytes) -> bool:
            path.write_bytes(candidate_bytes)
            stats.verification_runs += 1
            try:
                return run_verify(verify_command, repo_root, timeout)
            except BaseException:
                path.write_bytes(current_bytes)
                raise

        if batch:

            def simplify_batch(items: list[CandidateRange]) -> None:
                nonlocal current_bytes
                if not items:
                    return
                print(
                    f"INFO: trying batch {display_path}: "
                    f"candidates={len(items)}, lines={items[0].line}-{items[-1].line}"
                )
                candidate_bytes = blank_items(current_bytes, items)
                if verify_candidate_bytes(candidate_bytes):
                    current_bytes = candidate_bytes
                    for item in items:
                        record_attempt(item, removed=True)
                    print(
                        f"INFO: removed redundant batch at {display_path}: "
                        f"candidates={len(items)}"
                    )
                    return

                path.write_bytes(current_bytes)
                if len(items) == 1:
                    item = items[0]
                    record_attempt(item, removed=False)
                    print(
                        f"INFO: kept required {item.kind} at "
                        f"{display_path}:{item.line}"
                    )
                    return

                midpoint = len(items) // 2
                simplify_batch(items[:midpoint])
                simplify_batch(items[midpoint:])

            simplify_batch(candidates)
            continue

        for item in candidates:
            print(
                f"INFO: trying {item.kind} {display_path}:{item.line}: "
                f"{item.preview}"
            )
            candidate_bytes = blank_items(current_bytes, [item])
            if verify_candidate_bytes(candidate_bytes):
                current_bytes = candidate_bytes
                record_attempt(item, removed=True)
                print(
                    f"INFO: removed redundant {item.kind} at "
                    f"{display_path}:{item.line}"
                )
            else:
                path.write_bytes(current_bytes)
                record_attempt(item, removed=False)
                print(
                    f"INFO: kept required {item.kind} at " f"{display_path}:{item.line}"
                )
    return stats


def modified_rs_files(repo_root: Path) -> list[str]:
    result = run_git(repo_root, ["diff", "--name-only"], check=False)
    if result.returncode != 0:
        print("WARN: failed to discover modified files for cleanup.")
        return []
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(".rs")
    ]


def added_empty_lines(repo_root: Path, file_path: str) -> list[int]:
    result = run_git(
        repo_root,
        ["diff", "-U0", "--no-color", "--", file_path],
        check=False,
    )
    if result.returncode != 0:
        print(f"WARN: failed to diff file for cleanup: {file_path}")
        return []

    lines_to_remove: list[int] = []
    current_line_number = 0
    for line in result.stdout.splitlines():
        if line.startswith("@@"):
            parts = line.split(" ")
            new_hunk_info = next((part for part in parts if part.startswith("+")), None)
            if new_hunk_info:
                new_hunk_info = new_hunk_info[1:]
                current_line_number = int(new_hunk_info.split(",", 1)[0])
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            if not content.strip():
                lines_to_remove.append(current_line_number)
            current_line_number += 1
    return lines_to_remove


def remove_lines(repo_root: Path, file_path: str, line_numbers: list[int]) -> int:
    if not line_numbers:
        return 0
    path = repo_root / file_path
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        print(f"WARN: skipping cleanup for non-UTF-8 file: {file_path}")
        return 0
    except FileNotFoundError:
        print(f"WARN: skipping cleanup for missing file: {file_path}")
        return 0

    removed = 0
    for line_number_to_remove in sorted(set(line_numbers), reverse=True):
        index = line_number_to_remove - 1
        if 0 <= index < len(lines) and not lines[index].strip():
            del lines[index]
            removed += 1
    if removed:
        path.write_text("".join(lines), encoding="utf-8")
    return removed


def cleanup_added_empty_lines(repo_root: Path) -> int:
    removed = 0
    for file_path in modified_rs_files(repo_root):
        removed += remove_lines(
            repo_root, file_path, added_empty_lines(repo_root, file_path)
        )
    if removed:
        print(f"INFO: cleanup removed {removed} formatter-introduced empty line(s).")
    return removed


def run_format_and_cleanup(args: argparse.Namespace, repo_root: Path) -> int:
    if args.dry_run or not args.format_command:
        return 0
    result = run_shell(args.format_command, repo_root, args.timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        print(f"WARN: format command failed: {detail}")
        return result.returncode
    if not args.no_cleanup:
        cleanup_added_empty_lines(repo_root)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=None,
        help="Optional git base ref for changed-file discovery, e.g. origin/main.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Workspace root. Defaults to git rev-parse --show-toplevel.",
    )
    parser.add_argument(
        "--verify-command",
        default=None,
        help="Verification command to run after each temporary assert removal.",
    )
    parser.add_argument(
        "--format-command",
        default=None,
        help="Optional formatter command to run after simplification, e.g. 'cargo fmt'.",
    )
    parser.add_argument(
        "--target-dir",
        action="append",
        default=[],
        help="Directory or comma-separated directories to scan recursively for .rs files.",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Specific .rs file or comma-separated files to simplify.",
    )
    parser.add_argument(
        "--function",
        action="append",
        default=[],
        help=(
            "Function name (or comma-separated names, optionally qualified with "
            "::) to restrict simplification to. Only functions whose short name "
            "matches are processed; all others are left untouched."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Per-command timeout in seconds; 0 disables.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidate proof assertions and standalone calls without editing.",
    )
    parser.add_argument(
        "--deep-clean",
        action="store_true",
        help="Simplify functions containing admits/assumes/external_body.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Try candidate groups first and bisect failed groups.",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Do not remove formatter-introduced added empty lines.",
    )
    parser.add_argument(
        "--modified-only",
        action="store_true",
        help=(
            "Only simplify functions that contain added lines in the current diff "
            "(committed diff against --base plus the worktree diff). Functions "
            "whose lines were not added by the change are left untouched. "
            "Intended for postprocess runs that should only touch newly changed "
            "proof code."
        ),
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help=(
            "Use text-based parsing only (asserts-only), without tree-sitter-verus. "
            "The default mode requires tree-sitter-verus installed; pass this flag "
            "to opt into the lower-precision text fallback for environments without it."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else git_root()

    verify_command = args.verify_command
    if not verify_command and not args.dry_run:
        print("INFO: assert simplification skipped; pass --verify-command.")
        return 0
    if not verify_command:
        verify_command = "true"

    if not args.text_only and SimplifyParser is None:
        print(
            "ERROR: tree-sitter-verus is required for the default mode but is not "
            "available. Install it (e.g. `cd <KVerus repo> && uv sync`), or pass "
            "--text-only for text-based (asserts-only) parsing.",
            file=sys.stderr,
        )
        return 1

    files = collect_files(args, repo_root)
    if not files:
        print("INFO: assert simplification found no Rust files.")
        return 0

    functions = split_path_args(args.function) if args.function else []
    function_names = [str(p) for p in functions] if functions else []
    modified_hunks_map = (
        modified_hunks(repo_root, args.base) if args.modified_only else None
    )
    total = SimplifyStats()
    for path in files:
        total.add(
            simplify_file(
                repo_root=repo_root,
                path=path,
                verify_command=verify_command,
                timeout=args.timeout,
                dry_run=args.dry_run,
                deep_clean=args.deep_clean,
                batch=args.batch,
                functions=function_names,
                modified_hunks_map=modified_hunks_map,
                text_only=args.text_only,
            )
        )

    format_status = run_format_and_cleanup(args, repo_root)
    print(
        "INFO: assert simplification "
        f"files={total.files_processed}, functions={total.functions_processed}, "
        f"skipped_unproven={total.functions_skipped_unproven}, "
        f"attempted={total.attempted}, removed={total.removed}, restored={total.restored}, "
        f"assert_attempted={total.assert_attempted}, "
        f"assert_removed={total.assert_removed}, "
        f"call_attempted={total.call_attempted}, "
        f"call_removed={total.call_removed}, "
        f"verification_runs={total.verification_runs}."
    )
    return format_status


if __name__ == "__main__":
    sys.exit(main())
