import random
import math
import time
import logging

logger = logging.getLogger("Telemetry")

class TelemetryGenerator:
    """
    Generates telemetry data for the boat.
    This class currently uses generated data but can be modified to use real sensors.
    """
    def __init__(self):
        # Initial position in San Francisco Bay
        self.latitude = 37.7749 + (random.random() - 0.5) * 0.05
        self.longitude = -122.4194 + (random.random() - 0.5) * 0.05
        self.heading = random.random() * 360  # 0-360 degrees
        self.speed = random.random() * 5  # 0-5 knots
        self.battery = 100  # Battery percentage
        
        # For sequence numbering
        self.telemetry_sequence = 0
        
        logger.info(f"Initialized telemetry generator")
        logger.info(f"Initial position: {self.latitude}, {self.longitude}")
    
    def update_position(self):
        """Update the boat position based on current heading and speed."""
        # Update position based on heading and speed
        # Note: This will be replaced with real GPS data in the future
        lat_change = self.speed * 0.0001 * math.cos(math.radians(self.heading))
        lon_change = self.speed * 0.0001 * math.sin(math.radians(self.heading))
        
        self.latitude += lat_change
        self.longitude += lon_change
        
        # Adjust heading and speed occasionally
        if random.random() < 0.1:  # 10% chance each update
            self.heading += (random.random() - 0.5) * 10  # +/- 5 degrees
            self.heading %= 360  # Keep in 0-360 range
            
        if random.random() < 0.05:  # 5% chance each update
            self.speed += (random.random() - 0.5)  # +/- 0.5 knots
            self.speed = max(0, min(10, self.speed))  # Clamp between 0-10 knots
        
        # Battery drain
        self.battery -= 0.01  # Very slow drain 
        self.battery = max(0, self.battery)  # Don't go below 0
    
    def generate_telemetry_data(self):
        """
        Generate a complete telemetry data packet.
        
        Returns:
            dict: Telemetry data
        """
        # Update position
        self.update_position()
        
        # Create telemetry data
        telemetry = {
            "type": "telemetry",
            "subtype": "sensor_data",
            "sequence": self.telemetry_sequence,
            "timestamp": int(time.time() * 1000),
            "system_time": int(time.time() * 1000),
            "data": {
                "gps": {
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "heading": self.heading,
                    "speed": self.speed
                },
                "status": "autonomous_navigation",
                "battery": {
                    "percentage": self.battery,
                    "voltage": 12.0 + (self.battery - 50) * 0.04,  # Voltage drop
                    "current": 2.0 + random.random(),  # Current draw
                    "level": self.battery  # Add level field for web client
                },
                "system": {
                    "cpu_temp": 45.0 + random.random() * 15,  # 45-60°C
                    "signal_strength": -50 - random.random() * 30  # -50 to -80 dBm
                },
                "environment": {
                    "water_temp": 15.0 + random.random() * 5,  # 15-20°C
                    "air_temp": 20.0 + random.random() * 10,  # 20-30°C
                    "air_pressure": 1013.0 + (random.random() - 0.5) * 10,  # 1008-1018 hPa
                    "humidity": 60.0 + random.random() * 20,  # 60-80%
                    "water_depth": 15.0 + random.random() * 2,  # 15-17m
                    "wind_speed": 5.0 + random.random() * 5,  # 5-10 knots
                    "wind_direction": (self.heading + 180 + (random.random() - 0.5) * 45) % 360  # Roughly opposite to heading with some variation
                }
            }
        }
        
        # Increment sequence number
        self.telemetry_sequence += 1
        
        return telemetry
        
    def get_current_status(self):
        """
        Get the current boat status for status requests.
        
        Returns:
            dict: Status data
        """
        return {
            "position": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "heading": self.heading,
                "speed": self.speed
            },
            "battery": {
                "percentage": self.battery,
                "voltage": 12.0 + (self.battery - 50) * 0.04,
                "current": 2.0 + random.random()
            },
            "status": "autonomous_navigation",
            "connection_quality": "good",
            "timestamp": int(time.time() * 1000)
        } 