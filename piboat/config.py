import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Server Configuration
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "localhost")
SERVER_PORT = os.getenv("SERVER_PORT", "8000")
WS_SERVER_URL = f"ws://{SERVER_DOMAIN}:{SERVER_PORT}/ws/device/{{device_id}}"
DEVICE_ID = os.getenv("DEVICE_ID", "boat-1")

# Telemetry Configuration
TELEMETRY_INTERVAL = float(os.getenv("TELEMETRY_INTERVAL", "1.0"))  # Send telemetry every 1 second

# Video Configuration
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1280"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "720"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))

# You can customize these values using environment variables
if os.environ.get("WS_SERVER_URL"):
    WS_SERVER_URL = os.environ.get("WS_SERVER_URL")
    
if os.environ.get("DEVICE_ID"):
    DEVICE_ID = os.environ.get("DEVICE_ID")
    
if os.environ.get("TELEMETRY_INTERVAL"):
    TELEMETRY_INTERVAL = float(os.environ.get("TELEMETRY_INTERVAL")) 