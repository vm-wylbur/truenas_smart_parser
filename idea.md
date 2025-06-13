CONCLUSION: NetData SMART Data Availability

After thorough investigation, here's what I found:

Current State
The NetData smart_log module is hardcoded to ONLY track temperature data from SMART logs. Looking at the source code, it specifically filters for only these attributes:
•  ATTR194 (Temperature)
•  ATTR190 (Alternative temperature) 
•  ATTR_TEMPERATURE (SCSI/NVMe temperature)

What's Available in the Raw Data
The SMART logs in /var/lib/smartmontools/ contain MASSIVE amounts of additional data that NetData is completely ignoring:

For ATA/SATA disks:
•  Raw Read Error Rate (ID 1)
•  Reallocated Sector Count (ID 5) 
•  Power-On Hours (ID 9)
•  Power Cycle Count (ID 12)
•  And ~20 other critical health attributes

For NVMe drives:
•  Available Spare
•  Percentage Used  
•  Data Units Read/Written
•  Host Read/Write Commands
•  Controller Busy Time
•  Power Cycles
•  Unsafe Shutdowns
•  Media and Data Integrity Errors
•  All critical health indicators

The Answer to Your Question
NO - this additional SMART data is NOT available through NetData. The smart_log module is severely limited and only extracts temperature.

What We Could Do
1. Modify the NetData smart_log module to track additional attributes
2. Create a separate data collection script that parses the existing rich SMART logs
3. Use direct smartctl queries for real-time data (no historical trends)

The goldmine of SMART data exists in those CSV files, but NetData isn't using it. We'd need to either extend NetData's capabilities or build our own 24h analysis tool that directly processes those comprehensive SMART logs.
