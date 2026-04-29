# kiro-gateway-launcher

CLI launcher for [kiro-gateway](https://github.com/jwadow/kiro-gateway) that enables easy installation via `uv tool install`.

## Overview

`kiro-gateway-launcher` wraps the upstream `kiro-gateway` project, providing:

- **Easy installation** via `uv tool install`
- **Runtime git clone** of kiro-gateway source to `~/.local/share/kiro-gateway-launcher/repo/`
- **Interactive setup wizard** with auto-detection of kiro-cli/amazon-q SQLite databases
- **Configuration editor** for managing all environment variables
- **Update command** to pull latest changes from upstream

## Dependencies

This project depends on:

- [kiro-gateway](https://github.com/jwadow/kiro-gateway) - The upstream proxy server
- [uv](https://docs.astral.sh/uv/) - Python package manager

## Installation

```bash
# Install via uv
uv tool install git+https://github.com/Hunter-Leo/kiro-gateway-launcher.git
```

## Quick Start

```bash
# First run - will launch setup wizard
kiro-gateway-launcher

# Or manually configure
kiro-gateway-launcher config --edit
```

## Commands

### Start Server (default)

```bash
# Start with default settings
kiro-gateway-launcher

# Start with custom host/port
kiro-gateway-launcher -H 127.0.0.1 -p 8080
```

### Configuration Management

```bash
# View/edit configuration
kiro-gateway-launcher config

# Re-run setup wizard
kiro-gateway-launcher config --edit

# Show config file path
kiro-gateway-launcher config --show-path

# Reset configuration
kiro-gateway-launcher config --reset
```

### Update

```bash
# Pull latest kiro-gateway source
kiro-gateway-launcher update
```

## Configuration Variables

Configuration is stored in `~/.config/kiro-gateway/.env`.

### Credentials

| Variable | Description | Default |
|----------|-------------|---------|
| `REFRESH_TOKEN` | Kiro refresh token (from IDE network traffic) | - |
| `KIRO_CREDS_FILE` | Path to Kiro credentials JSON file | - |
| `KIRO_CLI_DB_FILE` | Path to kiro-cli SQLite database (AWS SSO) | - |

**Note:** At least one credential source must be configured.

### Server

| Variable | Description | Default |
|----------|-------------|---------|
| `PROXY_API_KEY` | Client auth key (clients pass this as Bearer token) | `my-super-secret-password-123` |
| `SERVER_HOST` | Bind address | `0.0.0.0` |
| `SERVER_PORT` | Server port | `8001` |

### Network

| Variable | Description | Default |
|----------|-------------|---------|
| `VPN_PROXY_URL` | Proxy for Kiro API (GFW / corporate networks) | - |
| `KIRO_REGION` | AWS region | `us-east-1` |
| `KIRO_API_REGION` | Kiro API region (if different from AWS region) | - |
| `PROFILE_ARN` | AWS Profile ARN for per-account override | - |

### Advanced

| Variable | Description | Default | Allowed Values |
|----------|-------------|---------|----------------|
| `LOG_LEVEL` | Log verbosity | `INFO` | `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `FIRST_TOKEN_TIMEOUT` | Seconds to wait for first token before retry | `15` | - |
| `STREAMING_READ_TIMEOUT` | Seconds to wait between chunks during streaming | `300` | - |
| `FIRST_TOKEN_MAX_RETRIES` | Max retry attempts on first token timeout | `3` | - |
| `TRUNCATION_RECOVERY` | Inject synthetic messages on API truncation | `true` | `true`, `false` |
| `TOOL_DESCRIPTION_MAX_LENGTH` | Max chars for tool descriptions (0 = disabled) | `10000` | - |
| `DEBUG_MODE` | Save debug logs | `off` | `off`, `errors`, `all` |
| `DEBUG_DIR` | Directory for debug log files | `debug_logs` | - |
| `FAKE_REASONING` | Enable extended thinking via tag injection | `true` | `true`, `false` |
| `FAKE_REASONING_MAX_TOKENS` | Max thinking tokens | `4000` | - |
| `FAKE_REASONING_BUDGET_CAP` | Max thinking budget cap (0 = disabled) | `10000` | - |
| `FAKE_REASONING_HANDLING` | How to handle thinking blocks in responses | `as_reasoning_content` | See below |

#### FAKE_REASONING_HANDLING Options

| Value | Description |
|-------|-------------|
| `as_reasoning_content` | Return as reasoning_content field (recommended) |
| `remove` | Remove thinking block completely |
| `pass` | Pass through with original tags |
| `strip_tags` | Remove tags but keep content |

## Credential Setup

### Option 1: Refresh Token

1. Open browser DevTools (F12) → Network tab
2. Use Kiro IDE and look for API requests
3. Find the `refresh_token` in request headers or body
4. Run `kiro-gateway-launcher config --edit` and select "Refresh token"

### Option 2: Credentials JSON File

1. Locate your Kiro credentials JSON file
2. Run `kiro-gateway-launcher config --edit` and select "JSON credentials file"
3. Enter the path to your credentials file

### Option 3: SQLite Database (Auto-detected)

The setup wizard can auto-detect installed kiro-cli or amazon-q SQLite databases:

- `~/.local/share/kiro-cli/data.sqlite3` (Linux/macOS)
- `~/.local/share/amazon-q/data.sqlite3` (Linux/macOS)
- `~/Library/Application Support/kiro-cli/data.sqlite3` (macOS)

## How It Works

1. **ConfigLoader** loads environment variables from `~/.config/kiro-gateway/.env`
2. **RepoManager** clones kiro-gateway to `~/.local/share/kiro-gateway-launcher/repo/` (if not exists)
3. **sys.path injection** enables `import kiro` from the cloned repo
4. **SetupWizard** guides first-time credential configuration
5. **uvicorn** starts the FastAPI server

## Troubleshooting

### "No valid Kiro credentials found"

Run the setup wizard:
```bash
kiro-gateway-launcher config --edit
```

### "cannot import kiro-gateway"

Update the kiro-gateway source:
```bash
kiro-gateway-launcher update
```

### "GitHub API rate limit exceeded"

The `update` command now uses `git fetch` directly, avoiding GitHub API rate limits.

### "thinking budget exceeds cap"

Set `FAKE_REASONING_BUDGET_CAP=0` to disable the cap:
```bash
kiro-gateway-launcher config
# Select FAKE_REASONING_BUDGET_CAP and enter 0
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Related Projects

- [kiro-gateway](https://github.com/jwadow/kiro-gateway) - The upstream proxy server
- [uv](https://docs.astral.sh/uv/) - Python package manager
