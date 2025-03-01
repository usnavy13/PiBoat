#!/usr/bin/env python3
"""
Enhanced Webcam Test Script for Raspberry Pi
This script identifies available webcams, tests connections, and provides detailed diagnostics.
"""
import cv2
import time
import os
import sys
import glob
from datetime import datetime

def list_v4l_devices():
    """
    List all Video4Linux devices available in the system.
    
    Returns:
        A list of available video device paths
    """
    devices = glob.glob('/dev/video*')
    return sorted(devices)

def get_device_info(device_path):
    """
    Get detailed information about a V4L device.
    
    Args:
        device_path: Path to the video device (e.g., /dev/video0)
    
    Returns:
        Dictionary with device information or None if failed
    """
    try:
        # Extract device number from path
        device_id = int(device_path.replace('/dev/video', ''))
        
        # Try to open the device
        cap = cv2.VideoCapture(device_id)
        if not cap.isOpened():
            return {
                'path': device_path,
                'id': device_id,
                'status': 'Failed to open',
                'error': 'Device could not be opened'
            }
        
        # Get device properties
        props = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'format': int(cap.get(cv2.CAP_PROP_FORMAT)),
            'backend': cap.getBackendName()
        }
        
        # Try to capture a frame to verify working status
        ret, frame = cap.read()
        if ret:
            status = 'Working'
            frame_info = f"{frame.shape[1]}x{frame.shape[0]}, {frame.dtype}"
        else:
            status = 'Not capturing frames'
            frame_info = 'N/A'
        
        # Release the capture
        cap.release()
        
        return {
            'path': device_path,
            'id': device_id,
            'status': status,
            'properties': props,
            'frame_info': frame_info
        }
        
    except Exception as e:
        return {
            'path': device_path,
            'id': device_id if 'device_id' in locals() else -1,
            'status': 'Error',
            'error': str(e)
        }

def test_all_devices():
    """
    Test all available video devices and report details.
    
    Returns:
        List of working device IDs
    """
    print("Detecting and testing video devices...")
    devices = list_v4l_devices()
    
    if not devices:
        print("No video devices found.")
        return []
    
    print(f"Found {len(devices)} video device(s):")
    
    working_devices = []
    
    for device_path in devices:
        print(f"\nTesting {device_path}...")
        info = get_device_info(device_path)
        
        print(f"  Status: {info['status']}")
        
        if 'error' in info:
            print(f"  Error: {info['error']}")
            continue
            
        if info['status'] == 'Working':
            working_devices.append(info['id'])
            print(f"  Backend: {info['properties']['backend']}")
            print(f"  Resolution: {info['properties']['width']}x{info['properties']['height']}")
            print(f"  FPS: {info['properties']['fps']}")
            print(f"  Frame Info: {info['frame_info']}")
        
    print(f"\nFound {len(working_devices)} working device(s): {working_devices}")
    return working_devices

def test_resolutions(device_id):
    """
    Test different resolutions on a specific device.
    
    Args:
        device_id: Device ID to test
    
    Returns:
        List of working resolutions
    """
    # Common resolutions to test
    resolutions = [
        (640, 480),   # VGA
        (800, 600),   # SVGA
        (1280, 720),  # 720p
        (1920, 1080), # 1080p
        (320, 240),   # QVGA
        (1024, 768),  # XGA
    ]
    
    print(f"\nTesting resolutions for device {device_id}:")
    working_resolutions = []
    
    cap = cv2.VideoCapture(device_id)
    if not cap.isOpened():
        print(f"  Error: Could not open device {device_id}")
        return working_resolutions
    
    for width, height in resolutions:
        print(f"  Testing {width}x{height}...", end="")
        
        # Set resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Get actual resolution (may differ from requested)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Try to capture a frame to verify
        ret, frame = cap.read()
        
        if ret:
            if actual_width == width and actual_height == height:
                status = "OK"
                working_resolutions.append((width, height))
            else:
                status = f"Adjusted to {actual_width}x{actual_height}"
                working_resolutions.append((actual_width, actual_height))
        else:
            status = "Failed"
        
        print(f" {status}")
    
    cap.release()
    return working_resolutions

def test_fps(device_id, resolution):
    """
    Test FPS capabilities of a webcam with a specific resolution.
    
    Args:
        device_id: Device ID to test
        resolution: (width, height) tuple
    
    Returns:
        Measured FPS
    """
    width, height = resolution
    
    cap = cv2.VideoCapture(device_id)
    if not cap.isOpened():
        return 0
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Warm up the camera
    for _ in range(5):
        cap.read()
    
    # Measure FPS
    frames = 0
    start_time = time.time()
    duration = 2  # seconds
    
    while time.time() - start_time < duration:
        ret, _ = cap.read()
        if ret:
            frames += 1
    
    elapsed = time.time() - start_time
    fps = frames / elapsed
    
    cap.release()
    return fps

def test_webcam(device_id=0, duration=5, fps=20, width=640, height=480):
    """
    Connect to webcam, record video for specified duration, and save to file.
    
    Args:
        device_id: Webcam device ID
        duration: Length of video recording in seconds
        fps: Frames per second to record
        width: Frame width
        height: Frame height
    
    Returns:
        Path to saved video file or None if failed
    """
    # Create output directory if it doesn't exist
    output_dir = "webcam_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename based on current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"webcam_test_{timestamp}_dev{device_id}.avi")
    
    # Try to connect to the webcam
    cap = cv2.VideoCapture(device_id)
    
    # Check if the webcam is opened correctly
    if not cap.isOpened():
        print(f"Error: Could not open webcam with device ID {device_id}")
        return None
    
    # Set webcam properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    
    # Get webcam properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Define codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_file, fourcc, fps, (frame_width, frame_height))
    
    print(f"Recording {duration} seconds of video at {fps} FPS...")
    print(f"Resolution: {frame_width}x{frame_height} (requested: {width}x{height})")
    print(f"Reported FPS: {actual_fps} (requested: {fps})")
    
    start_time = time.time()
    frames_captured = 0
    
    try:
        # Record for specified duration
        while time.time() - start_time < duration:
            ret, frame = cap.read()
            
            if not ret:
                print("Error: Failed to capture frame")
                break
            
            # Write the frame to the output file
            out.write(frame)
            frames_captured += 1
            
            # Display progress
            if frames_captured % 10 == 0:
                elapsed = time.time() - start_time
                print(f"Captured {frames_captured} frames ({elapsed:.1f}s elapsed)")
    
    except KeyboardInterrupt:
        print("Recording stopped by user")
    
    finally:
        # Release webcam and video writer
        cap.release()
        out.release()
        
        # Verify the recording
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"Video saved successfully to: {output_file}")
            actual_fps = frames_captured / (time.time() - start_time)
            print(f"Total frames captured: {frames_captured}")
            print(f"Actual FPS: {actual_fps:.1f}")
            return output_file
        else:
            print("Error: Failed to save video file")
            return None

if __name__ == "__main__":
    print("Enhanced Webcam Test Script for Raspberry Pi")
    print("============================================")
    
    # Detect and test all available webcams
    working_devices = test_all_devices()
    
    if not working_devices:
        print("\nNo working webcam devices found. Please check connections.")
        sys.exit(1)
    
    # Select a device for further testing
    if len(working_devices) > 1:
        print("\nMultiple working devices found. Please select one:")
        for i, device_id in enumerate(working_devices):
            print(f"{i+1}. Device {device_id} (/dev/video{device_id})")
        
        selection = -1
        while selection < 0 or selection >= len(working_devices):
            try:
                selection = int(input("Enter selection (1-{}): ".format(len(working_devices)))) - 1
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        selected_device = working_devices[selection]
    else:
        selected_device = working_devices[0]
        print(f"\nUsing device {selected_device} for further testing.")
    
    # Test supported resolutions
    resolutions = test_resolutions(selected_device)
    
    if not resolutions:
        print("No working resolutions found for this device.")
        sys.exit(1)
    
    # Test FPS for each resolution
    print("\nTesting FPS capabilities:")
    for width, height in resolutions:
        fps = test_fps(selected_device, (width, height))
        print(f"  {width}x{height}: {fps:.1f} FPS")
    
    # Run video recording test with best resolution
    print("\nRunning video recording test with best resolution...")
    best_resolution = resolutions[0]  # Default to first resolution
    
    # Try to find 640x480 if available, or closest
    target_res = (640, 480)
    closest_res = None
    closest_diff = float('inf')
    
    for res in resolutions:
        # Calculate how close this resolution is to our target
        diff = abs(res[0] - target_res[0]) + abs(res[1] - target_res[1])
        if diff < closest_diff:
            closest_diff = diff
            closest_res = res
    
    if closest_res:
        best_resolution = closest_res
    
    # Run recording test
    result = test_webcam(
        device_id=selected_device,
        width=best_resolution[0],
        height=best_resolution[1],
        fps=20,
        duration=5
    )
    
    if result:
        print("\nTest completed successfully.")
        print(f"Device {selected_device} is working with resolution {best_resolution[0]}x{best_resolution[1]}.")
        print("Recommendation: Use this device ID and resolution in your WebRTC configuration.")
    else:
        print("\nTest failed.") 