#!/usr/bin/env python

import os
import sys
import asyncio
import signal

async def shutdown_handler(signal_event):
    """Handle shutdown signals by waiting for the event to be set."""
    await signal_event.wait()

def main_with_signals():
    """Set up signal handlers and run the main coroutine properly."""
    # Add the current directory to the path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import after path setup
    from piboat.main import main
    
    # Create shutdown event
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    signal_event = asyncio.Event()
    
    # Set up signal handlers properly for asyncio
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_event.set())
    
    # Run main and shutdown handler concurrently
    try:
        main_task = loop.create_task(main())
        shutdown_task = loop.create_task(shutdown_handler(signal_event))
        
        # Wait for either main to complete or shutdown to be triggered
        loop.run_until_complete(asyncio.gather(
            main_task, 
            shutdown_task,
            return_exceptions=True
        ))
    except Exception as e:
        print(f"Error running simulation: {str(e)}")
        sys.exit(1)
    finally:
        loop.close()

if __name__ == "__main__":
    try:
        main_with_signals()
    except KeyboardInterrupt:
        print("Simulation stopped by user")
    except Exception as e:
        print(f"Error running simulation: {str(e)}")
        sys.exit(1) 