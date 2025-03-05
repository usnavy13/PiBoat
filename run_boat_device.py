#!/usr/bin/env python

import os
import sys
import asyncio

async def run_device():
    """Run the boat device directly."""
    # Import only after path is setup in main()
    from piboat.config import DEVICE_ID, WS_SERVER_URL
    from piboat.device.device import BoatDevice
    
    # Create the boat device with compass enabled
    device = BoatDevice(
        device_id=DEVICE_ID,
        server_url=WS_SERVER_URL
    )
    
    # Run the device and wait for it to complete
    await device.run()

def main():
    """Run the main coroutine."""
    # Add the current directory to the path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import after path setup
    from piboat.utils.logging_setup import setup_logging
    
    # Set up logging for the runner
    logger = setup_logging("BoatRunner", "boat_device.log")
    
    logger.info("Starting boat device with compass enabled")
    
    try:
        # Use asyncio.run to properly handle the coroutine
        asyncio.run(run_device())
    except Exception as e:
        logger.error(f"Error running device: {str(e)}")
        sys.exit(1)
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