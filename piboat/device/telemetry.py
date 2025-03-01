import random
import math
import time
import logging
import decimal  # Add import for decimal module
from piboat.device.gps_handler import GPSHandler

logger = logging.getLogger("Telemetry")

class TelemetryGenerator:
    """
    Generates telemetry data for the boat using real GPS data.
    """
    def __init__(self, use_gps=True, gps_port='/dev/ttyACM0'):
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
        
        # GPS integration - always enabled
        self.use_gps = True  # Force GPS usage to true regardless of parameter
        self.gps = None
        
        # Initialize GPS
        self._init_gps(gps_port)
        
        logger.info(f"Initialized telemetry generator with real GPS data")
    
    def _init_gps(self, port):
        """Initialize the GPS handler."""
        try:
            self.gps = GPSHandler(port=port)
            self.gps.start()
            logger.info(f"GPS handler started on port {port}")
        except Exception as e:
            logger.error(f"Failed to initialize GPS: {str(e)}")
            logger.error(f"Real telemetry data unavailable until GPS is working")
    
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
        Also calculates speed and heading based on position changes.
        """
        if self.gps:
            gps_data = self.gps.get_gps_data()
            current_time = time.time()
            
            # Update position if we have valid GPS data
            if gps_data['has_fix'] and gps_data['latitude'] is not None and gps_data['longitude'] is not None:
                # Store previous position before updating to new one
                if self.latitude is not None and self.longitude is not None:
                    self.prev_latitude = self.latitude
                    self.prev_longitude = self.longitude
                    self.prev_position_timestamp = self.last_position_update
                
                # Update current position
                self.latitude = gps_data['latitude']
                self.longitude = gps_data['longitude']
                self.last_position_update = current_time
                
                # Calculate speed and heading if we have previous position
                if self.prev_latitude is not None and self.prev_longitude is not None:
                    # Time elapsed in seconds
                    time_elapsed = current_time - self.prev_position_timestamp
                    
                    if time_elapsed > 0:
                        # Calculate distance in meters
                        distance = self._calculate_distance(
                            self.prev_latitude, self.prev_longitude,
                            self.latitude, self.longitude
                        )
                        
                        # Calculate speed in meters per second, then convert to knots
                        # 1 meter/second = 1.94384 knots
                        speed_mps = distance / time_elapsed
                        speed_knots = speed_mps * 1.94384
                        
                        # Apply some smoothing to avoid jumps
                        alpha = 0.3  # Smoothing factor (0-1)
                        self.speed = (alpha * speed_knots) + ((1 - alpha) * self.speed)
                        
                        # Calculate heading only if we moved a meaningful distance
                        if distance > 1.0:  # More than 1 meter of movement
                            new_heading = self._calculate_heading(
                                self.prev_latitude, self.prev_longitude,
                                self.latitude, self.longitude
                            )
                            
                            # Apply smoothing to heading as well
                            if self.heading is None:
                                self.heading = new_heading
                            else:
                                # Special handling for crossing 0/360 boundary
                                if abs(new_heading - self.heading) > 180:
                                    if new_heading > self.heading:
                                        self.heading += 360
                                    else:
                                        new_heading += 360
                                        
                                self.heading = (alpha * new_heading) + ((1 - alpha) * self.heading)
                                self.heading = self.heading % 360
                
                logger.debug(f"Updated position from GPS: {self.latitude}, {self.longitude}")
                logger.debug(f"Calculated speed: {self.speed:.2f} knots, heading: {self.heading:.1f}°")
                
            elif time.time() - self.last_position_update > 60:  # Log a warning if no position update for 60 seconds
                logger.warning(f"No GPS fix received for {int(time.time() - self.last_position_update)} seconds")
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
                'source': position_source
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
                    'longitude': telemetry['position']['longitude'],
                    'source': telemetry['position']['source'],
                    'status': telemetry['status']['gps'].get('status', 'unknown'),
                    'satellites': telemetry['status']['gps'].get('satellites', None),
                    'fix_quality': telemetry['status']['gps'].get('fix_quality', None),
                    'has_fix': telemetry['status']['gps'].get('has_fix', False),
                    'acquiring_fix': telemetry['status']['gps'].get('acquiring_fix', False),
                    'altitude': telemetry['status']['gps'].get('altitude', None)
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
        if self.gps:
            self.gps.stop()
            logger.info("GPS handler stopped") 