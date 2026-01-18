# claude-block

File and directory protection for Claude Code using `.claude-block` configuration files.

## Installation

1. Register the marketplace:

```
/plugin marketplace add iirorahkonen/claude-block-marketplace
```

2. Install the plugin:

```
/plugin install claude-block@claude-block-marketplace
```

## Usage

### Creating Protection Files

Use the `/claude-block` skill to interactively create a `.claude-block` file:

```
/claude-block
```

### Manual Creation

Create a `.claude-block` file in any directory you want to protect.

### Local Configuration Files

For personal or machine-specific protection rules that shouldn't be committed to git, use `.claude-block.local`:

```json
// .claude-block.local - not committed to git
{
  "blocked": [".personal-config", "local-secrets/**/*"]
}
```

Add `.claude-block.local` to your `.gitignore`:

```
.claude-block.local
```

When both `.claude-block` and `.claude-block.local` exist in the same directory:
- **Blocked patterns**: Combined (union) - files blocked by either config are protected
- **Allowed patterns**: Local overrides main
- **Guide messages**: Local takes precedence
- **Note**: Cannot mix `allowed` and `blocked` modes between the two files

## .claude-block Format

The `.claude-block` file uses JSON format with three modes:

### Block All (Default)

Empty file or `{}` blocks all modifications:

```json
{}
```

### Allowed List

Only allow specific patterns, block everything else:

```json
{
  "allowed": ["*.test.ts", "tests/**/*", "docs/*.md"]
}
```

### Blocked List

Block specific patterns, allow everything else:

```json
{
  "blocked": ["*.config.js", "secrets/**/*", "*.env*"]
}
```

### Guide Messages

Add a message shown when Claude tries to modify protected files:

```json
{
  "blocked": ["migrations/**/*"],
  "guide": "Database migrations are protected. Ask before modifying."
}
```

### Pattern-Specific Guides

Different messages for different patterns:

```json
{
  "blocked": [
    { "pattern": "*.env*", "guide": "Environment files contain secrets." },
    { "pattern": "config/**", "guide": "Config files require review." }
  ],
  "guide": "This directory has protected files."
}
```

## Pattern Syntax

| Pattern | Description |
|---------|-------------|
| `*` | Matches any characters except path separator |
| `**` | Matches any characters including path separator (recursive) |
| `?` | Matches single character |

### Examples

| Pattern | Matches |
|---------|---------|
| `*.ts` | All TypeScript files in the directory |
| `**/*.ts` | All TypeScript files recursively |
| `src/**/*` | Everything under src/ |
| `*.test.*` | Files with .test. in the name |
| `config?.json` | config1.json, configA.json, etc. |

## How It Works

1. When Claude tries to modify a file, the hook checks for `.claude-block` and `.claude-block.local` in the target directory and all parent directories
2. If found, both files are read and their configurations are merged
3. The hook evaluates the patterns against the target file path
4. Based on the mode (block-all, allowed-list, blocked-list), the operation is allowed or blocked
5. If blocked, the guide message (if any) is shown to help Claude understand why

## Protection Rules

- `.claude-block` and `.claude-block.local` files cannot be modified or deleted by Claude once created
- Protection applies to all files in the directory and subdirectories
- The closest configuration file(s) to the target takes precedence
- When both `.claude-block` and `.claude-block.local` exist, they are merged
- Invalid configurations (both `allowed` and `blocked` specified, or mixed modes between files) will block all operations

## Plugin Structure

```
claude-block/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── hooks/
│   ├── hooks.json           # Hook configuration
│   └── protect-directories.ps1  # Protection enforcement
├── skills/
│   └── claude-block/
│       └── SKILL.md         # Interactive creator skill
├── LICENSE
└── README.md
```

## License

MIT
