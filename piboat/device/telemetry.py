import random
import math
import time
import logging
import decimal  # Add import for decimal module
from piboat.device.gps_handler import GPSHandler
from piboat.device.compass_handler import CompassHandler

logger = logging.getLogger("Telemetry")

class TelemetryGenerator:
    """
    Generates telemetry data for the boat using real GPS data.
    """
    def __init__(self, gps_port='/dev/ttyACM0', motor_controller=None):
        # Set initial position to None until we get a valid GPS fix
        self.latitude = None
        self.longitude = None
        self.heading = None
        self.speed = 0
        self.battery = 100  # Battery percentage
        self.last_position_update = 0  # Timestamp of last position update
        
        # Store previous position for calculating speed and heading
        self.prev_latitude = None
        self.prev_longitude = None
        self.prev_position_timestamp = 0
        
        # For sequence numbering
        self.telemetry_sequence = 0
        
        # Store reference to motor controller
        self.motor_controller = motor_controller
        
        # Initialize GPS - always required
        self.gps = self._init_gps(gps_port)
        
        # Initialize compass - always required for heading data
        self.compass = self._init_compass()
        if self.compass is None:
            logger.warning("Compass initialization failed. Heading data will not be available!")
        
        logger.info("Initialized telemetry generator with real GPS data")
    
    def _init_gps(self, port):
        """Initialize the GPS handler."""
        try:
            self.gps = GPSHandler(port=port)
            self.gps.start()
            logger.info(f"GPS handler started on port {port}")
            return self.gps
        except Exception as e:
            logger.error(f"Failed to initialize GPS: {str(e)}")
            logger.error(f"Real telemetry data unavailable until GPS is working")
            return None
    
    def _init_compass(self):
        """Initialize the compass handler."""
        try:
            compass = CompassHandler()
            success = compass.start()
            if success:
                logger.info("Compass initialized successfully")
                # You can set calibration if needed
                # compass.set_calibration(offset_x=0, offset_y=0, declination=0)
                return compass
            else:
                logger.error("Failed to initialize compass. No heading data will be available!")
                return None
        except Exception as e:
            logger.error(f"Error initializing compass: {str(e)}")
            return None
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the distance between two coordinates using the Haversine formula.
        Returns distance in meters.
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Earth radius in meters
        earth_radius = 6371000
        distance = earth_radius * c
        
        return distance
    
    def _calculate_heading(self, lat1, lon1, lat2, lon2):
        """
        Calculate the heading (course) from point 1 to point 2.
        Returns heading in degrees (0-360).
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Calculate heading
        dlon = lon2_rad - lon1_rad
        y = math.sin(dlon) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        heading_rad = math.atan2(y, x)
        
        # Convert to degrees and normalize to 0-360
        heading_deg = math.degrees(heading_rad)
        heading_deg = (heading_deg + 360) % 360
        
        return heading_deg
    
    def update_position(self):
        """
        Update the boat position based on GPS data if available.
        Keeps the last known position if no new GPS data is available.
        Uses ONLY GPS data for speed.
        Uses ONLY compass for heading, never GPS.
        """
        # Update compass heading if available
        if self.compass and self.compass.connected:
            compass_heading = self.compass.get_heading()
            
            if self.heading is None:
                self.heading = compass_heading
                logger.debug(f"Initial compass heading: {self.heading:.1f}°")
            else:
                # Apply smoothing to compass heading
                alpha = 0.3  # Smoothing factor (0-1)
                
                # Special handling for crossing 0/360 boundary
                if abs(compass_heading - self.heading) > 180:
                    if compass_heading > self.heading:
                        self.heading += 360
                    else:
                        compass_heading += 360
                        
                self.heading = (alpha * compass_heading) + ((1 - alpha) * self.heading)
                self.heading = self.heading % 360
                
                logger.debug(f"Updated compass heading: {self.heading:.1f}°")
        
        # Update GPS position and speed
        if self.gps:
            gps_data = self.gps.get_gps_data()
            current_time = time.time()
            
            # Update position if we have valid GPS data
            if gps_data['has_fix'] and gps_data['latitude'] is not None and gps_data['longitude'] is not None:
                # Update current position
                self.latitude = gps_data['latitude']
                self.longitude = gps_data['longitude']
                self.last_position_update = current_time
                
                # Use GPS speed_knots value directly
                if gps_data['speed_knots'] is not None:
                    # Apply some smoothing to avoid jumps
                    alpha = 0.3  # Smoothing factor (0-1)
                    self.speed = (alpha * gps_data['speed_knots']) + ((1 - alpha) * self.speed)
                    logger.debug(f"Updated speed from GPS: {self.speed:.2f} knots")
                
                logger.debug(f"Updated GPS position: {self.latitude:.6f}, {self.longitude:.6f}")
            else:
                logger.debug("No valid GPS position available")
        else:
            logger.warning("GPS handler not initialized, position data unavailable")
        
        # Battery drain - keep this as real battery monitoring will be added later
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
        elif hasattr(data, 'isoformat'):  # Handle datetime, date, and time objects
            # Convert datetime/time objects to ISO format strings
            return data.isoformat()
        elif isinstance(data, time.struct_time):
            # Convert struct_time to ISO format
            return time.strftime("%Y-%m-%dT%H:%M:%S", data)
        else:
            return data
    
    def generate_telemetry_data(self, increment_sequence=False):
        """Generate telemetry data for the boat from real GPS data."""
        # First update the position
        self.update_position()
        
        # Get GPS status
        gps_status = {}
        position_source = "unknown"  # Default when no position available
        
        if self.gps:
            gps_data = self.gps.get_gps_data()
            
            # Add acquiring_fix status
            # We are acquiring a fix if GPS is active but doesn't have a fix yet
            acquiring_fix = gps_data['running'] and not gps_data['has_fix']
            
            # Set position source based on GPS fix
            if gps_data['has_fix']:
                position_source = "gps"
                
            # Include all GPS values in the status
            gps_status = {
                'satellites': gps_data['satellites'],
                'fix_quality': gps_data['fix_quality'],
                'has_fix': gps_data['has_fix'],
                'acquiring_fix': acquiring_fix,
                'altitude': gps_data['altitude'],
                'speed_knots': gps_data['speed_knots'],
                'course': gps_data['course'],
                'gps_timestamp': gps_data['timestamp'],
                'running': gps_data['running'],
                'status': 'fix_acquired' if gps_data['has_fix'] else ('acquiring' if acquiring_fix else 'inactive')
            }
        
        # Get motor control status if available
        motor_status = {}
        if self.motor_controller and hasattr(self.motor_controller, 'get_motor_status'):
            motor_status = self.motor_controller.get_motor_status()
        
        # Increment sequence number only if requested
        if increment_sequence:
            self.telemetry_sequence += 1
        
        # Use float timestamp for JSON compatibility
        current_timestamp = time.time()
        
        telemetry = {
            'timestamp': current_timestamp,
            'sequence': self.telemetry_sequence,
            'position': {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'source': position_source
            },
            'navigation': {
                'heading': self.heading,
                'speed': self.speed,
                'rudder_position': motor_status.get('rudder_position', 0),
                'throttle': motor_status.get('throttle', 0)
            },
            'status': {
                'battery': self.battery,
                'gps': gps_status,
                'motors': motor_status
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
                    'longitude': telemetry['position']['longitude'],
                    'source': telemetry['position']['source'],
                    'status': telemetry['status']['gps'].get('status', 'unknown'),
                    'satellites': telemetry['status']['gps'].get('satellites', None),
                    'fix_quality': telemetry['status']['gps'].get('fix_quality', None),
                    'has_fix': telemetry['status']['gps'].get('has_fix', False),
                    'acquiring_fix': telemetry['status']['gps'].get('acquiring_fix', False),
                    'altitude': telemetry['status']['gps'].get('altitude', None),
                    'speed_knots': telemetry['status']['gps'].get('speed_knots', None),
                    'course': telemetry['status']['gps'].get('course', None),
                    'gps_timestamp': telemetry['status']['gps'].get('gps_timestamp', None),
                    'running': telemetry['status']['gps'].get('running', False)
                },
                'heading': telemetry['navigation']['heading'],
                'speed': telemetry['navigation']['speed'],
                'battery': telemetry['status']['battery'],
                'rudder_position': telemetry['navigation']['rudder_position'],
                'throttle': telemetry['navigation']['throttle']
            }
        }
        
        return server_telemetry
    
    def get_current_status(self):
        """Get the current status of the boat as a dict."""
        # Get motor status if available
        rudder_position = 0
        throttle = 0
        if self.motor_controller and hasattr(self.motor_controller, 'get_motor_status'):
            motor_status = self.motor_controller.get_motor_status()
            rudder_position = motor_status.get('rudder_position', 0)
            throttle = motor_status.get('throttle', 0)
            
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'heading': self.heading,
            'speed': self.speed,
            'battery': self.battery,
            'rudder_position': rudder_position,
            'throttle': throttle
        }
    
    def shutdown(self):
        """Clean up resources before shutting down."""
        if self.gps:
            self.gps.stop()
            logger.info("GPS handler stopped")
            
        if self.compass:
            self.compass.stop()
            logger.info("Compass handler stopped")
    
    def set_motor_controller(self, motor_controller):
        """
        Set the motor controller after TelemetryGenerator has been initialized.
        This allows an existing motor controller to be shared with the telemetry system.
        
        Args:
            motor_controller: The MotorController instance to use for telemetry
        """
        self.motor_controller = motor_controller
        logger.info("Motor controller attached to telemetry system")
        return True 