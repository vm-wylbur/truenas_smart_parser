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
# truenas-smart-parser/src/truenas_smart_parser/parser.py

import json
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import polars as pl
from loguru import logger

# SMART attribute IDs we care about for ATA drives
ATTR_RAW_READ_ERROR_RATE: Final[int] = 1
ATTR_REALLOCATED_SECTOR_CT: Final[int] = 5
ATTR_POWER_ON_HOURS: Final[int] = 9
ATTR_POWER_CYCLE_COUNT: Final[int] = 12
ATTR_TEMPERATURE_CELSIUS: Final[int] = 194
ATTR_CURRENT_PENDING_SECTOR: Final[int] = 197
ATTR_OFFLINE_UNCORRECTABLE: Final[int] = 198


@dataclass(frozen=True)
class DriveHealth:
    """Health metrics for a single drive."""
    device_path: str
    drive_type: str  # 'ata' or 'nvme'
    serial: str

    # Temperature metrics
    temperature_current: float | None
    temperature_max_24h: float | None
    temperature_mean_24h: float | None
    temperature_warning: float | None = None  # Warning threshold
    temperature_critical: float | None = None  # Critical threshold
    temperature_operational_max: float | None = None  # ATA operational limit

    # Error metrics (all-time)
    reallocated_sectors_total: int = 0
    pending_sectors_total: int = 0
    uncorrectable_sectors_total: int = 0
    read_errors_total: int = 0
    media_errors_total: int = 0

    # Error metrics (24h)
    reallocated_sectors_24h: int = 0
    pending_sectors_24h: int = 0
    uncorrectable_sectors_24h: int = 0
    read_errors_24h: int = 0
    media_errors_24h: int = 0

    # NVMe specific
    available_spare_pct: float | None = None
    percentage_used: float | None = None
    unsafe_shutdowns: int = 0

    # General info
    power_on_hours: int = 0
    power_cycles: int = 0
    last_updated: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'device_path': self.device_path,
            'drive_type': self.drive_type,
            'serial': self.serial,
            'temperature': {
                'current': self.temperature_current,
                'max_24h': self.temperature_max_24h,
                'mean_24h': self.temperature_mean_24h,
                'warning': self.temperature_warning,
                'critical': self.temperature_critical,
                'operational_max': self.temperature_operational_max,
            },
            'errors': {
                'total': {
                    'reallocated_sectors': self.reallocated_sectors_total,
                    'pending_sectors': self.pending_sectors_total,
                    'uncorrectable_sectors': self.uncorrectable_sectors_total,
                    'read_errors': self.read_errors_total,
                    'media_errors': self.media_errors_total,
                },
                '24h': {
                    'reallocated_sectors': self.reallocated_sectors_24h,
                    'pending_sectors': self.pending_sectors_24h,
                    'uncorrectable_sectors': self.uncorrectable_sectors_24h,
                    'read_errors': self.read_errors_24h,
                    'media_errors': self.media_errors_24h,
                },
            },
            'nvme_specific': {
                'available_spare_pct': self.available_spare_pct,
                'percentage_used': self.percentage_used,
                'unsafe_shutdowns': self.unsafe_shutdowns,
            },
            'info': {
                'power_on_hours': self.power_on_hours,
                'power_cycles': self.power_cycles,
                'last_updated': (
                    self.last_updated.isoformat() if self.last_updated else None
                ),
            },
        }


def parse_ata_csv(csv_content: str) -> pl.DataFrame:
    """Parse ATA SMART CSV format into a polars DataFrame.
    
    Format: timestamp; attr_id;norm_val;raw_val; attr_id;norm_val;raw_val; ...
    """
    lines = csv_content.strip().split('\n')
    if not lines:
        return pl.DataFrame()

    records = []
    for line in lines:
        parts = line.split(';')
        if len(parts) < 2:
            continue

        timestamp_str = parts[0].strip()
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        # Parse attribute triplets
        attrs = {}
        i = 1
        while i + 2 < len(parts):
            try:
                attr_id = int(parts[i].strip())
                norm_val = int(parts[i+1].strip())
                raw_val = int(parts[i+2].strip())

                attrs[f"attr_{attr_id}_norm"] = norm_val
                attrs[f"attr_{attr_id}_raw"] = raw_val
            except (ValueError, IndexError):
                pass
            i += 3

        if attrs:
            attrs['timestamp'] = timestamp
            records.append(attrs)

    if not records:
        return pl.DataFrame()

    return pl.DataFrame(records).sort('timestamp')


def parse_nvme_csv(csv_content: str) -> pl.DataFrame:
    """Parse NVMe SMART CSV format into a polars DataFrame.
    
    Format: timestamp; attr_name;value; attr_name;value; ...
    """
    lines = csv_content.strip().split('\n')
    if not lines:
        return pl.DataFrame()

    records = []
    for line in lines:
        parts = line.split(';')
        if len(parts) < 2:
            continue

        timestamp_str = parts[0].strip()
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        # Parse attribute pairs
        attrs = {}
        i = 1
        while i + 1 < len(parts):
            attr_name = parts[i].strip()
            value = parts[i+1].strip()

            # Convert numeric values where appropriate
            if attr_name in [
                'temperature', 'power_cycles', 'power_on_hours',
                'unsafe_shutdowns', 'controller_busy_time',
                'media_and_data_integrity_errors',
                'error_information_log_entries'
            ]:
                try:
                    attrs[attr_name] = int(value)
                except ValueError:
                    attrs[attr_name] = value
            elif (attr_name in ['available_spare', 'percentage_used'] and
                  value.endswith('%')):
                try:
                    attrs[attr_name] = float(value.rstrip('%'))
                except ValueError:
                    attrs[attr_name] = value
            else:
                attrs[attr_name] = value

            i += 2

        if attrs:
            attrs['timestamp'] = timestamp
            records.append(attrs)

    if not records:
        return pl.DataFrame()

    return pl.DataFrame(records).sort('timestamp')


def analyze_ata_health(df: pl.DataFrame, serial: str,
                      device_path: str = "",
                      thresholds: dict[str, float | None] | None = None
                      ) -> DriveHealth:
    """Analyze ATA drive health from parsed DataFrame."""
    if df.is_empty():
        return DriveHealth(
            device_path=device_path,
            drive_type='ata',
            serial=serial,
            temperature_current=None,
            temperature_max_24h=None,
            temperature_mean_24h=None
        )

    # Get latest values
    latest = df.row(-1, named=True)

    # Calculate 24h window
    now = df['timestamp'].max()
    cutoff_24h = now - timedelta(hours=24)
    df_24h = df.filter(pl.col('timestamp') >= cutoff_24h)

    # Temperature analysis
    # ATA drives encode temperature in the lower 8 bits of the raw value
    temp_current_raw = latest.get(f'attr_{ATTR_TEMPERATURE_CELSIUS}_raw')
    if temp_current_raw is not None:
        # Extract temperature from lower 8 bits
        temp_current = temp_current_raw & 0xFF
    else:
        temp_current = None
    
    temp_max_24h = None
    temp_mean_24h = None
    if (not df_24h.is_empty() and
        f'attr_{ATTR_TEMPERATURE_CELSIUS}_raw' in df_24h.columns):
        # Get all temperature values and decode them
        temp_values = df_24h[f'attr_{ATTR_TEMPERATURE_CELSIUS}_raw'].to_list()
        decoded_temps = [t & 0xFF for t in temp_values if t is not None]
        if decoded_temps:
            temp_max_24h = max(decoded_temps)
            temp_mean_24h = sum(decoded_temps) / len(decoded_temps)

    # Error analysis - get latest values
    reallocated_total = latest.get(f'attr_{ATTR_REALLOCATED_SECTOR_CT}_raw', 0)
    pending_total = latest.get(f'attr_{ATTR_CURRENT_PENDING_SECTOR}_raw', 0)
    uncorrectable_total = latest.get(
        f'attr_{ATTR_OFFLINE_UNCORRECTABLE}_raw', 0
    )
    read_errors_total = latest.get(f'attr_{ATTR_RAW_READ_ERROR_RATE}_raw', 0)

    # Calculate 24h changes
    reallocated_24h = 0
    pending_24h = 0
    uncorrectable_24h = 0
    read_errors_24h = 0

    if not df_24h.is_empty() and len(df_24h) > 1:
        first_24h = df_24h.row(0, named=True)

        if f'attr_{ATTR_REALLOCATED_SECTOR_CT}_raw' in first_24h:
            reallocated_24h = max(
                0,
                reallocated_total - first_24h.get(
                    f'attr_{ATTR_REALLOCATED_SECTOR_CT}_raw', 0
                )
            )
        if f'attr_{ATTR_CURRENT_PENDING_SECTOR}_raw' in first_24h:
            pending_24h = max(
                0,
                pending_total - first_24h.get(
                    f'attr_{ATTR_CURRENT_PENDING_SECTOR}_raw', 0
                )
            )
        if f'attr_{ATTR_OFFLINE_UNCORRECTABLE}_raw' in first_24h:
            uncorrectable_24h = max(
                0,
                uncorrectable_total - first_24h.get(
                    f'attr_{ATTR_OFFLINE_UNCORRECTABLE}_raw', 0
                )
            )
        if f'attr_{ATTR_RAW_READ_ERROR_RATE}_raw' in first_24h:
            read_errors_24h = max(
                0,
                read_errors_total - first_24h.get(
                    f'attr_{ATTR_RAW_READ_ERROR_RATE}_raw', 0
                )
            )

    # Get thresholds
    thresholds = thresholds or {}
    temp_warning = thresholds.get("warning")
    temp_critical = thresholds.get("critical", 70.0)
    temp_operational = thresholds.get("operational_max", 60.0)

    return DriveHealth(
        device_path=device_path,
        drive_type='ata',
        serial=serial,
        temperature_current=(
            float(temp_current) if temp_current is not None else None
        ),
        temperature_max_24h=(
            float(temp_max_24h) if temp_max_24h is not None else None
        ),
        temperature_mean_24h=(
            float(temp_mean_24h) if temp_mean_24h is not None else None
        ),
        temperature_warning=temp_warning,
        temperature_critical=temp_critical,
        temperature_operational_max=temp_operational,
        reallocated_sectors_total=reallocated_total,
        pending_sectors_total=pending_total,
        uncorrectable_sectors_total=uncorrectable_total,
        read_errors_total=read_errors_total,
        reallocated_sectors_24h=reallocated_24h,
        pending_sectors_24h=pending_24h,
        uncorrectable_sectors_24h=uncorrectable_24h,
        read_errors_24h=read_errors_24h,
        power_on_hours=latest.get(f'attr_{ATTR_POWER_ON_HOURS}_raw', 0),
        power_cycles=latest.get(f'attr_{ATTR_POWER_CYCLE_COUNT}_raw', 0),
        last_updated=now
    )


def analyze_nvme_health(df: pl.DataFrame, serial: str,
                       device_path: str = "",
                       thresholds: dict[str, float | None] | None = None
                       ) -> DriveHealth:
    """Analyze NVMe drive health from parsed DataFrame."""
    if df.is_empty():
        return DriveHealth(
            device_path=device_path,
            drive_type='nvme',
            serial=serial,
            temperature_current=None,
            temperature_max_24h=None,
            temperature_mean_24h=None
        )

    # Get latest values
    latest = df.row(-1, named=True)

    # Calculate 24h window
    now = df['timestamp'].max()
    cutoff_24h = now - timedelta(hours=24)
    df_24h = df.filter(pl.col('timestamp') >= cutoff_24h)

    # Temperature analysis
    temp_current = latest.get('temperature')
    temp_max_24h = None
    temp_mean_24h = None
    if not df_24h.is_empty() and 'temperature' in df_24h.columns:
        temp_max_24h = df_24h['temperature'].max()
        temp_mean_24h = df_24h['temperature'].mean()

    # Error analysis
    media_errors_total = latest.get('media_and_data_integrity_errors', 0)

    # Calculate 24h changes
    media_errors_24h = 0
    if not df_24h.is_empty() and len(df_24h) > 1:
        first_24h = df_24h.row(0, named=True)
        if 'media_and_data_integrity_errors' in first_24h:
            media_errors_24h = max(
                0,
                media_errors_total - first_24h.get(
                    'media_and_data_integrity_errors', 0
                )
            )

    # Get thresholds
    thresholds = thresholds or {}
    temp_warning = thresholds.get("warning", 85.0)
    temp_critical = thresholds.get("critical", 95.0)
    temp_operational = thresholds.get("operational_max", 85.0)

    return DriveHealth(
        device_path=device_path,
        drive_type='nvme',
        serial=serial,
        temperature_current=(
            float(temp_current) if temp_current is not None else None
        ),
        temperature_max_24h=(
            float(temp_max_24h) if temp_max_24h is not None else None
        ),
        temperature_mean_24h=(
            float(temp_mean_24h) if temp_mean_24h is not None else None
        ),
        temperature_warning=temp_warning,
        temperature_critical=temp_critical,
        temperature_operational_max=temp_operational,
        media_errors_total=media_errors_total,
        media_errors_24h=media_errors_24h,
        available_spare_pct=latest.get('available_spare'),
        percentage_used=latest.get('percentage_used'),
        unsafe_shutdowns=latest.get('unsafe_shutdowns', 0),
        power_on_hours=latest.get('power_on_hours', 0),
        power_cycles=latest.get('power_cycles', 0),
        last_updated=now
    )


def parse_smart_csv(csv_path: str | Path,
                   drive_type: str) -> pl.DataFrame:
    """Parse a SMART CSV file based on drive type."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    content = csv_path.read_text()

    if drive_type.lower() == 'ata':
        return parse_ata_csv(content)
    elif drive_type.lower() == 'nvme':
        return parse_nvme_csv(content)
    else:
        raise ValueError(f"Unknown drive type: {drive_type}")


@dataclass(frozen=True)
class SystemHealth:
    """System-wide health metrics aggregated from all drives."""
    drives: list[DriveHealth]
    total_drives: int
    healthy_drives: int
    warning_drives: int
    critical_drives: int

    # Aggregate metrics
    total_errors_24h: int
    max_temperature: float
    total_reallocated_sectors: int
    total_pending_sectors: int
    total_media_errors: int

    # System summary
    oldest_drive_hours: int
    newest_drive_hours: int
    nvme_drives: int
    ata_drives: int
    last_updated: datetime

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'summary': {
                'total_drives': self.total_drives,
                'healthy_drives': self.healthy_drives,
                'warning_drives': self.warning_drives,
                'critical_drives': self.critical_drives,
                'total_errors_24h': self.total_errors_24h,
                'max_temperature': self.max_temperature,
                'total_reallocated_sectors': self.total_reallocated_sectors,
                'total_pending_sectors': self.total_pending_sectors,
                'total_media_errors': self.total_media_errors,
            },
            'system': {
                'oldest_drive_hours': self.oldest_drive_hours,
                'newest_drive_hours': self.newest_drive_hours,
                'nvme_drives': self.nvme_drives,
                'ata_drives': self.ata_drives,
                'last_updated': (
                    self.last_updated.isoformat() if self.last_updated else None
                ),
            },
            'drives': [drive.to_dict() for drive in self.drives],
        }


def query_ata_thresholds(
    device_path: str, ssh_command: Callable | None = None
) -> dict[str, float | None]:
    """Query ATA drive temperature thresholds.
    
    Args:
        device_path: Device path (e.g., /dev/sda)
        ssh_command: Optional function to execute commands via SSH
                    Should accept command string and return output string
    
    Returns:
        Dict with temperature thresholds in Celsius
    """
    try:
        if ssh_command:
            output = ssh_command(f"smartctl -x --json {device_path}")
        else:
            result = subprocess.run(
                ["smartctl", "-x", "--json", device_path],
                capture_output=True,
                text=True,
                check=False
            )
            output = result.stdout

        data = json.loads(output)
        temp_info = data.get("temperature", {})

        return {
            "warning": None,  # ATA doesn't have warning threshold
            "critical": float(temp_info.get("limit_max", 70)),  # Damage threshold
            "operational_max": float(temp_info.get("op_limit_max", 60))
        }
    except Exception:
        # Return sensible defaults if query fails
        return {"warning": None, "critical": 70.0, "operational_max": 60.0}


def query_nvme_thresholds(
    device_path: str, ssh_command: Callable | None = None
) -> dict[str, float | None]:
    """Query NVMe drive temperature thresholds.
    
    Args:
        device_path: Device path (e.g., /dev/nvme0)
        ssh_command: Optional function to execute commands via SSH
    
    Returns:
        Dict with temperature thresholds in Celsius
    """
    try:
        if ssh_command:
            output = ssh_command(f"nvme id-ctrl {device_path} -o json")
        else:
            result = subprocess.run(
                ["nvme", "id-ctrl", device_path, "-o", "json"],
                capture_output=True,
                text=True,
                check=False
            )
            output = result.stdout

        data = json.loads(output)

        # Convert from Kelvin to Celsius
        wctemp_k = data.get("wctemp", 358)  # Default 85°C
        cctemp_k = data.get("cctemp", 368)  # Default 95°C

        return {
            "warning": float(wctemp_k - 273),
            "critical": float(cctemp_k - 273),
            "operational_max": float(wctemp_k - 273)  # Use warning as operational
        }
    except Exception:
        # Return sensible defaults if query fails
        return {"warning": 85.0, "critical": 95.0, "operational_max": 85.0}


def auto_discover_device_mapping(ssh_command: Callable) -> dict[str, str]:
    """Auto-discover device mapping by scanning remote host.
    
    Args:
        ssh_command: Function to execute commands via SSH
                    Should accept command string and return output string
    
    Returns:
        Dict mapping serial numbers to device paths
        e.g., {"1RJE48WM": "/dev/sda", ...}
    
    Note:
        This function can fail silently if SSH authentication fails in
        subprocess context (e.g., missing SSH agent, different user context).
        SSH commands that work interactively may fail when called from
        Python subprocess due to publickey authentication issues.
        When SSH fails, returns empty dict and caller falls back to
        unknown_ device paths, which is expected behavior.
    """
    device_mapping = {}
    
    logger.info("Starting auto-discovery of device mappings...")
    
    try:
        logger.debug("Running: smartctl --scan")
        scan_output = ssh_command("smartctl --scan")
        logger.debug(f"Scan output: {repr(scan_output)}")
        
        if not scan_output.strip():
            logger.warning("No output from smartctl --scan")
            return device_mapping
        
        lines = scan_output.strip().split('\n')
        logger.info(f"Found {len(lines)} lines from smartctl --scan")
        
        for i, line in enumerate(lines):
            if not line:
                logger.debug(f"Line {i}: empty, skipping")
                continue
            
            logger.debug(f"Line {i}: {repr(line)}")
            parts = line.split()
            if len(parts) < 1:
                logger.warning(f"Line {i}: invalid format, skipping")
                continue
                
            device = parts[0]
            logger.debug(f"Processing device: {device}")
            
            # Get serial number
            serial_cmd = (f"smartctl -i {device} | grep 'Serial Number' | "
                         f"awk '{{print $3}}'")
            logger.debug(f"Running: {serial_cmd}")
            
            info = ssh_command(serial_cmd)
            serial = info.strip()
            
            logger.debug(f"Device {device} serial output: {repr(info)}")
            logger.debug(f"Device {device} parsed serial: {repr(serial)}")
            
            if serial:
                device_mapping[serial] = device
                logger.info(f"Mapped {serial} -> {device}")
            else:
                logger.warning(f"No serial found for device {device}")
        
        logger.info(f"Auto-discovery completed: {len(device_mapping)} devices mapped")
        logger.debug(f"Final mapping: {device_mapping}")
        
    except Exception as e:
        logger.error(f"Auto-discovery failed with exception: {e}")
        logger.debug("Exception details:", exc_info=True)
    
    return device_mapping


def _extract_drive_info(
    filename: str
) -> tuple[str, str, str]:
    """Extract serial, model, and drive type from filename.
    
    Filename format:
    - ATA: attrlog.MODEL-SERIAL.ata.csv
    - NVMe: attrlog.MODEL-SERIAL.nvme.csv or attrlog.MODEL-SERIAL-nX.nvme.csv
    
    Returns: (serial, model, drive_type)
    """
    if not filename.startswith('attrlog.'):
        raise ValueError(f"Invalid filename format: {filename}")

    # Remove prefix and suffix
    name = filename.replace('attrlog.', '')

    if name.endswith('.ata.csv'):
        drive_type = 'ata'
        name = name.replace('.ata.csv', '')
    elif name.endswith('.nvme.csv'):
        drive_type = 'nvme'
        name = name.replace('.nvme.csv', '')
    else:
        raise ValueError(f"Unknown drive type in filename: {filename}")

    # Split model and serial
    # Handle NVMe format with -n1 suffix
    if drive_type == 'nvme' and '-n' in name:
        # Remove -nX suffix
        name = name.rsplit('-n', 1)[0]

    # Find last hyphen that separates model from serial
    parts = name.rsplit('-', 1)
    if len(parts) == 2:
        model, serial = parts
    else:
        # Fallback if format is unexpected
        model = name
        serial = name

    return serial, model, drive_type


def analyze_smart_directory(smart_dir: str | Path,
                          device_mapping: dict[str, str] | None = None,
                          auto_discover_devices: bool = False,
                          verbose: bool = False) -> SystemHealth:
    """Analyze all SMART CSV files in a local directory.
    
    Args:
        smart_dir: Directory containing SMART CSV files (e.g., /var/lib/smartmontools/)
        device_mapping: Optional mapping of serial numbers to device paths
                       e.g., {"1RJE48WM": "/dev/sda", ...}
        auto_discover_devices: If True, automatically discover device mapping
                              using local smartctl --scan commands
        verbose: If True, enable detailed logging output
    
    Returns:
        SystemHealth object with all drives and aggregate metrics
        
    Note:
        This function is for local analysis only. For remote analysis,
        use analyze_smart_remote() instead.
    """
    smart_dir = Path(smart_dir)
    if not smart_dir.is_dir():
        raise ValueError(f"Not a directory: {smart_dir}")

    # Configure logging based on verbose flag
    if not verbose:
        logger.disable("truenas_smart_parser")

    # Auto-discover device mapping if requested
    logger.debug(f"auto_discover_devices={auto_discover_devices}, device_mapping={device_mapping}")
    if auto_discover_devices and not device_mapping:
        logger.info("Auto-discovery conditions met, discovering local devices")
        
        def local_exec(command: str) -> str:
            """Execute command locally"""
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout
        
        device_mapping = auto_discover_device_mapping(local_exec)
        logger.info(f"Local auto-discovery returned {len(device_mapping or {})} mappings")
    elif not auto_discover_devices:
        logger.debug("Auto-discovery disabled")
    elif device_mapping:
        logger.debug(f"Device mapping already provided with {len(device_mapping)} entries")

    # Find all CSV files
    csv_files = list(smart_dir.glob("attrlog.*.csv"))
    if not csv_files:
        if not verbose:
            logger.enable("truenas_smart_parser")
        return SystemHealth(
            drives=[],
            total_drives=0,
            healthy_drives=0,
            warning_drives=0,
            critical_drives=0,
            total_errors_24h=0,
            max_temperature=0.0,
            total_reallocated_sectors=0,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=0,
            newest_drive_hours=0,
            nvme_drives=0,
            ata_drives=0,
            last_updated=datetime.now()
        )

    drives = []
    device_mapping = device_mapping or {}
    logger.info(f"Processing {len(csv_files)} CSV files with device mapping: {device_mapping}")

    for csv_file in csv_files:
        try:
            # Extract info from filename
            serial, model, drive_type = _extract_drive_info(csv_file.name)
            logger.debug(f"CSV file {csv_file.name}: serial={serial}, model={model}, type={drive_type}")

            # Get device path from mapping or generate one
            device_path = device_mapping.get(serial, f"/dev/unknown_{serial[:8]}")
            if serial in device_mapping:
                logger.info(f"Mapped {serial} -> {device_path} (from device mapping)")
            else:
                logger.warning(f"No mapping for {serial}, using fallback: {device_path}")
                logger.debug(f"Available mappings: {list(device_mapping.keys())}")

            # Parse CSV and analyze
            df = parse_smart_csv(csv_file, drive_type)

            # Query temperature thresholds if we have valid device path (local commands)
            thresholds = None
            if device_path != f"/dev/unknown_{serial[:8]}":
                try:
                    if drive_type == 'ata':
                        thresholds = query_ata_thresholds(device_path)
                    else:
                        thresholds = query_nvme_thresholds(device_path)
                except Exception:
                    pass  # Use defaults if query fails

            if drive_type == 'ata':
                health = analyze_ata_health(df, serial, device_path, thresholds)
            else:
                health = analyze_nvme_health(df, serial, device_path, thresholds)

            drives.append(health)

        except Exception as e:
            # Log error but continue with other drives
            print(f"Error analyzing {csv_file.name}: {e}")
            continue

    if not drives:
        if not verbose:
            logger.enable("truenas_smart_parser")
        return SystemHealth(
            drives=[],
            total_drives=0,
            healthy_drives=0,
            warning_drives=0,
            critical_drives=0,
            total_errors_24h=0,
            max_temperature=0.0,
            total_reallocated_sectors=0,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=0,
            newest_drive_hours=0,
            nvme_drives=0,
            ata_drives=0,
            last_updated=datetime.now()
        )

    # Calculate aggregate metrics
    total_errors_24h = sum(
        d.reallocated_sectors_24h + d.pending_sectors_24h +
        d.uncorrectable_sectors_24h + d.media_errors_24h
        for d in drives
    )

    temps = [d.temperature_current for d in drives if d.temperature_current is not None]
    max_temperature = max(temps) if temps else 0.0

    total_reallocated = sum(d.reallocated_sectors_total for d in drives)
    total_pending = sum(d.pending_sectors_total for d in drives)
    total_media_errors = sum(d.media_errors_total for d in drives)

    power_hours = [d.power_on_hours for d in drives if d.power_on_hours > 0]
    oldest_hours = max(power_hours) if power_hours else 0
    newest_hours = min(power_hours) if power_hours else 0

    nvme_count = sum(1 for d in drives if d.drive_type == 'nvme')
    ata_count = sum(1 for d in drives if d.drive_type == 'ata')

    # Classify drive health
    healthy = 0
    warning = 0
    critical = 0

    for drive in drives:
        # Check temperature against drive-specific thresholds
        temp_is_critical = False
        temp_is_warning = False

        if drive.temperature_current is not None:
            # Use drive-specific thresholds if available
            if (drive.temperature_critical and
                drive.temperature_current >= drive.temperature_critical):
                temp_is_critical = True
            elif (drive.temperature_warning and
                  drive.temperature_current >= drive.temperature_warning):
                temp_is_warning = True
            elif (drive.temperature_operational_max and
                  drive.temperature_current >= drive.temperature_operational_max):
                temp_is_warning = True

        # Critical: any new errors in 24h or critical temp
        if (drive.reallocated_sectors_24h > 0 or
            drive.pending_sectors_24h > 0 or
            drive.media_errors_24h > 0 or
            temp_is_critical):
            critical += 1
        # Warning: existing errors or warning temp
        elif (drive.reallocated_sectors_total > 0 or
              drive.pending_sectors_total > 0 or
              drive.media_errors_total > 0 or
              temp_is_warning or
              (drive.drive_type == 'nvme' and drive.available_spare_pct and drive.available_spare_pct < 10)):
            warning += 1
        else:
            healthy += 1

    return SystemHealth(
        drives=drives,
        total_drives=len(drives),
        healthy_drives=healthy,
        warning_drives=warning,
        critical_drives=critical,
        total_errors_24h=total_errors_24h,
        max_temperature=max_temperature,
        total_reallocated_sectors=total_reallocated,
        total_pending_sectors=total_pending,
        total_media_errors=total_media_errors,
        oldest_drive_hours=oldest_hours,
        newest_drive_hours=newest_hours,
        nvme_drives=nvme_count,
        ata_drives=ata_count,
        last_updated=datetime.now()
    )
    
    # Re-enable logging
    if not verbose:
        logger.enable("truenas_smart_parser")


def _ssh_exec_factory(host: str, ssh_options: list[str] | None = None):
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


def analyze_smart_remote(
    host: str,
    smart_dir: str = "/var/lib/smartmontools/",
    device_mapping: dict[str, str] | None = None,
    ssh_options: list[str] | None = None,
    auto_discover_devices: bool = True,
    verbose: bool = False
) -> SystemHealth:
    """Analyze SMART data from a remote host via SSH.
    
    Args:
        host: SSH hostname to connect to
        smart_dir: Directory containing SMART CSV files on remote host
        device_mapping: Optional mapping of serial numbers to device paths
                       e.g., {"1RJE48WM": "/dev/sda", ...}
        ssh_options: Additional SSH options (e.g., ["-i", "/path/to/key"])
        auto_discover_devices: If True, automatically discover device mapping
                              using smartctl --scan on the remote host
        verbose: If True, enable detailed logging output
    
    Returns:
        SystemHealth object with all drives and aggregate metrics
        
    Note:
        This function copies CSV files from the remote host to a temporary
        directory and performs all analysis locally. Device auto-discovery
        runs on the remote host to ensure CSV files and device mappings
        come from the same system.
    """
    # Configure logging based on verbose flag
    if not verbose:
        logger.disable("truenas_smart_parser")
    
    logger.info(f"Starting remote analysis of {host}:{smart_dir}")
    
    # Create SSH executor
    ssh_exec = _ssh_exec_factory(host, ssh_options)
    
    # Auto-discover device mapping if requested and not provided
    if auto_discover_devices and not device_mapping:
        logger.info("Auto-discovering device mappings on remote host...")
        device_mapping = auto_discover_device_mapping(ssh_exec)
    
    # Create temporary directory for CSV files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        logger.debug(f"Using temporary directory: {tmppath}")
        
        # List CSV files on remote host
        logger.info("Listing remote CSV files...")
        ls_cmd = ["ssh"] + (ssh_options or []) + [host, f"ls -1 {smart_dir}/attrlog.*.csv 2>/dev/null"]
        ls_result = subprocess.run(
            ls_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if ls_result.returncode != 0:
            logger.error(f"Failed to list files in {smart_dir} on {host}")
            logger.error(f"Command: {' '.join(ls_cmd)}")
            logger.error(f"Error: {ls_result.stderr}")
            raise RuntimeError(f"Failed to list CSV files on {host}")
        
        csv_files = ls_result.stdout.strip().split('\n')
        csv_files = [f for f in csv_files if f]  # Remove empty strings
        
        if not csv_files:
            logger.warning(f"No SMART CSV files found in {smart_dir} on {host}")
            return SystemHealth(
                drives=[],
                total_drives=0,
                healthy_drives=0,
                warning_drives=0,
                critical_drives=0,
                total_errors_24h=0,
                max_temperature=0.0,
                total_reallocated_sectors=0,
                total_pending_sectors=0,
                total_media_errors=0,
                oldest_drive_hours=0,
                newest_drive_hours=0,
                nvme_drives=0,
                ata_drives=0,
                last_updated=datetime.now()
            )
        
        logger.info(f"Found {len(csv_files)} CSV files, copying to local temp...")
        
        # Copy each CSV file
        copied_files = 0
        for csv_file in csv_files:
            filename = Path(csv_file).name
            local_file = tmppath / filename
            
            # Use scp to copy file
            scp_cmd = ["scp"] + (ssh_options or []) + [f"{host}:{csv_file}", str(local_file)]
            scp_result = subprocess.run(
                scp_cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if scp_result.returncode != 0:
                logger.warning(f"Failed to copy {filename}: {scp_result.stderr}")
                continue
            
            logger.debug(f"Copied {filename}")
            copied_files += 1
        
        if copied_files == 0:
            logger.error("Failed to copy any CSV files")
            raise RuntimeError("No CSV files could be copied from remote host")
        
        logger.info(f"Successfully copied {copied_files} CSV files")
        
        # Now analyze the local copies (CSV files and device mapping from same host)
        logger.info("Analyzing copied CSV files...")
        result = analyze_smart_directory(
            tmppath,
            device_mapping=device_mapping,
            auto_discover_devices=False,  # Already discovered above
            verbose=verbose  # Pass through verbose flag
        )
        
    # Re-enable logging
    if not verbose:
        logger.enable("truenas_smart_parser")
        
    return result
