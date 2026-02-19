/**
 * Block plugin for OpenCode
 *
 * Provides file and directory protection using .block configuration files.
 * Intercepts file modification tools (edit, write, bash, patch) and blocks
 * them based on protection rules defined in .block files.
 *
 * This is the OpenCode equivalent of the Claude Code PreToolUse hook.
 */
import type { Plugin } from "opencode/plugin";
import { resolve, dirname } from "path";

/** Tools that modify files and should be checked against .block rules. */
const PROTECTED_TOOLS = new Set(["edit", "write", "bash", "patch"]);

/**
 * Maps OpenCode tool names to the names expected by protect_directories.py.
 * The Python script was originally written for Claude Code's tool naming.
 */
const TOOL_NAME_MAP: Record<string, string> = {
  edit: "Edit",
  write: "Write",
  bash: "Bash",
  patch: "Write",
};

/**
 * Build the JSON input that protect_directories.py expects on stdin.
 *
 * Claude Code hook input format:
 *   { "tool_name": "Edit", "tool_input": { "file_path": "..." } }
 *   { "tool_name": "Bash", "tool_input": { "command": "..." } }
 */
function buildHookInput(
  tool: string,
  args: Record<string, unknown>,
): string | null {
  const toolName = TOOL_NAME_MAP[tool];
  if (!toolName) return null;

  const toolInput: Record<string, unknown> = {};

  if (tool === "bash") {
    const command = args.command ?? args.cmd;
    if (!command) return null;
    toolInput.command = command;
  } else {
    // edit, write, patch all use filePath
    const filePath = args.filePath ?? args.file_path ?? args.file;
    if (!filePath) return null;
    toolInput.file_path = filePath;
  }

  return JSON.stringify({ tool_name: toolName, tool_input: toolInput });
}

/**
 * Locate protect_directories.py relative to this plugin file.
 * When installed via npm the layout is:
 *   node_modules/opencode-block/opencode/index.ts
 *   node_modules/opencode-block/hooks/protect_directories.py
 *
 * When used from the repo directly:
 *   opencode/index.ts
 *   hooks/protect_directories.py
 */
function findScript(): string {
  const pluginDir = import.meta.dir;
  return resolve(pluginDir, "..", "hooks", "protect_directories.py");
}

export const BlockPlugin: Plugin = async ({ $ }) => {
  const scriptPath = findScript();

  return {
    "tool.execute.before": async (input, output) => {
      if (!PROTECTED_TOOLS.has(input.tool)) return;

      const hookInput = buildHookInput(
        input.tool,
        output.args as Record<string, unknown>,
      );
      if (!hookInput) return;

      try {
        const result =
          await $`echo ${hookInput} | python3 ${scriptPath}`.quiet();
        const stdout = result.stdout.toString().trim();
        if (!stdout) return;

        const decision = JSON.parse(stdout);
        if (decision.decision === "block") {
          throw new Error(decision.reason);
        }
      } catch (err: unknown) {
        if (err instanceof SyntaxError) {
          // Python output wasn't JSON — not a block, ignore
          return;
        }
        // Re-throw block errors and unexpected failures
        throw err;
      }
    },
  };
};
