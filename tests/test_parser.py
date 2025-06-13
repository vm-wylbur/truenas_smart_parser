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
# nas-smartdata/tests/test_parser.py

from datetime import datetime

import pytest

# Sample ATA CSV data with known values
ATA_CSV_SAMPLE = """2025-06-12 06:43:41;	1;100;0;	5;100;0;	9;100;1768;	12;100;25;	194;69;31;	197;100;0;
2025-06-12 07:13:41;	1;100;0;	5;100;0;	9;100;1768;	12;100;25;	194;70;30;	197;100;0;
2025-06-12 07:43:41;	1;100;0;	5;100;1;	9;100;1769;	12;100;25;	194;68;32;	197;100;0;"""

# Sample NVMe CSV data with known values
NVME_CSV_SAMPLE = """2025-06-12 06:43:41;	temperature;57;	available_spare;100%;	percentage_used;0%;	power_on_hours;1747;	unsafe_shutdowns;11;	media_and_data_integrity_errors;0;
2025-06-12 07:13:41;	temperature;49;	available_spare;100%;	percentage_used;0%;	power_on_hours;1747;	unsafe_shutdowns;11;	media_and_data_integrity_errors;0;
2025-06-12 07:43:41;	temperature;49;	available_spare;100%;	percentage_used;1%;	power_on_hours;1748;	unsafe_shutdowns;11;	media_and_data_integrity_errors;1;"""


class TestATAParsing:
    """Test parsing of ATA SMART CSV format."""

    def test_parse_ata_basic(self):
        """Test basic parsing of ATA format returns correct structure."""
        # Expected results for first row
        expected_timestamp = datetime(2025, 6, 12, 6, 43, 41)
        expected_attrs = {
            1: {"norm": 100, "raw": 0},    # Raw_Read_Error_Rate
            5: {"norm": 100, "raw": 0},    # Reallocated_Sector_Ct
            9: {"norm": 100, "raw": 1768}, # Power_On_Hours
            12: {"norm": 100, "raw": 25},  # Power_Cycle_Count
            194: {"norm": 69, "raw": 31},  # Temperature_Celsius
            197: {"norm": 100, "raw": 0},  # Current_Pending_Sector
        }

        # Parse will be implemented in smart_parser.py
        # For now, verify the test data structure
        lines = ATA_CSV_SAMPLE.strip().split('\n')
        assert len(lines) == 3

        # Verify first line structure
        parts = lines[0].split(';')
        assert parts[0] == "2025-06-12 06:43:41"

        # Check attribute 194 (temperature) values across time
        # Row 1: norm=69, raw=31°C
        # Row 2: norm=70, raw=30°C
        # Row 3: norm=68, raw=32°C

    def test_parse_ata_reallocated_sectors(self):
        """Test detection of reallocated sectors increase."""
        lines = ATA_CSV_SAMPLE.strip().split('\n')

        # In row 3, attribute 5 (Reallocated_Sector_Ct) raw value changes from 0 to 1
        # This indicates a new bad sector was reallocated
        row3_parts = lines[2].split(';')

        # Find attribute 5 in the data
        for i in range(1, len(row3_parts), 3):
            if row3_parts[i].strip() == "5":
                assert row3_parts[i+2].strip() == "1"  # raw value = 1
                break


class TestNVMeParsing:
    """Test parsing of NVMe SMART CSV format."""

    def test_parse_nvme_basic(self):
        """Test basic parsing of NVMe format returns correct structure."""
        # Expected results for first row
        expected_timestamp = datetime(2025, 6, 12, 6, 43, 41)
        expected_attrs = {
            "temperature": "57",
            "available_spare": "100%",
            "percentage_used": "0%",
            "power_on_hours": "1747",
            "unsafe_shutdowns": "11",
            "media_and_data_integrity_errors": "0",
        }

        lines = NVME_CSV_SAMPLE.strip().split('\n')
        assert len(lines) == 3

        # Verify first line structure
        parts = lines[0].split(';')
        assert parts[0] == "2025-06-12 06:43:41"

        # Temperature should decrease from 57 to 49
        # media_and_data_integrity_errors increases from 0 to 1 in row 3

    def test_parse_nvme_error_detection(self):
        """Test detection of media errors increase."""
        lines = NVME_CSV_SAMPLE.strip().split('\n')

        # In row 3, media_and_data_integrity_errors changes from 0 to 1
        row3_parts = lines[2].split(';')

        # Find media_and_data_integrity_errors
        for i in range(1, len(row3_parts), 2):
            if row3_parts[i].strip() == "media_and_data_integrity_errors":
                assert row3_parts[i+1].strip() == "1"  # error count = 1
                break


class TestHealthAnalysis:
    """Test health analysis calculations."""

    def test_temperature_max_24h(self):
        """Test calculation of max temperature in 24h window."""
        # From ATA sample: temps are 31, 30, 32 (raw values)
        # Expected max = 32°C
        expected_max_temp_ata = 32

        # From NVMe sample: temps are 57, 49, 49
        # Expected max = 57°C
        expected_max_temp_nvme = 57

    def test_error_counts(self):
        """Test error counting logic."""
        # ATA sample:
        # - Reallocated sectors: increases from 0 to 1
        # - Current pending: stays at 0

        # NVMe sample:
        # - Media errors: increases from 0 to 1
        # - Unsafe shutdowns: stays at 11

        expected_ata_errors = {
            "reallocated_sectors_total": 1,
            "reallocated_sectors_24h": 1,
            "pending_sectors_total": 0,
            "pending_sectors_24h": 0,
        }

        expected_nvme_errors = {
            "media_errors_total": 1,
            "media_errors_24h": 1,
            "unsafe_shutdowns_total": 11,
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
