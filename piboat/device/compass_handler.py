import smbus2 as smbus
import math
import time
import logging
import threading

logger = logging.getLogger("CompassHandler")

# BMM150 address and register definitions
BMM150_ADDR = 0x13
BMM150_CHIP_ID_REG = 0x40
BMM150_DATA_X_LSB = 0x42
BMM150_DATA_X_MSB = 0x43
BMM150_DATA_Y_LSB = 0x44
BMM150_DATA_Y_MSB = 0x45
BMM150_DATA_Z_LSB = 0x46
BMM150_DATA_Z_MSB = 0x47
BMM150_POWER_CONTROL_REG = 0x4B
BMM150_OP_MODE_REG = 0x4C
BMM150_CHIP_ID = 0x32

class CompassHandler:
    """
    Handles reading and parsing data from a BMM150 compass sensor.
    This class reads magnetometer data from an I2C bus and calculates
    the magnetic heading.
    """
    def __init__(self, bus_num=1):
        self.bus_num = bus_num
        self.bus = None
        self.heading = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.connected = False
        self.running = False
        self.thread = None
        self.hard_iron_offset_x = 0  # Calibration offsets
        self.hard_iron_offset_y = 0
        self.declination = 0  # Magnetic declination for true north correction

    def start(self):
        """
        Initialize and start the compass sensor.
        Returns True if successful, False otherwise.
        """
        try:
            # Initialize I2C bus
            self.bus = smbus.SMBus(self.bus_num)
            
            # Check chip ID - with retry logic to handle potential I2C instability
            retry_count = 0
            max_retries = 3
            chip_id = None
            
            while retry_count < max_retries:
                try:
                    chip_id = self.bus.read_byte_data(BMM150_ADDR, BMM150_CHIP_ID_REG)
                    logger.info(f"Read chip ID: {chip_id:#x} (attempt {retry_count+1})")
                    break
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Failed to read chip ID (attempt {retry_count}): {str(e)}")
                    time.sleep(0.5)  # Wait before retry
            
            # If we couldn't read the chip ID after all retries, fail
            if chip_id is None:
                logger.error("Failed to read BMM150 chip ID after multiple attempts")
                return False
                
            # Accept either 0x32 (standard) or 0x00 (variant) 
            if chip_id != 0x32 and chip_id != 0x00:
                logger.warning(f"Unexpected BMM150 chip ID: {chip_id:#x}, expected either 0x32 or 0x00")
                return False
            
            logger.info(f"BMM150 compass found with chip ID: {chip_id:#x}")
            
            # Power up the sensor
            self.bus.write_byte_data(BMM150_ADDR, BMM150_POWER_CONTROL_REG, 0x01)
            time.sleep(0.1)
            
            # Set normal mode
            self.bus.write_byte_data(BMM150_ADDR, BMM150_OP_MODE_REG, 0x00)
            time.sleep(0.1)
            
            self.connected = True
            
            # Start reading thread
            self.running = True
            self.thread = threading.Thread(target=self._read_compass_data)
            self.thread.daemon = True
            self.thread.start()
            
            logger.info("Compass handler started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize compass: {str(e)}")
            self.connected = False
            return False
    
    def stop(self):
        """Stop the compass data reading thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        if self.bus and self.connected:
            try:
                # Put sensor to sleep mode
                self.bus.write_byte_data(BMM150_ADDR, BMM150_POWER_CONTROL_REG, 0x00)
            except Exception as e:
                logger.error(f"Error putting compass to sleep: {str(e)}")
        
        logger.info("Compass handler stopped")
    
    def _twos_complement(self, val, bits):
        """Convert two's complement value."""
        if (val & (1 << (bits - 1))) != 0:
            val = val - (1 << bits)
        return val
    
    def _read_compass_data(self):
        """Thread function to continuously read compass data."""
        last_chip_id_check = 0
        chip_id_check_interval = 60  # Check chip ID every 60 seconds
        
        while self.running:
            try:
                if not self.connected:
                    time.sleep(1)
                    continue
                
                # Periodically verify chip ID to detect if it changes
                current_time = time.time()
                if current_time - last_chip_id_check > chip_id_check_interval:
                    try:
                        chip_id = self.bus.read_byte_data(BMM150_ADDR, BMM150_CHIP_ID_REG)
                        logger.debug(f"Periodic chip ID check: {chip_id:#x}")
                        if chip_id != 0x32 and chip_id != 0x00:
                            logger.warning(f"Chip ID changed during operation to {chip_id:#x}")
                    except Exception as e:
                        logger.warning(f"Failed to check chip ID during operation: {str(e)}")
                    
                    last_chip_id_check = current_time
                
                # Read the raw data
                x_lsb = self.bus.read_byte_data(BMM150_ADDR, BMM150_DATA_X_LSB)
                x_msb = self.bus.read_byte_data(BMM150_ADDR, BMM150_DATA_X_MSB)
                y_lsb = self.bus.read_byte_data(BMM150_ADDR, BMM150_DATA_Y_LSB)
                y_msb = self.bus.read_byte_data(BMM150_ADDR, BMM150_DATA_Y_MSB)
                z_lsb = self.bus.read_byte_data(BMM150_ADDR, BMM150_DATA_Z_LSB)
                z_msb = self.bus.read_byte_data(BMM150_ADDR, BMM150_DATA_Z_MSB)
                
                # Convert to 16-bit values
                x_raw = (x_msb << 8) | x_lsb
                y_raw = (y_msb << 8) | y_lsb
                z_raw = (z_msb << 8) | z_lsb
                
                # Apply two's complement
                x = self._twos_complement(x_raw >> 3, 13)
                y = self._twos_complement(y_raw >> 3, 13)
                z = self._twos_complement(z_raw >> 1, 15)
                
                # Apply hard iron calibration
                x -= self.hard_iron_offset_x
                y -= self.hard_iron_offset_y
                
                # Store values
                self.x = x
                self.y = y
                self.z = z
                
                # Calculate heading (degrees)
                heading = math.atan2(y, x) * 180.0 / math.pi
                
                # Apply magnetic declination to get true north
                heading += self.declination
                
                # Normalize to 0-360
                heading = (heading + 360) % 360
                
                # Update class attribute with new heading
                self.heading = heading
                
                # Don't read too frequently to avoid I2C bus congestion
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error reading compass data: {str(e)}")
                time.sleep(1)
    
    def get_heading(self):
        """Return the current heading in degrees (0-360)."""
        return self.heading
    
    def get_compass_data(self):
        """Return a dictionary with all compass data."""
        return {
            'heading': self.heading,
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'connected': self.connected
        }
    
    def set_calibration(self, offset_x=0, offset_y=0, declination=0):
        """
        Set calibration parameters for the compass.
        
        Args:
            offset_x: Hard iron calibration offset for X axis
            offset_y: Hard iron calibration offset for Y axis
            declination: Magnetic declination angle (difference between magnetic and true north)
        """
        self.hard_iron_offset_x = offset_x
        self.hard_iron_offset_y = offset_y
        self.declination = declination
        logger.info(f"Compass calibration set: offsets X={offset_x}, Y={offset_y}, declination={declination}°") 