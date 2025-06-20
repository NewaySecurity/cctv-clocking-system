# NEWAY SECURITY CCTV CLOCKING SYSTEM

![Neway Security Logo](static/assets/logo.png)

A Python-based face recognition attendance system that uses CCTV/RTSP camera feeds to automatically detect, recognize, and log employee attendance with audio greetings.

## Overview

The NEWAY SECURITY CCTV CLOCKING SYSTEM provides an automated solution for employee attendance tracking using facial recognition technology. The system connects to existing CCTV cameras via RTSP, identifies employees as they enter or leave the premises, and automatically logs their attendance with timestamps.

### Key Features

- **Face Recognition**: Automatically detects and recognizes employees from CCTV footage
- **Audio Greetings**: Plays personalized audio greetings when employees are recognized
- **Attendance Logging**: Records precise clock-in/out times in CSV or Google Sheets
- **Web Dashboard**: Real-time monitoring and attendance management interface
- **Employee Management**: Easy addition and removal of employees with image uploading
- **Comprehensive Settings**: Configurable parameters for all system components

## System Requirements

- **Hardware**:
  - Computer/server with webcam or network access to RTSP camera feed
  - Microphone and speakers (for audio greetings)
  - Minimum 4GB RAM (8GB+ recommended)
  - Sufficient storage for logs and face database

- **Software**:
  - Python 3.8 or higher
  - Web browser for dashboard access
  - Operating System: Windows, macOS, or Linux
  - RTSP-compatible camera (e.g., Andowl 8K WiFi camera)

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/neway-security/cctv-clocking-system.git
cd "NEWAY SECURITY CCTV CLOCKING SYSTEM"
```

### Step 2: Install Dependencies

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### Step 3: Prepare Directories

The system will automatically create necessary directories on first run, but you can manually create them:

```bash
mkdir -p faces logs config
```

### Step 4: Configure the System

1. Edit the configuration file in `config/default.yml` or use the web interface
2. Configure your RTSP camera URL and credentials
3. Adjust face recognition parameters if needed

### Step 5: Run the System

```bash
python src/main.py
```

The web dashboard will be accessible at http://localhost:5000 by default.

## Configuration Guide

The system can be configured in two ways:

1. **Web Interface**: Navigate to Settings in the web dashboard
2. **Configuration File**: Edit `config/default.yml` directly

### Key Configuration Options

#### Camera Settings
- RTSP URL format: `rtsp://username:password@camera-ip:port/stream`
- Frame resolution and processing rate
- Reconnection parameters

#### Face Recognition
- Detection method (HOG or CNN)
- Match tolerance (0.5-0.7 recommended)
- Minimum face size and downscaling for performance

#### Audio Settings
- TTS engine selection (offline pyttsx3 or online gTTS)
- Voice properties (rate, volume, language)
- Custom greeting messages

#### Logging Options
- CSV or Google Sheets storage
- File naming patterns
- Google API credentials (if using Sheets)

## Usage Guide

### Employee Management

1. **Adding Employees**:
   - Navigate to the Employees page
   - Click "Add New Employee"
   - Enter the employee's name
   - Upload clear face images (multiple angles recommended)

2. **Updating Employees**:
   - Click "Update" on an employee card
   - Add additional face images to improve recognition

3. **Deleting Employees**:
   - Click "Delete" on an employee card
   - Confirm deletion in the prompt

### Monitoring Attendance

1. **Live Feed**:
   - The dashboard home page shows the live camera feed
   - Recognized faces are highlighted with name labels
   - Recent events are displayed in the sidebar

2. **Attendance Logs**:
   - Navigate to the Logs page
   - Filter by date range or employee name
   - Export to CSV/Excel as needed
   - Switch between detailed and summary views

### System Maintenance

1. **Check Status Indicators**:
   - Green: System functioning normally
   - Yellow: Warnings or non-critical issues
   - Red: Critical errors requiring attention

2. **Backup Important Data**:
   - Regularly backup the `faces` directory
   - Export attendance logs periodically

## Directory Structure

```
NEWAY SECURITY CCTV CLOCKING SYSTEM/
├── config/                 # Configuration files
│   └── default.yml         # Default configuration
├── docs/                   # Documentation files
├── faces/                  # Employee face images (by name)
│   ├── John_Smith/         # Employee-specific directories
│   │   ├── 1.jpg           # Face images
│   │   └── 2.jpg
│   └── ...
├── logs/                   # Attendance log files
│   └── YYYY-MM.csv         # Monthly CSV log files
├── src/                    # Source code
│   ├── __init__.py
│   ├── audio_manager.py    # Text-to-speech functionality
│   ├── camera_handler.py   # RTSP camera integration
│   ├── data_logger.py      # Attendance logging
│   ├── face_recognition_module.py  # Face detection/recognition
│   ├── main.py             # Main application entry point
│   ├── utils.py            # Utility functions
│   └── web_dashboard.py    # Flask web interface
├── static/                 # Web assets
│   ├── assets/             # Branding and styles
│   │   ├── logo.png        # Neway Security logo
│   │   └── style.css       # Custom CSS
│   └── ...                 # Other static files
├── templates/              # HTML templates
│   ├── base.html           # Base template
│   ├── employees.html      # Employee management
│   ├── index.html          # Dashboard home
│   ├── login.html          # Login page
│   ├── logs.html           # Attendance logs
│   └── settings.html       # System configuration
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Branding Guidelines

The NEWAY SECURITY CCTV CLOCKING SYSTEM follows a specific brand identity with the following color scheme:

- **Primary Color**: Black (#000000) - Used for backgrounds, headers, and primary elements
- **Secondary Color**: Gold (#FFD700) - Used for accents, highlights, and important UI elements
- **Accent Color**: Red (#FF0000) - Used sparingly for alerts, warnings, and critical information

### Logo Placement

The Neway Security logo should be:
- Displayed in the sidebar of the dashboard
- Included on the login screen
- Maintained in all exports and reports

### Color Usage

- Black provides a professional, secure aesthetic as the primary background
- Gold represents premium quality and is used for interactive elements and highlights
- Red is used sparingly to draw attention to important notifications or actions

### Interface Customization

The interface can be customized by modifying:
- `static/assets/style.css` - Custom CSS for the entire application
- `templates/base.html` - Base template that defines the layout structure

## Troubleshooting

### Common Issues

1. **Camera Connection Failures**:
   - Verify RTSP URL format and credentials
   - Ensure camera is powered and connected to network
   - Check firewall settings

2. **Face Recognition Problems**:
   - Add multiple, high-quality face images in different lighting
   - Adjust recognition tolerance in settings
   - Ensure proper camera positioning and lighting

3. **Audio Issues**:
   - Verify speakers are connected and volume is adequate
   - Try alternative TTS engine in settings
   - Check language settings match expected pronunciation

### Getting Help

For technical support or further assistance:
- Email: support@neway-security.com
- Phone: +27 XX XXX XXXX
- Documentation: See the `docs/` directory for detailed guides

## License

Copyright © 2025 Neway Security. All rights reserved.

