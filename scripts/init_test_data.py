#!/usr/bin/env python3
"""
Test Data Initialization Script for NEWAY SECURITY CCTV CLOCKING SYSTEM

This script creates sample employee directories and test data to help
users get started with the system.
"""

import os
import sys
import shutil
import argparse
import datetime
import csv
from pathlib import Path

# Add project root to sys.path if needed
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils import get_logger, FACES_DIR, LOGS_DIR

# Initialize logger
logger = get_logger(__name__)

# Sample employee data
SAMPLE_EMPLOYEES = [
    {
        "name": "John_Smith",
        "display_name": "John Smith",
        "description": "Security Manager"
    },
    {
        "name": "Sarah_Johnson",
        "display_name": "Sarah Johnson",
        "description": "Receptionist"
    },
    {
        "name": "David_Nkosi",
        "display_name": "David Nkosi",
        "description": "Security Officer"
    },
    {
        "name": "Thabo_Mokoena",
        "display_name": "Thabo Mokoena",
        "description": "IT Manager"
    },
    {
        "name": "Emily_Williams",
        "display_name": "Emily Williams",
        "description": "HR Director"
    }
]

# Sample log entries
def generate_sample_logs():
    """Generate sample attendance log entries for the past week."""
    today = datetime.datetime.now()
    sample_logs = []
    
    # Generate entries for the past 7 days
    for day_offset in range(7):
        # Calculate date
        log_date = today - datetime.timedelta(days=day_offset)
        date_str = log_date.strftime('%Y-%m-%d')
        
        # Generate entries for each employee
        for employee in SAMPLE_EMPLOYEES:
            # Clock in (morning)
            clock_in_hour = 7 + (employee["name"].hash() % 2)  # Vary between 7 and 8 AM
            clock_in_min = employee["name"].hash() % 60
            clock_in_time = f"{clock_in_hour:02d}:{clock_in_min:02d}:00"
            
            # Clock out (evening)
            clock_out_hour = 16 + (employee["name"].hash() % 3)  # Vary between 16 and 18 (4-6 PM)
            clock_out_min = employee["name"].hash() % 60
            clock_out_time = f"{clock_out_hour:02d}:{clock_out_min:02d}:00"
            
            # Add entries (skip weekends for some employees to simulate days off)
            if log_date.weekday() < 5 or employee["name"].hash() % 3 == 0:
                sample_logs.append([employee["display_name"], date_str, clock_in_time, "IN"])
                sample_logs.append([employee["display_name"], date_str, clock_out_time, "OUT"])
    
    return sample_logs

def create_employee_directories():
    """Create sample employee directories in the faces folder."""
    print(f"Creating sample employee directories in {FACES_DIR}...")
    
    # Create faces directory if it doesn't exist
    FACES_DIR.mkdir(exist_ok=True, parents=True)
    
    # Create employee directories
    for employee in SAMPLE_EMPLOYEES:
        employee_dir = FACES_DIR / employee["name"]
        
        # Create directory if it doesn't exist
        if not employee_dir.exists():
            employee_dir.mkdir(exist_ok=True)
            print(f"Created directory for {employee['display_name']} at {employee_dir}")
        else:
            print(f"Directory for {employee['display_name']} already exists")
        
        # Create a placeholder text file with instructions
        placeholder_file = employee_dir / "README.txt"
        with open(placeholder_file, 'w') as f:
            f.write(f"Sample Employee: {employee['display_name']}\n")
            f.write(f"Role: {employee['description']}\n\n")
            f.write("Instructions:\n")
            f.write("1. Add clear face images of this person to this directory\n")
            f.write("2. Images should show the face clearly with good lighting\n")
            f.write("3. Multiple angles improve recognition accuracy\n")
            f.write("4. Acceptable formats: JPG, JPEG, PNG\n")
            f.write("5. The system will automatically process these images\n")

def create_sample_logs():
    """Create sample attendance log entries."""
    print(f"Creating sample attendance logs in {LOGS_DIR}...")
    
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(exist_ok=True, parents=True)
    
    # Generate sample log data
    sample_logs = generate_sample_logs()
    
    # Group by month for monthly CSV files
    logs_by_month = {}
    for entry in sample_logs:
        date = entry[1]  # Date is in second column
        month_key = date[:7]  # YYYY-MM
        
        if month_key not in logs_by_month:
            logs_by_month[month_key] = []
            
        logs_by_month[month_key].append(entry)
    
    # Create monthly CSV files
    for month_key, entries in logs_by_month.items():
        # Create filename like 2023-06.csv
        csv_file = LOGS_DIR / f"{month_key}.csv"
        
        # Write to CSV
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(['Name', 'Date', 'Time', 'Event'])
            # Write entries
            writer.writerows(entries)
            
        print(f"Created sample log file: {csv_file} with {len(entries)} entries")

def main():
    """Main function to initialize test data."""
    parser = argparse.ArgumentParser(description="Initialize test data for NEWAY SECURITY CCTV CLOCKING SYSTEM")
    
    parser.add_argument("--employees", action="store_true", help="Create sample employee directories")
    parser.add_argument("--logs", action="store_true", help="Create sample attendance logs")
    parser.add_argument("--all", action="store_true", help="Create all sample data")
    
    args = parser.parse_args()
    
    # If no args specified, show help
    if not (args.employees or args.logs or args.all):
        parser.print_help()
        return
    
    # Create sample data based on arguments
    if args.employees or args.all:
        create_employee_directories()
        
    if args.logs or args.all:
        create_sample_logs()
        
    print("\nSample data initialization complete.")
    print("Next steps:")
    print("1. Add face images to the employee directories in faces/")
    print("2. Configure your camera settings in config/default.yml")
    print("3. Run the system with: python src/main.py")

if __name__ == "__main__":
    main()

