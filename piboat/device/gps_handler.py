import serial
import pynmea2
import logging
import time
import threading
import decimal  # Add import for decimal module
from datetime import datetime

logger = logging.getLogger("GPSHandler")

class GPSHandler:
    """
    Handles reading and parsing data from a USB GPS device.
    This class reads NMEA sentences from a serial port and extracts
    GPS position and other navigation data.
    """
    def __init__(self, port='/dev/ttyACM0', baudrate=9600, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.running = False
        self.thread = None
        
        # GPS data
        self.latitude = None
        self.longitude = None
        self.altitude = None
        self.speed_knots = None
        self.course = None  # Heading/course in degrees
        self.satellites = None
        self.timestamp = None
        self.fix_quality = None
        
        # Lock for thread safety when accessing GPS data
        self.lock = threading.Lock()
        
        logger.info(f"Initialized GPS handler for port {self.port}")
    
    def start(self):
        """Start reading GPS data in a background thread."""
        if self.thread and self.thread.is_alive():
            logger.warning("GPS handler already running")
            return
            
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            logger.info(f"Connected to GPS device on {self.port}")
            
            self.running = True
            self.thread = threading.Thread(target=self._read_gps_data)
            self.thread.daemon = True
            self.thread.start()
            logger.info("GPS handler thread started")
            
        except Exception as e:
            logger.error(f"Failed to connect to GPS device: {str(e)}")
            self.running = False
            if self.serial_conn:
                self.serial_conn.close()
                self.serial_conn = None
    
    def stop(self):
        """Stop reading GPS data."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        
        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None
        logger.info("GPS handler stopped")
    
    def _read_gps_data(self):
        """Background thread to continuously read and parse GPS data."""
        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    logger.error("Serial connection closed. Attempting to reconnect...")
                    time.sleep(5)
                    self.start()
                    continue
                
                line = self.serial_conn.readline().decode('ascii', errors='replace').strip()
                if not line:
                    continue
                    
                # Try to parse the NMEA sentence
                try:
                    msg = pynmea2.parse(line)
                    self._process_nmea_message(msg)
                except pynmea2.ParseError:
                    # Skip invalid sentences
                    continue
                    
            except Exception as e:
                logger.error(f"Error reading GPS data: {str(e)}")
                time.sleep(1)
    
    def _process_nmea_message(self, msg):
        """Process different types of NMEA messages."""
        with self.lock:
            try:
                if hasattr(msg, 'timestamp'):
                    self.timestamp = msg.timestamp
                
                # GGA message - Fix data
                if isinstance(msg, pynmea2.GGA):
                    if msg.latitude and msg.longitude:
                        self.latitude = msg.latitude
                        self.longitude = msg.longitude
                    if hasattr(msg, 'altitude'):
                        self.altitude = msg.altitude
                    if hasattr(msg, 'num_sats'):
                        self.satellites = msg.num_sats
                    if hasattr(msg, 'gps_qual'):
                        self.fix_quality = msg.gps_qual
                
                # RMC message - Recommended minimum navigation information
                elif isinstance(msg, pynmea2.RMC):
                    if msg.latitude and msg.longitude:
                        self.latitude = msg.latitude
                        self.longitude = msg.longitude
                    if hasattr(msg, 'spd_over_grnd'):
                        self.speed_knots = msg.spd_over_grnd
                    if hasattr(msg, 'true_course'):
                        self.course = msg.true_course
                
                # VTG message - Track made good and ground speed
                elif isinstance(msg, pynmea2.VTG):
                    if hasattr(msg, 'spd_over_grnd_kts'):
                        self.speed_knots = msg.spd_over_grnd_kts
                    if hasattr(msg, 'true_track'):
                        self.course = msg.true_track
                
                # GSA message - GPS DOP and active satellites
                elif isinstance(msg, pynmea2.GSA):
                    pass  # Add any GSA specific processing if needed
                
            except Exception as e:
                logger.error(f"Error processing NMEA message: {str(e)}")
    
    def _convert_decimal(self, value):
        """Convert Decimal to float if needed."""
        if isinstance(value, decimal.Decimal):
            return float(value)
        return value
    
    def get_gps_data(self):
        """
        Get the current GPS data.
        Returns a dictionary with the latest GPS information.
        """
        with self.lock:
            return {
                'latitude': self._convert_decimal(self.latitude),
                'longitude': self._convert_decimal(self.longitude),
                'altitude': self._convert_decimal(self.altitude),
                'speed_knots': self._convert_decimal(self.speed_knots),
                'course': self._convert_decimal(self.course),
                'satellites': self.satellites,
                'timestamp': self.timestamp,
                'fix_quality': self.fix_quality,
                'has_fix': self.fix_quality is not None and int(self.fix_quality) > 0,
                'running': self.running
            }

    def has_fix(self):
        """
        Check if the GPS has a fix.
        Returns True if the GPS has a valid fix, False otherwise.
        """
        with self.lock:
            return self.fix_quality is not None and int(self.fix_quality) > 0 