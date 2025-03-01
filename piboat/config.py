import os

# Server Configuration
WS_SERVER_URL = "ws://192.168.1.227:8000/ws/device/{device_id}"
DEVICE_ID = "boat-1"

# Telemetry Configuration
TELEMETRY_INTERVAL = 1.0  # Send telemetry every 1 second

# Video Configuration
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480
VIDEO_FPS = 30

# You can customize these values using environment variables
if os.environ.get("WS_SERVER_URL"):
    WS_SERVER_URL = os.environ.get("WS_SERVER_URL")
    
if os.environ.get("DEVICE_ID"):
    DEVICE_ID = os.environ.get("DEVICE_ID")
    
if os.environ.get("TELEMETRY_INTERVAL"):
    TELEMETRY_INTERVAL = float(os.environ.get("TELEMETRY_INTERVAL")) 