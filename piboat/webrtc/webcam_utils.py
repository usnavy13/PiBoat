import cv2
import logging
import glob
import os
import time

logger = logging.getLogger("WebcamUtils")

class WebcamDetector:
    """
    Utility class to detect and validate available webcam devices.
    Helps ensure we use a working webcam device ID.
    """
    
    @staticmethod
    def list_v4l_devices():
        """
        List all Video4Linux devices available in the system.
        
        Returns:
            A list of available video device paths
        """
        try:
            devices = glob.glob('/dev/video*')
            return sorted(devices)
        except Exception as e:
            logger.error(f"Error listing V4L devices: {e}")
            return []
    
    @staticmethod
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
                # Check if the error might be because the device is busy/already in use
                if os.path.exists(device_path):
                    # Try with a different API backend to test if it's really a camera
                    for backend in [cv2.CAP_V4L2, cv2.CAP_V4L]:
                        test_cap = cv2.VideoCapture(device_id, backend)
                        if test_cap.isOpened():
                            test_cap.release()
                            return {
                                'path': device_path,
                                'id': device_id,
                                'status': 'Busy',
                                'error': 'Device is likely already in use'
                            }
                        
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
            logger.error(f"Error getting device info for {device_path}: {e}")
            return {
                'path': device_path,
                'id': device_id if 'device_id' in locals() else -1,
                'status': 'Error',
                'error': str(e)
            }
    
    @staticmethod
    def find_working_devices(stop_after_first=False, start_with_device=0, max_devices=None, check_busy=True):
        """
        Find all working video devices.
        
        Args:
            stop_after_first: If True, stop testing after finding the first working device.
            start_with_device: Start testing with this device ID (useful to prioritize known devices).
            max_devices: Maximum number of devices to check before giving up (None = check all)
            check_busy: If True, consider 'Busy' devices as potentially valid and return them
        
        Returns:
            List of working device IDs and a list of busy device IDs
        """
        logger.info("Detecting video devices...")
        devices = WebcamDetector.list_v4l_devices()
        
        if not devices:
            logger.warning("No video devices found")
            return [], []
        
        logger.info(f"Found {len(devices)} video device(s)")
        
        working_devices = []
        busy_devices = []
        devices_checked = 0
        
        # If start_with_device is specified and exists, test it first
        device_zero_path = f'/dev/video{start_with_device}'
        if device_zero_path in devices:
            devices.remove(device_zero_path)
            devices.insert(0, device_zero_path)
        
        for device_path in devices:
            # Limit the number of devices to check
            if max_devices is not None and devices_checked >= max_devices:
                logger.info(f"Reached maximum devices to check ({max_devices}), stopping search.")
                break
                
            devices_checked += 1
            logger.info(f"Testing {device_path}")
            info = WebcamDetector.get_device_info(device_path)
            
            logger.info(f"Device {device_path} status: {info['status']}")
            
            if info['status'] == 'Working':
                working_devices.append(info['id'])
                logger.info(f"Device {info['id']} is working with resolution "
                          f"{info['properties']['width']}x{info['properties']['height']} "
                          f"at {info['properties']['fps']} FPS")
                
                # Stop after finding the first working device if requested
                if stop_after_first:
                    logger.info(f"Found first working device, stopping search as requested.")
                    break
            elif info['status'] == 'Busy' and check_busy:
                busy_devices.append(info['id'])
                logger.info(f"Device {info['id']} appears to be busy (possibly already in use)")
                
                # If no working device yet and we have a busy one, consider it potentially valid
                if check_busy and stop_after_first and not working_devices:
                    logger.info(f"Found busy device and no working devices, considering it as potentially valid.")
                    break
        
        logger.info(f"Found {len(working_devices)} working device(s): {working_devices}")
        if busy_devices:
            logger.info(f"Found {len(busy_devices)} busy device(s): {busy_devices}")
            
        return working_devices, busy_devices
    
    @staticmethod
    def test_resolution(device_id, width, height):
        """
        Test if a specific resolution works with a device.
        
        Args:
            device_id: Device ID to test
            width: Desired width
            height: Desired height
            
        Returns:
            Tuple of (success, actual_width, actual_height)
        """
        try:
            cap = cv2.VideoCapture(device_id)
            if not cap.isOpened():
                logger.error(f"Could not open device {device_id}")
                return False, 0, 0
            
            # Set resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Get actual resolution (may differ from requested)
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Try to capture a frame to verify
            ret, _ = cap.read()
            
            # Release the capture
            cap.release()
            
            if ret:
                return True, actual_width, actual_height
            else:
                logger.warning(f"Device {device_id} failed to capture frame at {width}x{height}")
                return False, 0, 0
                
        except Exception as e:
            logger.error(f"Error testing resolution for device {device_id}: {e}")
            return False, 0, 0
    
    @staticmethod
    def find_best_device(target_width, target_height, stop_after_first=True, max_devices=3):
        """
        Find the best working webcam device for the given resolution.
        
        Args:
            target_width: Desired width
            target_height: Desired height
            stop_after_first: If True, stop searching after finding the first working device
            max_devices: Maximum number of devices to check before giving up
            
        Returns:
            Tuple of (device_id, actual_width, actual_height) or (None, 0, 0) if no device works
        """
        # Find working devices
        working_devices, busy_devices = WebcamDetector.find_working_devices(
            stop_after_first=stop_after_first, 
            start_with_device=0,
            max_devices=max_devices,
            check_busy=True
        )
        
        # If no working devices but we have busy ones, it's likely the camera is already in use
        if not working_devices and busy_devices:
            logger.warning("No available devices found, but detected busy devices. Camera likely already in use.")
            # Return the first busy device as it's probably a valid camera just currently in use
            return busy_devices[0], target_width, target_height
        
        if not working_devices:
            logger.error("No working webcam devices found")
            return None, 0, 0
        
        # Test each device with the target resolution
        best_device = None
        best_width = 0
        best_height = 0
        best_diff = float('inf')
        
        for device_id in working_devices:
            success, width, height = WebcamDetector.test_resolution(device_id, target_width, target_height)
            
            if success:
                # Calculate how close this resolution is to our target
                diff = abs(width - target_width) + abs(height - target_height)
                
                if diff < best_diff:
                    best_diff = diff
                    best_device = device_id
                    best_width = width
                    best_height = height
                    
                    # If we found an exact match, stop searching
                    if diff == 0:
                        break
        
        if best_device is not None:
            logger.info(f"Best device: {best_device} with resolution {best_width}x{best_height}")
            return best_device, best_width, best_height
        else:
            logger.error("No suitable webcam device found")
            return None, 0, 0

def get_best_webcam_device(target_width=640, target_height=480):
    """
    Convenience function to get the best webcam device for the target resolution.
    
    Args:
        target_width: Desired width (default: 640)
        target_height: Desired height (default: 480)
        
    Returns:
        The device ID of the best webcam or 0 if none found
    """
    try:
        # Only check a maximum of 3 devices to prevent long search times
        device_id, _, _ = WebcamDetector.find_best_device(
            target_width, 
            target_height, 
            stop_after_first=True,
            max_devices=3
        )
        return 0 if device_id is None else device_id
    except Exception as e:
        logger.error(f"Error finding best webcam device: {e}")
        return 0  # Fall back to default device ID 