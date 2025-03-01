# Autonomous Boat Project 

An autonomous boat system built with Python and running on a Raspberry Pi.

## Project Overview

This project aims to develop an autonomous boat capable of navigating waterways independently using a Raspberry Pi as the main controller. The boat will use various sensors for navigation, obstacle avoidance, and data collection.

## Project Structure

The project is organized into the following components:

```
piboat/
├── __init__.py         # Package init
├── config.py           # Configuration settings
├── main.py             # Entry point
├── device/             # Device-related components
│   ├── __init__.py
│   ├── device.py       # Main BoatDevice class
│   ├── telemetry.py    # Telemetry generation
│   └── commands.py     # Command handling
├── webrtc/             # WebRTC-related components
│   ├── __init__.py
│   ├── video.py        # Video streaming
│   └── webrtc_handler.py # WebRTC connection management
└── utils/              # Utility functions
    ├── __init__.py
    └── logging_setup.py # Logging configuration
```

## Hardware Requirements

- Raspberry Pi (3B+ or 4 recommended)
- Motor controller
- Propulsion system (motors, propellers)
- Power supply (batteries)
- Sensors (GPS, compass, ultrasonic, etc.)
- Waterproof enclosure

## Software Dependencies

- Python 3.7+
- Required Python libraries (see requirements.txt):
  - websockets
  - aiortc
  - aiohttp
  - opencv-python
  - numpy

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd PiBoat
   ```

2. Set up a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the Boat Device

To run the autonomous boat control system:

1. Make sure you have all dependencies installed
2. Run the boat device:
   ```
   ./run_boat_device.py
   ```
   
   Or alternatively:
   ```
   python run_boat_device.py
   ```

### Configuration

You can configure the boat device by setting environment variables:

- `WS_SERVER_URL`: The WebSocket server URL (default: `ws://192.168.1.227:8000/ws/device/{device_id}`)
- `DEVICE_ID`: The device ID to use (default: `boat-1`)
- `TELEMETRY_INTERVAL`: How often to send telemetry data in seconds (default: `1.0`)

Example:
```
DEVICE_ID=my-test-boat WS_SERVER_URL="ws://myserver.com:8000/ws/device/{device_id}" ./run_boat_device.py
```

## Usage

Usage instructions will be provided once the project reaches a functional state.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 