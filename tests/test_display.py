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
# truenas-smart-parser/tests/test_display.py

"""Tests for rich display functionality."""

from datetime import datetime
from io import StringIO

from rich.console import Console

from truenas_smart_parser import DriveHealth, SystemHealth
from truenas_smart_parser.display import (
    create_drives_table,
    create_drives_table_compact,
    create_system_summary_table,
    display_system_health,
    get_health_status,
    get_temp_color,
)


class TestDisplayHelpers:
    """Test display helper functions."""

    def test_get_temp_color(self):
        """Test temperature color logic."""
        # Normal temp
        assert get_temp_color(30, 60, 70) == "green"
        
        # Near warning (within 10%)
        assert get_temp_color(54, 60, 70) == "yellow"
        
        # At warning
        assert get_temp_color(60, 60, 70) == "orange1"
        
        # At critical
        assert get_temp_color(70, 60, 70) == "red"
        
        # None handling
        assert get_temp_color(None, 60, 70) == "dim"

    def test_get_health_status(self):
        """Test health status determination."""
        # Healthy drive
        drive = DriveHealth(
            device_path="/dev/sda",
            drive_type="ata",
            serial="HEALTHY",
            temperature_current=40.0,
            temperature_warning=60.0,
            temperature_critical=70.0,
            temperature_max_24h=42.0,
            last_updated=datetime.now()
        )
        emoji, color = get_health_status(drive)
        assert emoji == "🟢"
        assert color == "green"
        
        # Warning - high temp
        drive = DriveHealth(
            device_path="/dev/sda",
            drive_type="ata",
            serial="WARM",
            temperature_current=65.0,
            temperature_warning=60.0,
            temperature_critical=70.0,
            temperature_max_24h=65.0,
            last_updated=datetime.now()
        )
        emoji, color = get_health_status(drive)
        assert emoji == "🟡"
        assert color == "yellow"
        
        # Critical - new errors
        drive = DriveHealth(
            device_path="/dev/sda",
            drive_type="ata",
            serial="ERRORS",
            temperature_current=40.0,
            temperature_max_24h=42.0,
            temperature_warning=60.0,
            temperature_critical=70.0,
            reallocated_sectors_24h=1,
            last_updated=datetime.now()
        )
        emoji, color = get_health_status(drive)
        assert emoji == "🔴"
        assert color == "red"


class TestTables:
    """Test table creation."""

    def test_system_summary_table(self):
        """Test system summary table creation."""
        system = SystemHealth(
            drives=[],
            total_drives=4,
            healthy_drives=2,
            warning_drives=1,
            critical_drives=1,
            total_errors_24h=3,
            max_temperature=55.0,
            total_reallocated_sectors=5,
            total_pending_sectors=0,
            total_media_errors=1,
            oldest_drive_hours=50000,
            newest_drive_hours=10000,
            nvme_drives=2,
            ata_drives=2,
            last_updated=datetime.now()
        )
        
        table = create_system_summary_table(system)
        assert table.title == "System Health Summary"
        assert len(table.columns) == 2
        
        # Render to string to verify it works
        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        output = console.file.getvalue()
        assert "Total Drives" in output
        assert "4" in output
        assert "🟢" in output
        assert "🟡" in output
        assert "🔴" in output

    def test_drives_table(self):
        """Test drives table creation."""
        drives = [
            DriveHealth(
                device_path="/dev/sda",
                drive_type="ata",
                serial="ATA123",
                temperature_current=45.0,
                temperature_max_24h=48.0,
                temperature_warning=60.0,
                temperature_critical=70.0,
                power_on_hours=20000,
                power_cycles=50,
                reallocated_sectors_total=5,
                reallocated_sectors_24h=1,
                last_updated=datetime.now()
            ),
            DriveHealth(
                device_path="/dev/nvme0",
                drive_type="nvme",
                serial="NVME456",
                temperature_current=50.0,
                temperature_max_24h=52.0,
                temperature_warning=85.0,
                temperature_critical=95.0,
                available_spare_pct=95.0,
                percentage_used=5.0,
                power_on_hours=10000,
                power_cycles=30,
                last_updated=datetime.now()
            ),
        ]
        
        system = SystemHealth(
            drives=drives,
            total_drives=2,
            healthy_drives=1,
            warning_drives=1,
            critical_drives=0,
            total_errors_24h=1,
            max_temperature=50.0,
            total_reallocated_sectors=5,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=20000,
            newest_drive_hours=10000,
            nvme_drives=1,
            ata_drives=1,
            last_updated=datetime.now()
        )
        
        table = create_drives_table(system)
        assert table.title == "Drive Health Details"
        
        # Render to verify
        console = Console(file=StringIO(), width=200)
        console.print(table)
        output = console.file.getvalue()
        assert "sda" in output  # May be truncated
        assert "ATA123" in output
        assert "nvme0" in output
        assert "NVME456" in output
        assert "95%" in output  # Available spare

    def test_full_display(self):
        """Test full system display."""
        drives = [
            DriveHealth(
                device_path="/dev/sda",
                drive_type="ata",
                serial="TEST123",
                temperature_current=45.0,
                temperature_max_24h=48.0,
                last_updated=datetime.now()
            )
        ]
        
        system = SystemHealth(
            drives=drives,
            total_drives=1,
            healthy_drives=1,
            warning_drives=0,
            critical_drives=0,
            total_errors_24h=0,
            max_temperature=45.0,
            total_reallocated_sectors=0,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=10000,
            newest_drive_hours=10000,
            nvme_drives=0,
            ata_drives=1,
            last_updated=datetime.now()
        )
        
        # Should not raise any exceptions
        console = Console(file=StringIO(), force_terminal=True)
        display_system_health(system, console)
        output = console.file.getvalue()
        
        # Verify both tables are present
        assert "System Health Summary" in output
        assert "Drive Health Details" in output
        assert "Legend:" in output

    def test_compact_drives_table(self):
        """Test compact drives table creation."""
        drives = [
            DriveHealth(
                device_path="/dev/sda",
                drive_type="ata",
                serial="ATA123",
                temperature_current=45.0,
                temperature_max_24h=48.0,
                temperature_warning=60.0,
                temperature_critical=70.0,
                power_on_hours=20000,
                reallocated_sectors_total=5,
                reallocated_sectors_24h=1,
                pending_sectors_total=0,
                media_errors_total=0,
                uncorrectable_sectors_total=0,
                last_updated=datetime.now()
            ),
            DriveHealth(
                device_path="/dev/nvme0",
                drive_type="nvme",
                serial="NVME456",
                temperature_current=50.0,
                temperature_max_24h=52.0,
                temperature_warning=85.0,
                temperature_critical=95.0,
                available_spare_pct=95.0,
                percentage_used=5.0,
                power_on_hours=10000,
                reallocated_sectors_total=0,
                pending_sectors_total=0,
                media_errors_total=0,
                uncorrectable_sectors_total=0,
                last_updated=datetime.now()
            ),
        ]
        
        system = SystemHealth(
            drives=drives,
            total_drives=2,
            healthy_drives=1,
            warning_drives=1,
            critical_drives=0,
            total_errors_24h=1,
            max_temperature=50.0,
            total_reallocated_sectors=5,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=20000,
            newest_drive_hours=10000,
            nvme_drives=1,
            ata_drives=1,
            last_updated=datetime.now()
        )
        
        table = create_drives_table_compact(system)
        assert table.title == "Drive Health Details (Compact)"
        
        # Render to verify
        console = Console(file=StringIO(), width=120)
        console.print(table)
        output = console.file.getvalue()
        
        # Check compact format elements
        assert "sda" in output  # Device without /dev/
        assert "Serial: ATA123" in output
        assert "5/0/0/0" in output  # Error summary
        assert "Real/Pend/Media/Uncorr" in output
        assert "Spare: 95%" in output  # NVMe specific
        assert "Used: 5%" in output

    def test_compact_display(self):
        """Test full compact display."""
        drives = [
            DriveHealth(
                device_path="/dev/sda",
                drive_type="ata",
                serial="TEST123",
                temperature_current=45.0,
                temperature_max_24h=48.0,
                power_on_hours=10000,
                reallocated_sectors_total=0,
                pending_sectors_total=0,
                media_errors_total=0,
                uncorrectable_sectors_total=0,
                last_updated=datetime.now()
            )
        ]
        
        system = SystemHealth(
            drives=drives,
            total_drives=1,
            healthy_drives=1,
            warning_drives=0,
            critical_drives=0,
            total_errors_24h=0,
            max_temperature=45.0,
            total_reallocated_sectors=0,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=10000,
            newest_drive_hours=10000,
            nvme_drives=0,
            ata_drives=1,
            last_updated=datetime.now()
        )
        
        # Test compact mode
        console = Console(file=StringIO(), force_terminal=True)
        display_system_health(system, console, compact=True)
        output = console.file.getvalue()
        
        # Verify compact table is used
        assert "Drive Health Details (Compact)" in output
        assert "System Health Summary" in output
        assert "Legend:" in output