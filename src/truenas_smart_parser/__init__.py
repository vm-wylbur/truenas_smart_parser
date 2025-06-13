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
# truenas-smart-parser/src/truenas_smart_parser/__init__.py

"""TrueNAS SMART data parser and analyzer.

Parse SMART CSV logs from smartmontools and analyze drive health with
manufacturer-specific temperature thresholds.
"""

from .parser import (
    DriveHealth,
    SystemHealth,
    analyze_ata_health,
    analyze_nvme_health,
    analyze_smart_directory,
    analyze_smart_remote,
    parse_ata_csv,
    parse_nvme_csv,
    parse_smart_csv,
    query_ata_thresholds,
    query_nvme_thresholds,
)

__version__ = "0.1.0"

__all__ = [
    "DriveHealth",
    "SystemHealth",
    "analyze_smart_directory",
    "analyze_smart_remote",
    "analyze_ata_health",
    "analyze_nvme_health",
    "parse_ata_csv",
    "parse_nvme_csv",
    "parse_smart_csv",
    "query_ata_thresholds",
    "query_nvme_thresholds",
]
