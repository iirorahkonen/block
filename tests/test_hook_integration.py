"""Integration tests for the protect_directories.py hook."""

import subprocess
import sys
from pathlib import Path

# Get the hooks directory as absolute path
HOOKS_DIR = (Path(__file__).parent.parent / "hooks").resolve()
PROTECT_SCRIPT = HOOKS_DIR / "protect_directories.py"
RUN_HOOK_CMD = HOOKS_DIR / "run-hook.cmd"


def to_posix_path(path) -> str:
    """Convert path to forward slashes for JSON compatibility."""
    return str(path).replace("\\", "/")


def run_hook(input_json: str, cwd: str = None) -> tuple[str, int]:
    """Run the hook with given JSON input and return (output, exit_code).

    This calls Python directly (fast, but doesn't test the real execution path).
    Use run_hook_cmd() to test the actual Claude Code execution path.
    """
    result = subprocess.run(
        [sys.executable, str(PROTECT_SCRIPT)],
        input=input_json,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout + result.stderr, result.returncode


def run_hook_cmd(input_json: str, cwd: str = None) -> tuple[str, int]:
    """Run the hook via run-hook.cmd (matches Claude Code's real execution path).

    This tests the actual polyglot script execution, including:
    - Execute permissions (Unix/Mac requires +x to execute scripts directly)
    - Polyglot Windows/Unix compatibility
    - Python detection logic
    - Cross-platform compatibility

    On Unix/Mac, the script must have execute permissions to run directly.
    This matches how Claude Code executes hooks and would catch permission bugs.
    """
    import os

    # Detect platform and use appropriate execution method
    if os.name == 'nt':  # Windows
        # On Windows, .cmd files are executable by file association
        result = subprocess.run(
            [str(RUN_HOOK_CMD)],
            input=input_json,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    else:  # Unix/Mac
        # On Unix, run via shell which executes the script directly
        # This requires +x permission (the bug we're testing for!)
        result = subprocess.run(
            f'"{RUN_HOOK_CMD}"',
            input=input_json,
            capture_output=True,
            text=True,
            cwd=cwd,
            shell=True,
        )
    return result.stdout + result.stderr, result.returncode


class TestHookIntegration:
    """Test the protect_directories.py hook directly."""

    def test_blocks_when_block_file_exists(self, tmp_path):
        """Hook should block when .block file exists in directory."""
        (tmp_path / ".block").write_text("{}")
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block decision, got: {output}"

    def test_allows_when_no_block_file(self, tmp_path):
        """Hook should allow (no output) when no .block file exists."""
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook(input_json, cwd=str(tmp_path))

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert "block" not in output.lower(), f"Expected allow (no block), got: {output}"

    def test_detects_block_in_parent_directory(self, tmp_path):
        """Hook should detect .block file in parent directory."""
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        (parent / ".block").write_text("{}")
        file_path = to_posix_path(child / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(child))

        assert "block" in output.lower(), f"Expected block from parent .block, got: {output}"

    def test_detects_block_local_file(self, tmp_path):
        """Hook should detect .block.local file."""
        (tmp_path / ".block.local").write_text("{}")
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block decision, got: {output}"

    def test_allowed_pattern_permits_matching_file(self, tmp_path):
        """Hook should allow files matching allowed patterns."""
        (tmp_path / ".block").write_text('{"allowed": ["*.txt"]}')
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" not in output.lower(), f"Expected allow for *.txt pattern, got: {output}"

    def test_allowed_pattern_blocks_non_matching_file(self, tmp_path):
        """Hook should block files not matching allowed patterns."""
        (tmp_path / ".block").write_text('{"allowed": ["*.txt"]}')
        file_path = to_posix_path(tmp_path / "test.js")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block for non-matching file, got: {output}"


class TestWorkingDirectoryIndependence:
    """Test that protection works regardless of working directory.

    These tests verify the fix for the bug where the quick check used
    the current working directory instead of the target file's directory.
    This caused .block files in subdirectories to be missed when the
    working directory was set to the project root.
    """

    def test_blocks_when_cwd_is_parent_of_block_directory(self, tmp_path):
        """Hook should block when .block is in subdirectory and cwd is parent.

        This is the main scenario that was broken:
        - Project root: /project (cwd)
        - .block file: /project/subdir/.block
        - Target file: /project/subdir/file.txt

        The old quick check would start at /project and walk UP,
        never finding the .block file in the subdirectory.
        """
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / ".block").write_text("{}")
        file_path = to_posix_path(subdir / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        # Run with cwd set to PARENT (tmp_path), not the subdir
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block when cwd is parent of .block dir, got: {output}"

    def test_blocks_deeply_nested_file_when_cwd_is_root(self, tmp_path):
        """Hook should block deeply nested files when cwd is project root."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (tmp_path / "a" / ".block").write_text("{}")
        file_path = to_posix_path(nested / "deep.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block for deeply nested file, got: {output}"

    def test_allows_when_block_only_in_sibling_directory(self, tmp_path):
        """Hook should allow when .block is only in a sibling directory."""
        protected = tmp_path / "protected"
        unprotected = tmp_path / "unprotected"
        protected.mkdir()
        unprotected.mkdir()
        (protected / ".block").write_text("{}")
        file_path = to_posix_path(unprotected / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook(input_json, cwd=str(tmp_path))

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert "block" not in output.lower(), f"Expected allow for sibling dir, got: {output}"

    def test_blocks_with_pattern_when_cwd_is_parent(self, tmp_path):
        """Hook should correctly evaluate patterns when cwd is parent."""
        subdir = tmp_path / "snapshots"
        subdir.mkdir()
        (subdir / ".block").write_text('{"blocked": ["*.verified.json"]}')
        file_path = to_posix_path(subdir / "test.verified.json")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block for pattern match, got: {output}"

    def test_allows_non_matching_pattern_when_cwd_is_parent(self, tmp_path):
        """Hook should allow non-matching patterns when cwd is parent."""
        subdir = tmp_path / "snapshots"
        subdir.mkdir()
        (subdir / ".block").write_text('{"blocked": ["*.verified.json"]}')
        file_path = to_posix_path(subdir / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook(input_json, cwd=str(tmp_path))

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert "block" not in output.lower(), f"Expected allow for non-matching pattern, got: {output}"

    def test_allows_unprotected_target_when_cwd_is_protected(self, tmp_path):
        """Hook should allow targeting unprotected files even when CWD is protected.

        This tests the reverse scenario: running from a protected directory
        but targeting an absolute path in an unprotected directory.
        """
        protected = tmp_path / "protected"
        unprotected = tmp_path / "unprotected"
        protected.mkdir()
        unprotected.mkdir()
        (protected / ".block").write_text("{}")
        file_path = to_posix_path(unprotected / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook(input_json, cwd=str(protected))

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert "block" not in output.lower(), (
            f"Should NOT block unprotected target when CWD is protected, got: {output}"
        )

    def test_write_tool_respects_cwd_independence(self, tmp_path):
        """Write tool should block based on target path, not CWD."""
        protected = tmp_path / "protected"
        protected.mkdir()
        (protected / ".block").write_text("{}")
        file_path = to_posix_path(protected / "new_file.txt")

        input_json = f'{{"tool_name": "Write", "tool_input": {{"file_path": "{file_path}", "content": "test"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Write tool should be blocked, got: {output}"

    def test_bash_tool_respects_cwd_independence(self, tmp_path):
        """Bash tool should block based on target path, not CWD."""
        protected = tmp_path / "protected"
        protected.mkdir()
        (protected / ".block").write_text("{}")
        file_path = to_posix_path(protected / "file.txt")

        input_json = f'{{"tool_name": "Bash", "tool_input": {{"command": "touch {file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Bash tool should be blocked, got: {output}"


class TestRealExecutionPath:
    """Test the actual run-hook.cmd execution path (matches Claude Code behavior).

    These tests execute run-hook.cmd directly, exactly as Claude Code does.
    This catches issues that direct Python execution misses:
    - Missing execute permissions (chmod +x)
    - Shebang/polyglot script issues
    - Python detection failures
    - Cross-platform compatibility

    This would have caught the permission bug that was fixed in v1.1.12.
    """

    def test_hook_script_is_executable(self):
        """Verify run-hook.cmd has execute permissions (critical for Unix/Mac)."""
        import os
        import stat

        mode = os.stat(RUN_HOOK_CMD).st_mode
        is_executable = bool(mode & stat.S_IXUSR)

        assert is_executable, (
            f"{RUN_HOOK_CMD} is not executable (mode: {oct(mode)}). "
            f"Run: chmod +x {RUN_HOOK_CMD}"
        )

    def test_blocks_via_hook_cmd(self, tmp_path):
        """Test blocking via run-hook.cmd (real Claude Code execution path)."""
        (tmp_path / ".block").write_text("{}")
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook_cmd(input_json, cwd=str(tmp_path))

        assert exit_code == 0, f"Hook should exit 0 even when blocking, got: {exit_code}"
        assert "block" in output.lower(), f"Expected block decision via hook cmd, got: {output}"

    def test_allows_via_hook_cmd(self, tmp_path):
        """Test allowing via run-hook.cmd (no .block file)."""
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook_cmd(input_json, cwd=str(tmp_path))

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert "block" not in output.lower(), f"Expected allow (no block), got: {output}"

    def test_pattern_matching_via_hook_cmd(self, tmp_path):
        """Test pattern matching via run-hook.cmd."""
        (tmp_path / ".block").write_text('{"blocked": ["*.secret"]}')
        secret_file = to_posix_path(tmp_path / "api.secret")
        safe_file = to_posix_path(tmp_path / "readme.txt")

        # Should block .secret file
        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{secret_file}"}}}}'
        output, _ = run_hook_cmd(input_json, cwd=str(tmp_path))
        assert "block" in output.lower(), f"Expected block for *.secret, got: {output}"

        # Should allow other files
        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{safe_file}"}}}}'
        output, _ = run_hook_cmd(input_json, cwd=str(tmp_path))
        assert "block" not in output.lower(), f"Expected allow for .txt, got: {output}"

    def test_bash_command_detection_via_hook_cmd(self, tmp_path):
        """Test Bash command path extraction via run-hook.cmd."""
        (tmp_path / ".block").write_text("{}")
        file_path = to_posix_path(tmp_path / "output.txt")

        # Test output redirection detection
        input_json = f'{{"tool_name": "Bash", "tool_input": {{"command": "echo test > {file_path}"}}}}'
        output, _ = run_hook_cmd(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block for bash redirection, got: {output}"

    def test_python_fallback_message_via_hook_cmd(self, tmp_path, monkeypatch):
        """Test Python not found fallback message via run-hook.cmd.

        Note: This test is platform-dependent and may be skipped if
        it interferes with the actual Python detection in run-hook.cmd.
        """
        # This test is difficult to implement without breaking the hook
        # We'd need to modify PATH to hide Python, which could break pytest
        # Skip this test for now, but document the expected behavior
        import pytest
        pytest.skip(
            "Difficult to test Python fallback without breaking test runner. "
            "Expected behavior: hook should output JSON with Python requirement message "
            "if python3/python not found in PATH."
        )

    def test_hierarchical_protection_via_hook_cmd(self, tmp_path):
        """Test directory hierarchy traversal via run-hook.cmd."""
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        (parent / ".block").write_text("{}")
        file_path = to_posix_path(child / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook_cmd(input_json, cwd=str(child))

        assert "block" in output.lower(), f"Expected block from parent .block, got: {output}"
