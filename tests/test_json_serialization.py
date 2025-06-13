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
# truenas-smart-parser/tests/test_json_serialization.py

import json
from datetime import datetime

from truenas_smart_parser import DriveHealth, SystemHealth


class TestJSONSerialization:
    """Test JSON serialization of health objects."""

    def test_drive_health_to_dict(self):
        """Test DriveHealth.to_dict() creates valid JSON structure."""
        drive = DriveHealth(
            device_path="/dev/sda",
            drive_type="ata",
            serial="TEST123",
            temperature_current=45.0,
            temperature_max_24h=48.0,
            temperature_warning=None,
            temperature_critical=70.0,
            temperature_operational_max=60.0,
            reallocated_sectors_total=5,
            reallocated_sectors_24h=1,
            power_on_hours=12345,
            power_cycles=100,
            last_updated=datetime(2025, 6, 12, 10, 30, 45)
        )

        # Convert to dict
        drive_dict = drive.to_dict()

        # Verify structure
        assert drive_dict['device_path'] == "/dev/sda"
        assert drive_dict['drive_type'] == "ata"
        assert drive_dict['serial'] == "TEST123"
        assert drive_dict['temperature']['current'] == 45.0
        assert drive_dict['temperature']['max_24h'] == 48.0
        assert drive_dict['temperature']['critical'] == 70.0
        assert drive_dict['errors']['total']['reallocated_sectors'] == 5
        assert drive_dict['errors']['24h']['reallocated_sectors'] == 1
        assert drive_dict['info']['power_on_hours'] == 12345
        assert drive_dict['info']['last_updated'] == "2025-06-12T10:30:45"

        # Verify JSON serializable
        json_str = json.dumps(drive_dict)
        assert isinstance(json_str, str)

        # Verify can parse back
        parsed = json.loads(json_str)
        assert parsed['device_path'] == "/dev/sda"

    def test_system_health_to_dict(self):
        """Test SystemHealth.to_dict() creates valid JSON structure."""
        drives = [
            DriveHealth(
                device_path="/dev/sda",
                drive_type="ata",
                serial="TEST123",
                temperature_current=45.0,
                temperature_max_24h=48.0,
                last_updated=datetime(2025, 6, 12, 10, 30, 45)
            ),
            DriveHealth(
                device_path="/dev/nvme0",
                drive_type="nvme",
                serial="NVME456",
                temperature_current=50.0,
                temperature_max_24h=52.0,
                available_spare_pct=100.0,
                percentage_used=1.0,
                last_updated=datetime(2025, 6, 12, 10, 30, 45)
            ),
        ]

        system = SystemHealth(
            drives=drives,
            total_drives=2,
            healthy_drives=2,
            warning_drives=0,
            critical_drives=0,
            total_errors_24h=0,
            max_temperature=50.0,
            total_reallocated_sectors=0,
            total_pending_sectors=0,
            total_media_errors=0,
            oldest_drive_hours=12345,
            newest_drive_hours=1000,
            nvme_drives=1,
            ata_drives=1,
            last_updated=datetime(2025, 6, 12, 10, 30, 45)
        )

        # Convert to dict
        system_dict = system.to_dict()

        # Verify structure
        assert system_dict['summary']['total_drives'] == 2
        assert system_dict['summary']['healthy_drives'] == 2
        assert system_dict['summary']['max_temperature'] == 50.0
        assert system_dict['system']['nvme_drives'] == 1
        assert system_dict['system']['ata_drives'] == 1
        assert system_dict['system']['last_updated'] == "2025-06-12T10:30:45"
        assert len(system_dict['drives']) == 2
        assert system_dict['drives'][0]['serial'] == "TEST123"
        assert system_dict['drives'][1]['serial'] == "NVME456"

        # Verify JSON serializable
        json_str = json.dumps(system_dict)
        assert isinstance(json_str, str)

        # Verify can parse back
        parsed = json.loads(json_str)
        assert parsed['summary']['total_drives'] == 2

    def test_none_datetime_handling(self):
        """Test that None datetime is handled properly."""
        drive = DriveHealth(
            device_path="/dev/sda",
            drive_type="ata",
            serial="TEST123",
            temperature_current=None,
            temperature_max_24h=None,
            last_updated=None  # This should be handled
        )

        drive_dict = drive.to_dict()
        assert drive_dict['info']['last_updated'] is None

        # Should still be JSON serializable
        json_str = json.dumps(drive_dict)
        parsed = json.loads(json_str)
        assert parsed['info']['last_updated'] is None
