"""
Data logging module for NEWAY SECURITY CCTV CLOCKING SYSTEM.

This module provides attendance logging functionality with both CSV and
Google Sheets backends, duplicate entry prevention, and data retrieval.
"""

import os
import csv
import datetime
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any
from enum import Enum
import threading

import pandas as pd

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from src.utils import get_logger, load_config, LOGS_DIR

# Initialize logger
logger = get_logger(__name__)

class EventType(Enum):
    """Types of attendance events."""
    CLOCK_IN = "IN"
    CLOCK_OUT = "OUT"
    UNKNOWN = "UNKNOWN"

class LoggerBackend(Enum):
    """Available logger backends."""
    CSV = "csv"
    GOOGLE_SHEETS = "google_sheets"

class AttendanceLogger:
    """
    Base class for attendance logging functionality.
    
    Features:
    - Record clock in/out events
    - Prevent duplicate entries
    - Query attendance records
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the attendance logger.
        
        Args:
            config: Logging configuration. If None, loads from default config.
        """
        # Load configuration
        if config is None:
            self.config = load_config().get('logging', {})
        else:
            self.config = config
            
        # Extract configuration
        self.log_format = self.config.get('format', 'csv')
        self.csv_filename_pattern = self.config.get('csv_filename_pattern', '%Y-%m.csv')
        self.recognition_timeout = load_config().get('face_recognition', {}).get('recognition_timeout', 8)
        
        # Convert timeout from hours to seconds
        self.recognition_timeout_seconds = self.recognition_timeout * 3600
        
        # Runtime state
        self.last_events: Dict[str, Dict[str, datetime.datetime]] = {}
        self.lock = threading.RLock()
        
        # Initialize appropriate backend
        self._init_backend()
        
        logger.info(f"AttendanceLogger initialized with {self.log_format} backend")
    
    def _init_backend(self) -> None:
        """Initialize the appropriate logging backend based on configuration."""
        if self.log_format == LoggerBackend.GOOGLE_SHEETS.value:
            if not GOOGLE_API_AVAILABLE:
                logger.warning("Google Sheets API not available, falling back to CSV")
                self.log_format = LoggerBackend.CSV.value
                self._init_csv_backend()
            else:
                self._init_gsheets_backend()
        else:
            self._init_csv_backend()
    
    def _init_csv_backend(self) -> None:
        """Initialize the CSV logging backend."""
        # Ensure logs directory exists
        if not LOGS_DIR.exists():
            logger.info(f"Creating logs directory: {LOGS_DIR}")
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            
        logger.info("CSV logging backend initialized")
    
    def _init_gsheets_backend(self) -> None:
        """Initialize the Google Sheets logging backend."""
        # Extract Google Sheets configuration
        gsheets_config = self.config.get('google_sheets', {})
        self.credentials_file = gsheets_config.get('credentials_file')
        self.sheet_id = gsheets_config.get('sheet_id')
        self.sheet_name = gsheets_config.get('sheet_name', 'Attendance')
        
        # Validate configuration
        if not self.sheet_id:
            logger.warning("Google Sheet ID not configured, falling back to CSV")
            self.log_format = LoggerBackend.CSV.value
            return
            
        if not self.credentials_file or not Path(self.credentials_file).exists():
            logger.warning(f"Google API credentials file not found: {self.credentials_file}")
            logger.warning("Falling back to CSV logging")
            self.log_format = LoggerBackend.CSV.value
            return
            
        try:
            # Authenticate with Google API
            credentials = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.sheets_service = build('sheets', 'v4', credentials=credentials)
            
            # Check if sheet exists and create if not
            self._ensure_sheet_exists()
            
            logger.info(f"Google Sheets logging backend initialized with sheet ID: {self.sheet_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets backend: {e}")
            logger.warning("Falling back to CSV logging")
            self.log_format = LoggerBackend.CSV.value
    
    def _ensure_sheet_exists(self) -> None:
        """Ensure the specified sheet exists in the Google Spreadsheet."""
        try:
            # Get all sheets in the spreadsheet
            spreadsheet = self.sheets_service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            sheets = [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]
            
            # Check if our sheet exists
            if self.sheet_name not in sheets:
                logger.info(f"Creating new sheet '{self.sheet_name}' in Google Spreadsheet")
                
                # Create a new sheet
                request = {
                    'addSheet': {
                        'properties': {
                            'title': self.sheet_name
                        }
                    }
                }
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={'requests': [request]}
                ).execute()
                
                # Add header row
                self._write_to_gsheet(
                    [['Name', 'Date', 'Time', 'Event']],
                    f"{self.sheet_name}!A1:D1"
                )
                
                logger.info(f"Sheet '{self.sheet_name}' created successfully")
                
        except HttpError as e:
            logger.error(f"Error accessing Google Spreadsheet: {e}")
            raise
    
    def _get_csv_filename(self, dt: datetime.datetime = None) -> Path:
        """
        Get the CSV filename for the current month.
        
        Args:
            dt: Date to use for filename. If None, uses current date.
            
        Returns:
            Path to the CSV file
        """
        if dt is None:
            dt = datetime.datetime.now()
            
        filename = dt.strftime(self.csv_filename_pattern)
        return LOGS_DIR / filename
    
    def _write_to_csv(self, data: List[List[str]], filename: Optional[Path] = None) -> bool:
        """
        Write data to a CSV file.
        
        Args:
            data: List of rows to write
            filename: Path to CSV file. If None, uses current month's file.
            
        Returns:
            True if successful, False otherwise
        """
        if filename is None:
            filename = self._get_csv_filename()
            
        file_exists = filename.exists()
        
        try:
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header if new file
                if not file_exists:
                    writer.writerow(['Name', 'Date', 'Time', 'Event'])
                
                # Write data rows
                writer.writerows(data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error writing to CSV file {filename}: {e}")
            return False
    
    def _write_to_gsheet(self, data: List[List[str]], range_name: str) -> bool:
        """
        Write data to a Google Sheet.
        
        Args:
            data: List of rows to write
            range_name: A1 notation of the range to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            body = {
                'values': data
            }
            
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing to Google Sheet: {e}")
            return False
    
    def log_event(self, name: str, event_type: EventType = EventType.CLOCK_IN) -> bool:
        """
        Log an attendance event.
        
        Args:
            name: Person's name
            event_type: Type of event (IN/OUT)
            
        Returns:
            True if event was logged, False if skipped due to duplicate prevention
        """
        with self.lock:
            # Get current timestamp
            now = datetime.datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')
            
            # Check for duplicate entry
            if name in self.last_events and event_type.value in self.last_events[name]:
                last_time = self.last_events[name][event_type.value]
                time_diff = (now - last_time).total_seconds()
                
                if time_diff < self.recognition_timeout_seconds:
                    logger.debug(
                        f"Skipping duplicate {event_type.value} event for {name}, "
                        f"last event was {time_diff:.1f}s ago "
                        f"(timeout: {self.recognition_timeout_seconds}s)"
                    )
                    return False
            
            # Prepare data row
            data_row = [name, date_str, time_str, event_type.value]
            
            # Log to appropriate backend
            success = False
            if self.log_format == LoggerBackend.GOOGLE_SHEETS.value:
                range_name = f"{self.sheet_name}!A:D"
                success = self._write_to_gsheet([data_row], range_name)
            else:
                success = self._write_to_csv([data_row])
            
            # Update last event time if successful
            if success:
                if name not in self.last_events:
                    self.last_events[name] = {}
                    
                self.last_events[name][event_type.value] = now
                logger.info(f"Logged {event_type.value} event for {name} at {date_str} {time_str}")
            
            return success
    
    def get_events(
        self,
        start_date: Optional[datetime.datetime] = None,
        end_date: Optional[datetime.datetime] = None,
        name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get attendance events within a date range.
        
        Args:
            start_date: Start date for events (inclusive)
            end_date: End date for events (inclusive)
            name: Filter by person name
            
        Returns:
            DataFrame with attendance records
        """
        # Default to current month if no dates provided
        if start_date is None:
            today = datetime.datetime.now()
            start_date = datetime.datetime(today.year, today.month, 1)
            
        if end_date is None:
            end_date = datetime.datetime.now()
            
        # For Google Sheets backend
        if self.log_format == LoggerBackend.GOOGLE_SHEETS.value:
            return self._get_events_from_gsheet(start_date, end_date, name)
            
        # For CSV backend
        return self._get_events_from_csv(start_date, end_date, name)
    
    def _get_events_from_csv(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get attendance events from CSV files.
        
        Args:
            start_date: Start date for events
            end_date: End date for events
            name: Filter by person name
            
        Returns:
            DataFrame with attendance records
        """
        # Calculate which monthly files we need to read
        current_date = start_date
        filenames = []
        
        while current_date <= end_date:
            filenames.append(self._get_csv_filename(current_date))
            
            # Move to next month
            if current_date.month == 12:
                current_date = datetime.datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime.datetime(current_date.year, current_date.month + 1, 1)
        
        # Read and combine data from all relevant files
        dfs = []
        for filename in filenames:
            if filename.exists():
                try:
                    df = pd.read_csv(filename)
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Error reading CSV file {filename}: {e}")
        
        # If no data found, return empty DataFrame
        if not dfs:
            return pd.DataFrame(columns=['Name', 'Date', 'Time', 'Event'])
            
        # Combine all data
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # Convert Date column to datetime
        combined_df['Date'] = pd.to_datetime(combined_df['Date'])
        
        # Filter by date range
        mask = (combined_df['Date'] >= start_date.strftime('%Y-%m-%d')) & \
               (combined_df['Date'] <= end_date.strftime('%Y-%m-%d'))
        filtered_df = combined_df[mask]
        
        # Filter by name if provided
        if name:
            filtered_df = filtered_df[filtered_df['Name'] == name]
            
        return filtered_df
    
    def _get_events_from_gsheet(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get attendance events from Google Sheet.
        
        Args:
            start_date: Start date for events
            end_date: End date for events
            name: Filter by person name
            
        Returns:
            DataFrame with attendance records
        """
        try:
            # Get all data from the sheet
            range_name = f"{self.sheet_name}!A:D"
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            
            # Extract values
            values = result.get('values', [])
            
            # If no data, return empty DataFrame
            if not values:
                return pd.DataFrame(columns=['Name', 'Date', 'Time', 'Event'])
                
            # Create DataFrame (first row is header)
            df = pd.DataFrame(values[1:], columns=values[0])
            
            # Convert Date column to datetime
            df['Date'] = pd.to_datetime(df['Date'])
            
            # Filter by date range
            mask = (df['Date'] >= start_date.strftime('%Y-%m-%d')) & \
                   (df['Date'] <= end_date.strftime('%Y-%m-%d'))
            filtered_df = df[mask]
            
            # Filter by name if provided
            if name:
                filtered_df = filtered_df[filtered_df['Name'] == name]
                
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error retrieving data from Google Sheet: {e}")
            return pd.DataFrame(columns=['Name', 'Date', 'Time', 'Event'])
    
    def get_daily_summary(self, date: Optional[datetime.datetime] = None) -> pd.DataFrame:
        """
        Get a summary of attendance for a specific day.
        
        Args:
            date: The date to summarize. If None, uses today.
            
        Returns:
            DataFrame with daily attendance summary
        """
        if date is None:
            date = datetime.datetime.now()
            
        # Get all events for the day
        events_df = self.get_events(date, date)
        
        # If no data, return empty DataFrame
        if events_df.empty:
            return pd.DataFrame(columns=['Name', 'First In', 'Last Out', 'Duration'])
            
        # Group by name and get first IN and last OUT for each person
        summary = []
        for name in events_df['Name'].unique():
            person_df = events_df[events_df['Name'] == name]
            
            # Get first IN and last OUT
            in_records = person_df[person_df['Event'] == 'IN']
            out_records = person_df[person_df['Event'] == 'OUT']
            
            first_in = None
            last_out = None
            duration = None
            
            if not in_records.empty:
                in_times = pd.to_datetime(
                    in_records['Date'].astype(str) + ' ' + in_records['Time'].astype(str)
                )
                first_in = in_times.min()
                
            if not out_records.empty:
                out_times = pd.to_datetime(
                    out_records['Date'].astype(str) + ' ' + out_records['Time'].astype(str)
                )
                last_out = out_times.max()
                
            # Calculate duration if both in and out exist
            if first_in and last_out and last_out > first_in:
                duration = last_out - first_in
                duration_str = str(duration)
            else:
                duration_str = 'N/A'
                
            summary.append({
                'Name': name,
                'First In': first_in.strftime('%H:%M:%S') if first_in else 'N/A',
                'Last Out': last_out.strftime('%H:%M:%S') if last_out else 'N/A',
                'Duration': duration_str
            })
            
        return pd.DataFrame(summary)


# Example usage
if __name__ == "__main__":
    # Initialize logger
    logger = AttendanceLogger()
    
    # Test logging events
    logger.log_event("Thabiso", EventType.CLOCK_IN)
    time.sleep(1)
    logger.log_event("Sihle", EventType.CLOCK_IN)
    time.sleep(1)
    
    # This should be blocked by duplicate prevention
    blocked = not logger.log_event("Thabiso", EventType.CLOCK_IN)
    print(f"Duplicate event blocked: {blocked}")
    
    # Log out event
    logger.log_event("Thabiso", EventType.CLOCK_OUT)
    
    # Get today's events
    today = datetime.datetime.now()
    events = logger.get_events(today, today)
    print("\nToday's events:")
    print(events)
    
    # Get daily summary
    summary = logger.get_daily_summary()
    print("\nDaily summary:")
    print(summary)

