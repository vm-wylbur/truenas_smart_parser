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
    compact: bool = typer.Option(
        False,
        "--compact",
        help="Use compact multi-line table layout"
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
            output = system_health.to_dict()
            typer.echo(json.dumps(output, indent=2))
        else:
            # Rich tabular display
            console = Console()
            display_system_health(system_health, console, compact=compact)

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
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON"
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="Use compact multi-line table layout"
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
        import tempfile

        # Create SSH executor
        ssh_exec = ssh_exec_factory(host)
        logger.info(f"Connecting to {host} to analyze {smart_dir}")

        # Load or create device mapping
        device_mapping = {}
        if device_map and device_map.exists():
            logger.info(f"Loading device mapping from {device_map}")
            with open(device_map) as f:
                device_mapping = json.load(f)
        else:
            # Automatically scan for device mapping
            logger.info("No device mapping provided, scanning remote host...")
            scan_output = ssh_exec("smartctl --scan")
            
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
                    logger.debug(f"  Found {device}: {serial}")
            
            logger.info(f"Auto-discovered {len(device_mapping)} drives")

        # Create temporary directory for CSV files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # List CSV files on remote host
            logger.info("Listing remote CSV files...")
            ls_result = subprocess.run(
                ["ssh", host, f"ls -1 {smart_dir}/attrlog.*.csv 2>/dev/null"],
                capture_output=True,
                text=True,
                check=False
            )

            if ls_result.returncode != 0:
                logger.error(f"Failed to list files in {smart_dir} on {host}")
                raise typer.Exit(1)

            csv_files = ls_result.stdout.strip().split('\n')
            csv_files = [f for f in csv_files if f]  # Remove empty strings

            if not csv_files:
                logger.error(
                    f"No SMART CSV files found in {smart_dir} on {host}"
                )
                raise typer.Exit(1)

            logger.info(f"Found {len(csv_files)} CSV files, copying...")

            # Copy each CSV file
            for csv_file in csv_files:
                filename = Path(csv_file).name
                local_file = tmppath / filename

                # Use scp to copy file
                scp_result = subprocess.run(
                    ["scp", f"{host}:{csv_file}", str(local_file)],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if scp_result.returncode != 0:
                    logger.warning(
                        f"Failed to copy {filename}: {scp_result.stderr}"
                    )
                    continue

                logger.debug(f"Copied {filename}")

            # Now analyze the local copies with SSH threshold queries
            logger.info(f"Analyzing SMART data with {len(device_mapping)} mapped drives...")
            system_health = analyze_smart_directory(
                tmppath,
                device_mapping=device_mapping,
                ssh_command=ssh_exec  # Still use SSH for threshold queries
            )

            if json_output:
                # Convert to JSON-serializable format
                output = system_health.to_dict()
                typer.echo(json.dumps(output, indent=2))
            else:
                # Rich tabular display
                console = Console()
                display_system_health(system_health, console, compact=compact)

    except Exception as e:
        logger.error(f"Remote analysis failed: {e}")
        raise typer.Exit(1)



if __name__ == "__main__":
    app()
