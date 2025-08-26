# Talon - CrowdStrike Falcon API Monitor

An interactive REPL for monitoring CrowdStrike Falcon API alerts in real-time.

## Features

- 🔄 Real-time alert monitoring with customizable polling intervals
- 🎨 Rich terminal UI with colors and interactive navigation
- 🔍 Advanced filtering by severity, product, hostname, status, and keywords
- 📊 Live statistics and alert volume tracking
- 💾 Persistent connection management and configuration
- 📝 Multiple output formats (console, JSON, CSV) with logging support
- 🔐 Secure credential storage and token management
- ⚡ Optimized API usage with rate limiting and error handling

## Interface
<img width="1884" height="740" alt="image2" src="https://github.com/user-attachments/assets/fedf8504-22d7-4443-abfb-1ddf337e0126" />

## Installation

### Via pipx (Recommended)

```bash
pipx install git+https://github.com/Mercury0/talon
```

### From Source

```bash
git clone https://github.com/Mercury0/talon.git
cd talon
pip install -e .
```

## Quick Start

1. **Run Talon:**
   ```bash
   talon
   ```

2. **Create a connection:**
   ```
   > keys
   keys> create
   Enter Falcon ClientID: your_client_id
   Enter Secret: your_secret
   Enter Base URL: https://api.crowdstrike.com
   ```

3. **Connect and start monitoring:**
   ```
   keys> back
   > connect
   ```

## Usage

### Commands

**Root Menu:**
- `keys` - Manage API connections
- `connect` - Initial authentication to Falcon API
- `run` - Resume alert monitoring on existing Falcon connection
- `config` - Configure settings
- `stats` - View alert statistics
- `help` - Show help information
- `exit` - Exit the application

**Keys Menu:**
- `create` - Add new API connection
- `list` - View and select connections
- `remove` - Delete connections

**Config Menu:**
- `polling` - Set polling interval (default: 15s)
- `filter` - Configure alert filters
- `output` - Set output format (console/json/csv)
- `logging` - Enable/disable file logging

### Filtering

Configure filters to focus on specific alerts:

```
config> filter
Configure [s]everity/[p]roduct/[h]ostname/s[t]atus/[k]eywords/[c]lear/[q]uit: s
Minimum severity (empty to clear): 30
```

### Output Formats

- **Console**: Colorized real-time display (default)
- **JSON**: Machine-readable JSON output
- **CSV**: Comma-separated values for spreadsheets

## Configuration

Talon stores connections and settings in `~/.talon/config.json`.

## API Requirements

You'll need CrowdStrike Falcon API credentials with the following scopes:
- **Alerts**: Read access to query and fetch alert data

## Development

```bash
git clone https://github.com/Mercury0/talon.git
cd talon
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Type checking
mypy src/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

