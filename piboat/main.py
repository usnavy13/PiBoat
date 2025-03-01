import asyncio
import sys
import os
import signal

from piboat.config import DEVICE_ID, WS_SERVER_URL
from piboat.device.device import BoatDevice
from piboat.utils.logging_setup import setup_logging, log_library_versions

# Set up logging
logger = setup_logging("BoatDevice", "boat_device.log")

# Log library versions for debugging
log_library_versions(logger)

# Signal handler for graceful shutdown
shutdown_event = asyncio.Event()

def signal_handler():
    logger.info("Shutdown signal received")
    shutdown_event.set()

async def main():
    # Create and run the boat device
    device = BoatDevice(
        device_id=DEVICE_ID,
        server_url=WS_SERVER_URL
    )
    
    logger.info(f"Starting boat device: {DEVICE_ID}")
    logger.info(f"WebSocket server: {WS_SERVER_URL.format(device_id=DEVICE_ID)}")
    
    # Create the device task
    device_task = asyncio.create_task(device.run())
    
    # Wait for shutdown event or device task completion
    done, pending = await asyncio.wait(
        [device_task, shutdown_event.wait()], 
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Cancel remaining tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    logger.info("Device stopped")

if __name__ == "__main__":
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda sig, frame: signal_handler())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Device stopped by user")
    except Exception as e:
        logger.error(f"Error running device: {str(e)}")
        sys.exit(1) 