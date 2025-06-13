# truenas-smart-parser

Parse and analyze SMART data from TrueNAS drives with manufacturer-specific temperature threshold support.

## Features

- Parse SMART CSV logs from smartmontools
- Support for both ATA and NVMe drives
- Query live temperature thresholds from drives
- Health classification based on actual manufacturer limits
- 24-hour error tracking and temperature monitoring
- CLI and Python API

## Installation

```bash
uv pip install truenas-smart-parser
```

For development:
```bash
uv pip install -e ".[dev]"
```

## Usage

### Command Line

```bash
# Analyze local SMART data (rich tabular display by default)
truenas-smart-parser analyze /var/lib/smartmontools/

# Analyze remote TrueNAS via SSH
truenas-smart-parser analyze-remote nas

# Analyze with SSH threshold queries
truenas-smart-parser analyze /var/lib/smartmontools/ --ssh-host nas

# Use compact multi-line table layout (for wide tables)
truenas-smart-parser analyze /var/lib/smartmontools/ --compact
truenas-smart-parser analyze-remote nas --compact

# Use device mapping for better output (optional - auto-scan is default for remote)
truenas-smart-parser analyze /var/lib/smartmontools/ --device-map device_map.json

# Output as JSON instead of tables
truenas-smart-parser analyze /var/lib/smartmontools/ --json
truenas-smart-parser analyze-remote nas --json

# Enable verbose logging
truenas-smart-parser analyze-remote nas --verbose
```

The default output uses rich tables with color coding:
- 🟢 Green: Healthy drives
- 🟡 Yellow: Warning (high temp or existing errors)
- 🔴 Red: Critical (critical temp or new errors in 24h)

### Python API

```python
from truenas_smart_parser import analyze_smart_directory

# Basic usage
system_health = analyze_smart_directory("/var/lib/smartmontools/")

print(f"Total drives: {system_health.total_drives}")
print(f"Critical drives: {system_health.critical_drives}")

# With SSH for live thresholds
import subprocess

def ssh_exec(cmd):
    return subprocess.run(["ssh", "nas", cmd], 
                         capture_output=True, text=True).stdout

system_health = analyze_smart_directory(
    "/var/lib/smartmontools/",
    device_mapping={"1RJE48WM": "/dev/sda"},
    ssh_command=ssh_exec
)

# Access individual drives
for drive in system_health.drives:
    print(f"{drive.serial}: {drive.temperature_current}°C")
    if drive.temperature_critical:
        print(f"  Critical threshold: {drive.temperature_critical}°C")
```

## Health Classification

Drives are classified as:

- **Critical**: Temperature ≥ critical threshold OR new errors in last 24h
- **Warning**: Temperature ≥ warning/operational threshold OR existing errors
- **Healthy**: No temperature or error issues

Temperature thresholds are queried from drives:
- **ATA**: Operational limit (60°C), Damage threshold (70°C)
- **NVMe**: Warning (85°C), Critical (95°C)

## Requirements

- Python ≥ 3.13
- smartmontools installed on target system
- SSH access for remote monitoring

## License

GPL-2 or newer