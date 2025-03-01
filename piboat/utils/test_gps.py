#!/usr/bin/env python3
"""
Simple script to test the GPS functionality.
This script will initialize the GPS handler and print out GPS data for a specified duration.
"""

import time
import logging
import argparse
import sys
from piboat.device.gps_handler import GPSHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    parser = argparse.ArgumentParser(description='Test GPS functionality')
    parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port for GPS device')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for serial connection')
    parser.add_argument('--duration', type=int, default=300, help='Test duration in seconds (default: 5 minutes)')
    parser.add_argument('--init-wait', type=int, default=30, help='Initial GPS wait time in seconds (default: 30s)')
    args = parser.parse_args()
    
    logger = logging.getLogger('GPSTest')
    logger.info(f"Starting GPS test on port {args.port} for {args.duration} seconds")
    
    # Initialize GPS handler
    gps = GPSHandler(port=args.port, baudrate=args.baudrate)
    
    try:
        # Start the GPS handler
        gps.start()
        
        # Wait for GPS to initialize
        logger.info(f"Waiting {args.init_wait} seconds for GPS to initialize...")
        time.sleep(args.init_wait)
        
        # Loop and print data for the specified duration
        start_time = time.time()
        last_fix_status = None
        fix_achieved_time = None
        
        while time.time() - start_time < args.duration:
            gps_data = gps.get_gps_data()
            
            # Check if fix status has changed
            current_fix = gps_data['has_fix']
            if current_fix != last_fix_status:
                if current_fix:
                    fix_achieved_time = time.time()
                    logger.info(f"GPS FIX ACQUIRED after {int(fix_achieved_time - start_time)} seconds!")
                last_fix_status = current_fix
            
            # Print GPS data status
            logger.info("GPS Data:")
            
            # Display GPS status
            status = "Acquiring fix..." if gps_data['running'] and not gps_data['has_fix'] else "Fix Acquired" if gps_data['has_fix'] else "Inactive"
            logger.info(f"  Status: {status}")
            logger.info(f"  Fix: {'Yes' if gps_data['has_fix'] else 'No'}")
            
            if gps_data['has_fix']:
                # We have a fix, show time since first fix
                elapsed_since_fix = int(time.time() - fix_achieved_time) if fix_achieved_time else 0
                logger.info(f"  Fix duration: {elapsed_since_fix} seconds")
            
            logger.info(f"  Position: {gps_data['latitude']}, {gps_data['longitude']}")
            logger.info(f"  Altitude: {gps_data['altitude']} m")
            logger.info(f"  Speed: {gps_data['speed_knots']} knots")
            logger.info(f"  Course: {gps_data['course']} degrees")
            logger.info(f"  Satellites: {gps_data['satellites']}")
            logger.info(f"  Fix Quality: {gps_data['fix_quality']}")
            logger.info(f"  Timestamp: {gps_data['timestamp']}")
            
            # Calculate and show elapsed time
            elapsed = int(time.time() - start_time)
            remaining = args.duration - elapsed
            logger.info(f"  Test progress: {elapsed}s elapsed, {remaining}s remaining")
            logger.info("-------------------")
            
            # Wait before next update
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during GPS test: {str(e)}")
    finally:
        # Clean up
        gps.stop()
        logger.info("GPS test completed")

if __name__ == "__main__":
    main() 