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
# truenas-smart-parser/src/truenas_smart_parser/display.py

"""Rich tabular display for SMART health data."""

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .parser import DriveHealth, SystemHealth


def get_temp_color(temp: float | None, warning: float | None,
                   critical: float | None) -> str:
    """Get color for temperature based on thresholds."""
    if temp is None:
        return "dim"
    
    if critical and temp >= critical:
        return "red"
    elif warning and temp >= warning:
        return "orange1"
    elif warning and temp >= (warning * 0.9):  # Within 10% of warning
        return "yellow"
    else:
        return "green"


def get_health_status(drive: DriveHealth) -> tuple[str, str]:
    """Get health status emoji and color for a drive."""
    # Check temperature
    temp_is_critical = False
    temp_is_warning = False
    
    if drive.temperature_current is not None:
        if (drive.temperature_critical and 
            drive.temperature_current >= drive.temperature_critical):
            temp_is_critical = True
        elif (drive.temperature_warning and
              drive.temperature_current >= drive.temperature_warning):
            temp_is_warning = True
        elif (drive.temperature_operational_max and
              drive.temperature_current >= drive.temperature_operational_max):
            temp_is_warning = True
    
    # Check for new errors in 24h
    has_new_errors = (
        drive.reallocated_sectors_24h > 0 or
        drive.pending_sectors_24h > 0 or
        drive.media_errors_24h > 0
    )
    
    # Critical: temp critical or new errors
    if temp_is_critical or has_new_errors:
        return "🔴", "red"
    # Warning: temp warning or existing errors
    elif (temp_is_warning or
          drive.reallocated_sectors_total > 0 or
          drive.pending_sectors_total > 0 or
          drive.media_errors_total > 0 or
          (drive.drive_type == 'nvme' and 
           drive.available_spare_pct and 
           drive.available_spare_pct < 10)):
        return "🟡", "yellow"
    else:
        return "🟢", "green"


def format_temp(temp: float | None, warning: float | None,
                critical: float | None) -> Text:
    """Format temperature with color."""
    if temp is None:
        return Text("N/A", style="dim")
    
    color = get_temp_color(temp, warning, critical)
    return Text(f"{temp:.0f}°C", style=color)


def format_error_count(count: int, count_24h: int) -> Text:
    """Format error count with highlighting."""
    if count == 0:
        return Text("0", style="dim")
    
    text = Text(str(count))
    if count_24h > 0:
        text.stylize("bold red")
        text.append(f" (+{count_24h})", style="red")
    else:
        text.stylize("yellow")
    
    return text


def create_system_summary_table(system: SystemHealth) -> Table:
    """Create system summary table."""
    table = Table(title="System Health Summary", show_header=False)
    
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    # Drive counts with status indicators
    healthy_text = Text(f"{system.healthy_drives} ", style="green")
    healthy_text.append("🟢", style="green")
    
    warning_text = Text(f"{system.warning_drives} ", style="yellow")
    warning_text.append("🟡", style="yellow")
    
    critical_text = Text(f"{system.critical_drives} ", style="red")
    critical_text.append("🔴", style="red")
    
    table.add_row("Total Drives", str(system.total_drives))
    table.add_row("Healthy", healthy_text)
    table.add_row("Warning", warning_text)
    table.add_row("Critical", critical_text)
    table.add_section()
    
    # Temperature
    max_temp_color = "green"
    if system.max_temperature >= 85:  # Typical NVMe warning
        max_temp_color = "red"
    elif system.max_temperature >= 70:  # Typical ATA critical
        max_temp_color = "orange1"
    elif system.max_temperature >= 60:  # Typical ATA operational
        max_temp_color = "yellow"
    
    table.add_row(
        "Max Temperature",
        Text(f"{system.max_temperature:.0f}°C", style=max_temp_color)
    )
    
    # Errors
    error_style = "red bold" if system.total_errors_24h > 0 else "dim"
    table.add_row(
        "Errors (24h)",
        Text(str(system.total_errors_24h), style=error_style)
    )
    
    table.add_section()
    
    # Drive age
    oldest_days = system.oldest_drive_hours // 24
    newest_days = system.newest_drive_hours // 24
    table.add_row(
        "Drive Age Range",
        f"{newest_days:,d} - {oldest_days:,d} days"
    )
    
    # Drive types
    table.add_row(
        "Drive Types",
        f"{system.ata_drives} ATA, {system.nvme_drives} NVMe"
    )
    
    return table


def create_drives_table_compact(system: SystemHealth) -> Table:
    """Create compact multi-line drives table."""
    table = Table(title="Drive Health Details (Compact)", show_edge=True)
    
    # Compact columns
    table.add_column("Device Info", style="cyan")
    table.add_column("Type", width=4)
    table.add_column("Stat", justify="center", width=4)
    table.add_column("Health Details")
    
    for drive in system.drives:
        status_emoji, status_color = get_health_status(drive)
        
        # Device name without /dev/ prefix
        device_name = drive.device_path.replace("/dev/", "")
        
        # Temperature formatting
        temp_current = drive.temperature_current
        temp_max = drive.temperature_max_24h
        
        # Temperature limits
        limits = []
        if drive.temperature_warning:
            limits.append(f"{drive.temperature_warning:.0f}")
        else:
            limits.append("-")
        
        if drive.temperature_critical:
            limits.append(f"{drive.temperature_critical:.0f}")
        else:
            limits.append("-")
        
        limits_text = "/".join(limits)
        
        # Power on time
        if drive.power_on_hours > 0:
            days = drive.power_on_hours // 24
            age_text = f"{days:,d}d"
        else:
            age_text = "N/A"
        
        # Error summary (Real/Pend/Media/Uncorr)
        error_counts = [
            drive.reallocated_sectors_total,
            drive.pending_sectors_total, 
            drive.media_errors_total,
            drive.uncorrectable_sectors_total
        ]
        error_summary = "/".join(str(count) for count in error_counts)
        
        # Check for new errors to color the summary
        has_new_errors = (
            drive.reallocated_sectors_24h > 0 or
            drive.pending_sectors_24h > 0 or
            drive.media_errors_24h > 0 or
            drive.uncorrectable_sectors_24h > 0
        )
        
        if has_new_errors:
            error_text = Text(error_summary, style="red bold")
        elif sum(error_counts) > 0:
            error_text = Text(error_summary, style="yellow")
        else:
            error_text = Text(error_summary, style="dim")
        
        # Build health details line 1
        temp_color = get_temp_color(
            temp_current, drive.temperature_warning, drive.temperature_critical
        )
        
        health_line1 = Text()
        health_line1.append("Temp: ")
        if temp_current is not None:
            health_line1.append(f"{temp_current:.0f}°C", style=temp_color)
        else:
            health_line1.append("N/A", style="dim")
        
        if temp_max is not None:
            max_color = get_temp_color(
                temp_max, drive.temperature_warning, drive.temperature_critical
            )
            health_line1.append(f" (max {temp_max:.0f}°C", style=max_color)
        else:
            health_line1.append(" (max N/A", style="dim")
        
        health_line1.append(f", limits {limits_text}) • Age: {age_text}")
        
        # Build health details line 2
        health_line2 = Text("Errors: ")
        health_line2.append(error_text)
        health_line2.append(" (Real/Pend/Media/Uncorr)")
        
        # Add NVMe specific info
        if drive.drive_type == 'nvme':
            if drive.available_spare_pct is not None:
                spare_pct = drive.available_spare_pct
                if spare_pct < 10:
                    spare_style = "red"
                elif spare_pct < 20:
                    spare_style = "yellow"
                else:
                    spare_style = "green"
                health_line2.append(f" • Spare: ")
                health_line2.append(f"{spare_pct:.0f}%", style=spare_style)
            
            if drive.percentage_used is not None:
                health_line2.append(f" • Used: {drive.percentage_used:.0f}%")
        
        # Add rows with appropriate styling
        row_style = "bold" if status_color == "red" else None
        
        # First row: device info
        table.add_row(
            device_name,
            drive.drive_type.upper(),
            Text(status_emoji, style=status_color),
            health_line1,
            style=row_style
        )
        
        # Second row: serial and health details
        table.add_row(
            f"Serial: {drive.serial}",
            "",  # Empty type column
            "",  # Empty status column
            health_line2,
            style=row_style
        )
        
        # Add separator between drives (except last)
        if drive != system.drives[-1]:
            table.add_section()
    
    return table


def create_drives_table(system: SystemHealth) -> Table:
    """Create detailed drives table."""
    table = Table(title="Drive Health Details", show_edge=True)
    
    # Basic columns
    table.add_column("Device", style="cyan")
    table.add_column("Serial", style="dim")
    table.add_column("Type")
    table.add_column("Status", justify="center")
    
    # Temperature columns
    table.add_column("Temp", justify="right")
    table.add_column("Max 24h", justify="right")
    table.add_column("Limits (W/C)", justify="right", style="dim")
    
    # Usage columns
    table.add_column("Power On", justify="right")
    table.add_column("Cycles", justify="right")
    
    # Error columns
    table.add_column("Realloc", justify="right")
    table.add_column("Pending", justify="right")
    table.add_column("Uncorr", justify="right")
    table.add_column("Media", justify="right")
    
    # NVMe specific
    table.add_column("Spare %", justify="right")
    table.add_column("Used %", justify="right")
    
    for drive in system.drives:
        status_emoji, status_color = get_health_status(drive)
        
        # Temperature formatting
        temp_current = format_temp(
            drive.temperature_current,
            drive.temperature_warning,
            drive.temperature_critical
        )
        temp_max = format_temp(
            drive.temperature_max_24h,
            drive.temperature_warning,
            drive.temperature_critical
        )
        
        # Temperature limits
        limits = []
        if drive.temperature_warning:
            limits.append(f"{drive.temperature_warning:.0f}")
        else:
            limits.append("-")
        
        if drive.temperature_critical:
            limits.append(f"{drive.temperature_critical:.0f}")
        else:
            limits.append("-")
        
        limits_text = "/".join(limits)
        
        # Power on time
        if drive.power_on_hours > 0:
            days = drive.power_on_hours // 24
            power_on = f"{days:,d}d"
        else:
            power_on = "N/A"
        
        # Error counts
        realloc = format_error_count(
            drive.reallocated_sectors_total,
            drive.reallocated_sectors_24h
        )
        pending = format_error_count(
            drive.pending_sectors_total,
            drive.pending_sectors_24h
        )
        uncorr = format_error_count(
            drive.uncorrectable_sectors_total,
            drive.uncorrectable_sectors_24h
        )
        media = format_error_count(
            drive.media_errors_total,
            drive.media_errors_24h
        )
        
        # NVMe specific
        if drive.drive_type == 'nvme':
            spare = f"{drive.available_spare_pct:.0f}%" if drive.available_spare_pct is not None else "-"
            used = f"{drive.percentage_used:.0f}%" if drive.percentage_used is not None else "-"
            
            # Color code spare percentage
            if drive.available_spare_pct is not None:
                if drive.available_spare_pct < 10:
                    spare = Text(spare, style="red")
                elif drive.available_spare_pct < 20:
                    spare = Text(spare, style="yellow")
                else:
                    spare = Text(spare, style="green")
        else:
            spare = "-"
            used = "-"
        
        # Add row with appropriate styling
        row_style = "bold" if status_color == "red" else None
        
        table.add_row(
            drive.device_path,
            drive.serial,
            drive.drive_type.upper(),
            Text(status_emoji, style=status_color),
            temp_current,
            temp_max,
            limits_text,
            power_on,
            str(drive.power_cycles),
            realloc,
            pending,
            uncorr,
            media,
            spare,
            used,
            style=row_style
        )
    
    return table


def display_system_health(system: SystemHealth, console: Console | None = None, compact: bool = True):
    """Display system health using rich tables."""
    if console is None:
        console = Console()
    
    # System summary
    summary_table = create_system_summary_table(system)
    console.print(summary_table)
    console.print()
    
    # Detailed drives table
    if compact:
        drives_table = create_drives_table_compact(system)
    else:
        drives_table = create_drives_table(system)
    console.print(drives_table)
    
    # Legend
    console.print("\n[dim]Legend:[/dim]")
    console.print("[dim]  Temp Limits: W=Warning, C=Critical[/dim]")
    console.print("[dim]  Error counts: Total (24h changes in red)[/dim]")
    console.print("[dim]  Status: 🟢 Healthy, 🟡 Warning, 🔴 Critical[/dim]")