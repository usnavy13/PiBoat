import random
import math
import time
import logging
import decimal  # Add import for decimal module
from piboat.device.gps_handler import GPSHandler

logger = logging.getLogger("Telemetry")

class TelemetryGenerator:
    """
    Generates telemetry data for the boat.
    This class uses GPS data when available, falling back to generated data if not.
    """
    def __init__(self, use_gps=True, gps_port='/dev/ttyACM0'):
        # Initial position in San Francisco Bay
        self.latitude = 37.7749 + (random.random() - 0.5) * 0.05
        self.longitude = -122.4194 + (random.random() - 0.5) * 0.05
        self.heading = random.random() * 360  # 0-360 degrees
        self.speed = random.random() * 5  # 0-5 knots
        self.battery = 100  # Battery percentage
        
        # For sequence numbering
        self.telemetry_sequence = 0
        
        # GPS integration
        self.use_gps = use_gps
        self.gps = None
        
        if self.use_gps:
            self._init_gps(gps_port)
        
        logger.info(f"Initialized telemetry generator")
        logger.info(f"Initial position: {self.latitude}, {self.longitude}")
    
    def _init_gps(self, port):
        """Initialize the GPS handler."""
        try:
            self.gps = GPSHandler(port=port)
            self.gps.start()
            logger.info(f"GPS handler started on port {port}")
        except Exception as e:
            logger.error(f"Failed to initialize GPS: {str(e)}")
            self.use_gps = False
    
    def update_position(self):
        """
        Update the boat position based on GPS data if available,
        otherwise use simulated movement.
        """
        if self.use_gps and self.gps:
            gps_data = self.gps.get_gps_data()
            
            # Update position if we have valid GPS data
            if gps_data['has_fix'] and gps_data['latitude'] is not None and gps_data['longitude'] is not None:
                self.latitude = gps_data['latitude']
                self.longitude = gps_data['longitude']
                logger.debug(f"Updated position from GPS: {self.latitude}, {self.longitude}")
                
                # Update speed and heading if available
                if gps_data['speed_knots'] is not None:
                    self.speed = gps_data['speed_knots']
                if gps_data['course'] is not None:
                    self.heading = gps_data['course']
                return
            else:
                logger.debug("No GPS fix available, using simulated movement")
        
        # Fallback to simulated movement if no GPS or no GPS fix
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
    
    def _convert_decimal_values(self, data):
        """Convert any Decimal values in the data structure to float for JSON serialization."""
        if isinstance(data, dict):
            return {k: self._convert_decimal_values(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_decimal_values(i) for i in data]
        elif isinstance(data, decimal.Decimal):
            # Convert Decimal to float for JSON serialization
            return float(data)
        else:
            return data
    
    def generate_telemetry_data(self, increment_sequence=False):
        """Generate telemetry data for the boat."""
        # First update the position
        self.update_position()
        
        # Get GPS status if available
        gps_status = {}
        position_source = "simulation"  # Default to simulation
        
        if self.use_gps and self.gps:
            gps_data = self.gps.get_gps_data()
            
            # Add acquiring_fix status
            # We are acquiring a fix if GPS is active but doesn't have a fix yet
            acquiring_fix = gps_data['running'] and not gps_data['has_fix']
            
            # Set position source based on GPS fix
            if gps_data['has_fix']:
                position_source = "gps"
                
            gps_status = {
                'satellites': gps_data['satellites'],
                'fix_quality': gps_data['fix_quality'],
                'has_fix': gps_data['has_fix'],
                'acquiring_fix': acquiring_fix,
                'altitude': gps_data['altitude'],
                'status': 'fix_acquired' if gps_data['has_fix'] else ('acquiring' if acquiring_fix else 'inactive')
            }
        
        # Increment sequence number only if requested
        if increment_sequence:
            self.telemetry_sequence += 1
        
        telemetry = {
            'timestamp': time.time(),
            'sequence': self.telemetry_sequence,
            'position': {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'source': position_source  # Add source information to position data
            },
            'navigation': {
                'heading': self.heading,
                'speed': self.speed,
            },
            'status': {
                'battery': self.battery,
                'gps': gps_status
            }
        }
        
        # Convert any Decimal values to float before returning
        return self._convert_decimal_values(telemetry)
    
    def increment_sequence(self):
        """
        Explicitly increment the sequence number.
        This should be called after successfully sending telemetry data.
        """
        self.telemetry_sequence += 1
        return self.telemetry_sequence
    
    def generate_server_telemetry_data(self, increment_sequence=True):
        """
        Generate telemetry data in the format expected by the server.
        This restructures the data from generate_telemetry_data() to match
        the server's expected format.
        
        Parameters:
            increment_sequence (bool): Whether to increment the sequence number.
                                      Defaults to True for backward compatibility.
        """
        # Get telemetry data without incrementing sequence here
        # We'll handle sequence incrementation separately
        telemetry = self.generate_telemetry_data(increment_sequence=False)
        
        # Increment sequence if requested (default to True for backward compatibility)
        if increment_sequence:
            self.telemetry_sequence += 1
            telemetry['sequence'] = self.telemetry_sequence
        
        # Transform into server format
        server_telemetry = {
            'type': 'telemetry',
            'subtype': 'sensor_data',
            'sequence': telemetry['sequence'],
            'timestamp': telemetry['timestamp'],
            'data': {
                'gps': {
                    'latitude': telemetry['position']['latitude'],
                    'longitude': telemetry['position']['longitude']
                },
                'heading': telemetry['navigation']['heading'],
                'speed': telemetry['navigation']['speed'],
                'battery': telemetry['status']['battery']
            }
        }
        
        return server_telemetry
    
    def get_current_status(self):
        """Get the current status of the boat as a dict."""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'heading': self.heading,
            'speed': self.speed,
            'battery': self.battery
        }
    
    def shutdown(self):
        """Cleanup resources when shutting down."""
        if self.use_gps and self.gps:
            self.gps.stop()
            logger.info("GPS handler stopped") 