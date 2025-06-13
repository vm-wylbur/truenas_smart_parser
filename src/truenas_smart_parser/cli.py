# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# Copyright (C) 2025 HRDAG https://hrdag.org
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#
# ------
# truenas-smart-parser/src/truenas_smart_parser/cli.py

"""Command-line interface for NAS SMART data analysis."""

import json
import subprocess
from pathlib import Path

import typer
from loguru import logger

from .parser import analyze_smart_directory

app = typer.Typer()


def ssh_exec_factory(host: str):
    """Create an SSH command executor for a specific host."""
    def ssh_exec(command: str) -> str:
        result = subprocess.run(
            ["ssh", host, command],
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout
    return ssh_exec


@app.command()
def analyze(
    smart_dir: Path = typer.Argument(
        ...,
        help="Directory containing SMART CSV files"
    ),
    device_map: Path | None = typer.Option(
        None,
        "--device-map",
        help="JSON file mapping serial numbers to device paths"
    ),
    ssh_host: str | None = typer.Option(
        None,
        "--ssh-host",
        help="SSH host for querying live temperature thresholds"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON"
    ),
):
    """Analyze SMART data from CSV files."""
    try:
        # Load device mapping if provided
        device_mapping = {}
        if device_map and device_map.exists():
            with open(device_map) as f:
                device_mapping = json.load(f)

        # Create SSH command function if host provided
        ssh_command = None
        if ssh_host:
            ssh_command = ssh_exec_factory(ssh_host)
            logger.info(f"Using SSH host {ssh_host} for threshold queries")

        # Analyze drives
        logger.info(f"Analyzing SMART data in {smart_dir}")
        system_health = analyze_smart_directory(
            smart_dir,
            device_mapping=device_mapping,
            ssh_command=ssh_command
        )

        if json_output:
            # Convert to JSON-serializable format
            output = {
                "summary": {
                    "total_drives": system_health.total_drives,
                    "healthy_drives": system_health.healthy_drives,
                    "warning_drives": system_health.warning_drives,
                    "critical_drives": system_health.critical_drives,
                    "max_temperature": system_health.max_temperature,
                    "total_errors_24h": system_health.total_errors_24h,
                },
                "drives": [
                    {
                        "device_path": d.device_path,
                        "serial": d.serial,
                        "type": d.drive_type,
                        "temperature_current": d.temperature_current,
                        "temperature_max_24h": d.temperature_max_24h,
                        "temperature_warning": d.temperature_warning,
                        "temperature_critical": d.temperature_critical,
                        "errors_24h": (
                            d.reallocated_sectors_24h +
                            d.pending_sectors_24h +
                            d.media_errors_24h
                        ),
                        "power_on_hours": d.power_on_hours,
                    }
                    for d in system_health.drives
                ],
            }
            typer.echo(json.dumps(output, indent=2))
        else:
            # Human-readable output
            typer.echo("System Health Summary")
            typer.echo("=" * 50)
            typer.echo(f"Total drives: {system_health.total_drives}")
            typer.echo(f"  ✅ Healthy: {system_health.healthy_drives}")
            typer.echo(f"  ⚠️  Warning: {system_health.warning_drives}")
            typer.echo(f"  ❌ Critical: {system_health.critical_drives}")
            typer.echo()
            max_temp = system_health.max_temperature
            typer.echo(f"Max temperature: {max_temp:.1f}°C")
            typer.echo(f"Total errors (24h): {system_health.total_errors_24h}")

            if system_health.critical_drives > 0:
                typer.echo()
                typer.echo("Critical Drives:")
                for drive in system_health.drives:
                    temp_check = ""
                    if (drive.temperature_current and
                        drive.temperature_critical and
                        drive.temperature_current >= drive.temperature_critical):
                        temp_check = (
                            f" (≥{drive.temperature_critical}°C threshold)"
                        )

                    errors = (
                        drive.reallocated_sectors_24h +
                        drive.pending_sectors_24h +
                        drive.media_errors_24h
                    )
                    if errors > 0 or temp_check:
                        typer.echo(
                            f"  - {drive.device_path} ({drive.serial}): "
                            f"{drive.temperature_current}°C{temp_check}, "
                            f"{errors} new errors"
                        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise typer.Exit(1)


@app.command()
def scan(
    ssh_host: str = typer.Argument(..., help="SSH host to scan for drives"),
    output: Path = typer.Option(
        "device_map.json",
        "--output",
        "-o",
        help="Output file for device mapping"
    ),
):
    """Scan remote host for drives and create device mapping."""
    try:
        ssh_exec = ssh_exec_factory(ssh_host)

        logger.info(f"Scanning drives on {ssh_host}")
        scan_output = ssh_exec("smartctl --scan")

        device_mapping = {}
        for line in scan_output.strip().split('\n'):
            if not line:
                continue

            parts = line.split()
            device = parts[0]

            # Get serial number
            info = ssh_exec(
                f"smartctl -i {device} | grep 'Serial Number' | "
                f"awk '{{print $3}}'"
            )
            serial = info.strip()

            if serial:
                device_mapping[serial] = device
                logger.info(f"  Found {device}: {serial}")

        # Save mapping
        with open(output, 'w') as f:
            json.dump(device_mapping, f, indent=2)

        typer.echo(f"Found {len(device_mapping)} drives")
        typer.echo(f"Device mapping saved to {output}")

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
