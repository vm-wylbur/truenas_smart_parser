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
from rich.console import Console

from .display import display_system_health
from .parser import analyze_smart_directory, analyze_smart_remote

app = typer.Typer()


def ssh_exec_factory(host: str, ssh_options: list[str] | None = None):
    """Create an SSH command executor for a specific host.
    
    Args:
        host: SSH hostname
        ssh_options: Additional SSH options (e.g., ["-i", "/path/to/key"])
    """
    ssh_options = ssh_options or []
    
    def ssh_exec(command: str) -> str:
        ssh_cmd = ["ssh"] + ssh_options + [host, command]
        result = subprocess.run(
            ssh_cmd,
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
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON"
    ),
    wide: bool = typer.Option(
        False,
        "--wide",
        help="Use wide single-line table layout"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging output"
    ),
):
    """Analyze SMART data from CSV files."""
    # Configure logging
    if not verbose:
        logger.remove()
        logger.add(lambda _: None)  # Suppress all logging
    
    try:
        # Load device mapping if provided
        device_mapping = None
        if device_map and device_map.exists():
            with open(device_map) as f:
                device_mapping = json.load(f)

        # Analyze local drives
        logger.info(f"Analyzing local SMART data in {smart_dir}")
        system_health = analyze_smart_directory(
            smart_dir,
            device_mapping=device_mapping,
            auto_discover_devices=(device_mapping is None)
        )

        if json_output:
            # Convert to JSON-serializable format
            output = system_health.to_dict()
            typer.echo(json.dumps(output, indent=2))
        else:
            # Rich tabular display
            console = Console()
            display_system_health(system_health, console, compact=not wide)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise typer.Exit(1)


@app.command("analyze-remote")
def analyze_remote(
    host: str = typer.Argument(..., help="SSH host to connect to"),
    smart_dir: str = typer.Argument(
        "/var/lib/smartmontools/",
        help="Directory containing SMART CSV files on remote host"
    ),
    device_map: Path | None = typer.Option(
        None,
        "--device-map",
        help="JSON file mapping serial numbers to device paths"
    ),
    ssh_options: str | None = typer.Option(
        None,
        "--ssh-options",
        help="Additional SSH options (e.g., '-i /path/to/key -o StrictHostKeyChecking=no')"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON"
    ),
    wide: bool = typer.Option(
        False,
        "--wide",
        help="Use wide single-line table layout"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging output"
    ),
):
    """Analyze SMART data from a remote TrueNAS host via SSH."""
    # Configure logging
    if not verbose:
        logger.remove()
        logger.add(lambda _: None)  # Suppress all logging
    
    try:
        # Load device mapping if provided
        device_mapping = None
        if device_map and device_map.exists():
            logger.info(f"Loading device mapping from {device_map}")
            with open(device_map) as f:
                device_mapping = json.load(f)

        # Parse SSH options
        parsed_ssh_options = ssh_options.split() if ssh_options else None

        # Use the new analyze_smart_remote function
        logger.info(f"Analyzing remote SMART data on {host}:{smart_dir}")
        system_health = analyze_smart_remote(
            host=host,
            smart_dir=smart_dir,
            device_mapping=device_mapping,
            ssh_options=parsed_ssh_options,
            auto_discover_devices=(device_mapping is None)
        )

        if json_output:
            # Convert to JSON-serializable format
            output = system_health.to_dict()
            typer.echo(json.dumps(output, indent=2))
        else:
            # Rich tabular display
            console = Console()
            display_system_health(system_health, console, compact=not wide)

    except Exception as e:
        logger.error(f"Remote analysis failed: {e}")
        raise typer.Exit(1)



if __name__ == "__main__":
    app()
