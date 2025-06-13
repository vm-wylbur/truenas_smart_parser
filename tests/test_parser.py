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
# truenas-smart-parser/tests/test_parser.py

from datetime import datetime

import pytest

from truenas_smart_parser import (
    analyze_ata_health,
    analyze_nvme_health,
    parse_ata_csv,
    parse_nvme_csv,
)

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
        # Parse the CSV
        df = parse_ata_csv(ATA_CSV_SAMPLE)
        
        # Verify we got 3 rows
        assert len(df) == 3
        
        # Check first row timestamp
        first_row = df.row(0, named=True)
        assert first_row['timestamp'] == datetime(2025, 6, 12, 6, 43, 41)
        
        # Check temperature values (attr 194)
        assert df['attr_194_raw'].to_list() == [31, 30, 32]
        
        # Check power-on hours (attr 9)
        assert df['attr_9_raw'].to_list() == [1768, 1768, 1769]

    def test_parse_ata_reallocated_sectors(self):
        """Test detection of reallocated sectors increase."""
        df = parse_ata_csv(ATA_CSV_SAMPLE)
        health = analyze_ata_health(df, serial="TEST001", device_path="/dev/sda")
        
        # Check that reallocated sectors increased from 0 to 1
        assert health.reallocated_sectors_total == 1
        assert health.reallocated_sectors_24h == 1


class TestNVMeParsing:
    """Test parsing of NVMe SMART CSV format."""

    def test_parse_nvme_basic(self):
        """Test basic parsing of NVMe format returns correct structure."""
        # Parse the CSV
        df = parse_nvme_csv(NVME_CSV_SAMPLE)
        
        # Verify we got 3 rows
        assert len(df) == 3
        
        # Check first row timestamp
        first_row = df.row(0, named=True)
        assert first_row['timestamp'] == datetime(2025, 6, 12, 6, 43, 41)
        
        # Check temperature values
        assert df['temperature'].to_list() == [57, 49, 49]
        
        # Check percentage values were parsed correctly
        assert df['available_spare'].to_list() == [100.0, 100.0, 100.0]
        assert df['percentage_used'].to_list() == [0.0, 0.0, 1.0]

    def test_parse_nvme_error_detection(self):
        """Test detection of media errors increase."""
        df = parse_nvme_csv(NVME_CSV_SAMPLE)
        health = analyze_nvme_health(df, serial="TEST-NVME", device_path="/dev/nvme0")
        
        # Check that media errors increased from 0 to 1
        assert health.media_errors_total == 1
        assert health.media_errors_24h == 1


class TestHealthAnalysis:
    """Test health analysis calculations."""

    def test_temperature_max_24h(self):
        """Test calculation of max temperature in 24h window."""
        # Test ATA temperature max
        df_ata = parse_ata_csv(ATA_CSV_SAMPLE)
        health_ata = analyze_ata_health(df_ata, serial="TEST", device_path="/dev/sda")
        assert health_ata.temperature_current == 32.0  # Last value
        assert health_ata.temperature_max_24h == 32.0  # Max of 31, 30, 32
        
        # Test NVMe temperature max
        df_nvme = parse_nvme_csv(NVME_CSV_SAMPLE)
        health_nvme = analyze_nvme_health(df_nvme, serial="TEST", device_path="/dev/nvme0")
        assert health_nvme.temperature_current == 49.0  # Last value
        assert health_nvme.temperature_max_24h == 57.0  # Max of 57, 49, 49

    def test_error_counts(self):
        """Test error counting logic."""
        # Test ATA error counts
        df_ata = parse_ata_csv(ATA_CSV_SAMPLE)
        health_ata = analyze_ata_health(df_ata, serial="TEST", device_path="/dev/sda")
        assert health_ata.reallocated_sectors_total == 1
        assert health_ata.reallocated_sectors_24h == 1
        assert health_ata.pending_sectors_total == 0
        assert health_ata.pending_sectors_24h == 0
        
        # Test NVMe error counts
        df_nvme = parse_nvme_csv(NVME_CSV_SAMPLE)
        health_nvme = analyze_nvme_health(df_nvme, serial="TEST", device_path="/dev/nvme0")
        assert health_nvme.media_errors_total == 1
        assert health_nvme.media_errors_24h == 1
        assert health_nvme.unsafe_shutdowns == 11


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
