#!/usr/bin/env python3
"""
Webcam Connection Test Script for PiBoat
This script tests webcam connectivity using the same logic as the WebRTC system.
"""
import os
import sys
import logging
import time

# Add the current directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WebcamTest")

def main():
    """Test webcam connectivity using our utility functions."""
    try:
        # Import our webcam utilities
        from piboat.webrtc.webcam_utils import WebcamDetector, get_best_webcam_device
        from piboat.config import VIDEO_WIDTH, VIDEO_HEIGHT
        
        # Display configuration
        logger.info(f"Target resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        
        # List all available video devices
        devices = WebcamDetector.list_v4l_devices()
        logger.info(f"Found {len(devices)} video devices: {devices}")
        
        # Test each device but stop after finding the first working one
        logger.info("Testing devices (will stop after finding first working device)...")
        working_devices = WebcamDetector.find_working_devices(stop_after_first=True, start_with_device=0)
        logger.info(f"Working devices: {working_devices}")
        
        if not working_devices:
            logger.error("No working webcam devices found!")
            logger.info("Possible solutions:")
            logger.info("1. Check if the webcam is properly connected")
            logger.info("2. Verify webcam permissions (try: ls -la /dev/video*)")
            logger.info("3. Try rebooting the system")
            sys.exit(1)
        
        # Find the best device for our configuration
        device_id, width, height = WebcamDetector.find_best_device(VIDEO_WIDTH, VIDEO_HEIGHT, stop_after_first=True)
        if device_id is not None:
            logger.info(f"Best device for {VIDEO_WIDTH}x{VIDEO_HEIGHT}: Device {device_id} ({width}x{height})")
        else:
            logger.error(f"No suitable device found for {VIDEO_WIDTH}x{VIDEO_HEIGHT} resolution!")
            sys.exit(1)
        
        # Test that our get_best_webcam_device utility works
        best_device = get_best_webcam_device(VIDEO_WIDTH, VIDEO_HEIGHT)
        logger.info(f"Best device ID from utility function: {best_device}")
        
        # Try to capture frames for 5 seconds to verify continuous operation
        logger.info(f"Attempting to capture frames from device {best_device} for 5 seconds...")
        
        import cv2
        cap = cv2.VideoCapture(best_device)
        
        if not cap.isOpened():
            logger.error(f"Failed to open device {best_device}!")
            sys.exit(1)
            
        # Set properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
        
        # Get actual properties
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Webcam properties: {actual_width}x{actual_height} at {actual_fps} FPS")
        
        # Try to capture frames for 5 seconds
        start_time = time.time()
        frames_captured = 0
        
        try:
            while time.time() - start_time < 5:
                ret, frame = cap.read()
                
                if not ret:
                    logger.error("Failed to capture frame!")
                    break
                    
                frames_captured += 1
                
                if frames_captured % 10 == 0:
                    logger.info(f"Captured {frames_captured} frames...")
                    
        finally:
            # Release the camera
            cap.release()
        
        # Calculate FPS
        elapsed = time.time() - start_time
        fps = frames_captured / elapsed if elapsed > 0 else 0
        
        logger.info(f"Captured {frames_captured} frames in {elapsed:.1f} seconds ({fps:.1f} FPS)")
        
        if frames_captured > 0:
            logger.info("Webcam test SUCCESSFUL!")
            logger.info(f"Device {best_device} is working correctly.")
            return True
        else:
            logger.error("Webcam test FAILED! No frames were captured.")
            return False
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Error testing webcam: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=== PiBoat Webcam Connection Test ===")
    success = main()
    
    if success:
        logger.info("\nTest completed successfully. Your webcam should work with WebRTC.")
        sys.exit(0)
    else:
        logger.error("\nTest failed. Please check your webcam setup.")
        sys.exit(1) 