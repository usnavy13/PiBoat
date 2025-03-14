#!/usr/bin/env python

import os
import sys
import asyncio
import signal
import atexit

# Global variable to hold the device reference for cleanup during signal handling
boat_device = None

# Function to perform direct emergency motor stop
def emergency_motor_stop():
    """Direct emergency motor stop function"""
    global boat_device
    try:
        if boat_device and hasattr(boat_device, 'command_handler') and hasattr(boat_device.command_handler, 'motor_controller'):
            print("Performing direct emergency motor stop")
            boat_device.command_handler.motor_controller.cleanup()
    except Exception as e:
        print(f"Failed direct emergency motor stop: {str(e)}")

# Register the emergency motor stop as an exit handler
atexit.register(emergency_motor_stop)

async def run_device():
    """Run the boat device directly."""
    global boat_device
    
    # Import only after path is setup in main()
    from piboat.config import DEVICE_ID, WS_SERVER_URL
    from piboat.device.device import BoatDevice
    
    # Create the boat device with compass enabled
    boat_device = BoatDevice(
        device_id=DEVICE_ID,
        server_url=WS_SERVER_URL
    )
    
    try:
        # Run the device and wait for it to complete
        await boat_device.run()
    finally:
        # Make sure we clean up properly even if an exception occurs
        if boat_device:
            await boat_device.shutdown()

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) and SIGTERM signals"""
    print("\nReceived shutdown signal. Stopping boat device...")
    
    # Emergency motor stop in case the normal shutdown fails
    try:
        if boat_device and hasattr(boat_device, 'command_handler') and hasattr(boat_device.command_handler, 'motor_controller'):
            print("Performing emergency motor stop")
            boat_device.command_handler.motor_controller.cleanup()
    except Exception as e:
        print(f"Failed emergency motor stop in signal handler: {str(e)}")
    
    # Exit the program to trigger the finally blocks
    sys.exit(0)

def main():
    """Run the main coroutine."""
    # Add the current directory to the path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import after path setup
    from piboat.utils.logging_setup import setup_logging
    
    # Set up logging for the runner
    logger = setup_logging("BoatRunner", "boat_device.log")
    
    logger.info("Starting boat device with compass enabled")
    
    # Set up signal handlers for proper cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Use asyncio.run to properly handle the coroutine
        asyncio.run(run_device())
    except KeyboardInterrupt:
        logger.info("Keyboard interruption detected, shutting down gracefully...")
    except Exception as e:
        logger.error(f"Error running device: {str(e)}")
    finally:
        logger.info("Boat device runner stopped")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Device stopped by user")
    except Exception as e:
        print(f"Error running device: {str(e)}")
        sys.exit(1) 