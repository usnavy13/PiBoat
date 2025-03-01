import fractions
import logging
import math
from datetime import datetime

import cv2
import numpy
from aiortc import VideoStreamTrack
from av import VideoFrame

from piboat.config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
from piboat.webrtc.webcam_utils import get_best_webcam_device

logger = logging.getLogger("VideoTrack")


class TestPatternVideoTrack(VideoStreamTrack):
    """
    A video track that displays a simple color pattern.
    """
    def __init__(self):
        super().__init__()
        self._counter = 0
        self._fps = VIDEO_FPS
        self.width = VIDEO_WIDTH
        self.height = VIDEO_HEIGHT
        self._timestamp = 0
        self.kind = "video"
        self._time_base = fractions.Fraction(1, 90000)
        
        # Define supported codecs to ensure compatibility
        self._supported_codecs = ["VP8", "H264"]
        logger.info(f"Video track initialized with supported codecs: {', '.join(self._supported_codecs)}")
        
        # Set up a simple static image for fallback
        self._static_image = numpy.zeros((self.height, self.width, 3), dtype=numpy.uint8)
        self._static_image[:, :, 0] = 255  # Make it red for easy identification
        
        logger.info(f"Using test pattern video stream with {self.width}x{self.height} resolution at {self._fps}fps")
        
    def get_codec_compatibility(self, remote_sdp):
        """
        Check if the remote SDP offer contains compatible codecs.
        Returns a tuple (compatible, message) where compatible is a boolean
        and message contains details if not compatible.
        """
        if not remote_sdp:
            return (False, "No remote SDP provided")
            
        # Simple SDP parsing to check for codecs
        remote_codecs = []
        
        # Look for codec information in the SDP
        lines = remote_sdp.split("\n")
        for line in lines:
            # Check for rtpmap entries (which define codecs)
            if line.startswith("a=rtpmap:"):
                # Extract codec name from rtpmap
                codec_info = line.split(" ")[1].split("/")[0].upper()
                remote_codecs.append(codec_info)
                logger.info(f"Found codec in SDP: {codec_info}")
                
            # Also check for fmtp lines which might contain specific codec parameters
            elif line.startswith("a=fmtp:") and "profile-level-id" in line:
                remote_codecs.append("H264")  # H.264 specific parameters 
                logger.info("Detected H.264 parameters in SDP")
                
        # If no specific codec info was found but we see a video section,
        # assume basic compatibility rather than rejecting
        if not remote_codecs and "m=video" in remote_sdp:
            logger.info("No specific codec info found, but video section exists. Assuming compatibility.")
            return (True, "Assuming compatibility based on video section presence")
                
        # Check if we found any compatible codecs
        compatible_codecs = [c for c in remote_codecs if c in self._supported_codecs or c in ["H264", "VP8"]]
        
        if compatible_codecs:
            return (True, f"Found compatible codecs: {', '.join(compatible_codecs)}")
        elif remote_codecs:
            # If we found codecs but none are compatible, return false
            return (False, f"Found incompatible codecs: {', '.join(remote_codecs)}")
        else:
            # More permissive: if we have a video section but couldn't parse codecs, assume it's OK
            # Most browsers will support at least H.264 or VP8
            return (True, "No video codecs explicitly found in remote SDP, assuming default compatibility")
    
    async def recv(self):
        pts, time_base = await self._next_timestamp()
        
        try:
            # Create a test pattern
            return await self._create_pattern_frame(pts, time_base)
                
        except Exception as e:
            logger.error(f"Error in video frame generation: {e}")
            # Return a static frame on error
            frame = VideoFrame.from_ndarray(self._static_image, format="bgr24")
            frame.pts = pts
            frame.time_base = time_base
            return frame
    
    async def _create_pattern_frame(self, pts, time_base):
        """Create a simple color pattern."""
        # Create a simple color pattern
        img = numpy.zeros((self.height, self.width, 3), dtype=numpy.uint8)
        
        # Increment counter
        self._counter = (self._counter + 1) % 360
        
        # Simple color gradient
        for y in range(self.height):
            for x in range(self.width):
                hue = (self._counter + y + x) % 180
                if hue < 60:
                    r, g, b = 255, int(hue * 4.25), 0
                elif hue < 120:
                    r, g, b = int((120 - hue) * 4.25), 255, 0
                else:
                    r, g, b = 0, 255, int((hue - 120) * 4.25)
                img[y, x] = [b, g, r]  # OpenCV uses BGR
        
        # Add timestamp to the frame
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            img, 
            f"PiBoat - {timestamp}", 
            (20, 40), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.8, 
            (255, 255, 255), 
            2
        )
        
        # Create VideoFrame from numpy array
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame
            
    async def _next_timestamp(self):
        """Generate the next frame timestamp."""
        self._timestamp += int(90000 / self._fps)
        return self._timestamp, self._time_base 


class WebcamVideoTrack(VideoStreamTrack):
    """
    A video track that captures frames from a USB webcam.
    """
    def __init__(self, device_id=None):
        super().__init__()
        self._fps = VIDEO_FPS
        self.width = VIDEO_WIDTH
        self.height = VIDEO_HEIGHT
        self._timestamp = 0
        self.kind = "video"
        self._time_base = fractions.Fraction(1, 90000)
        
        # If no device_id is provided, try to find the best one
        if device_id is None:
            logger.info(f"No device ID provided, searching for best webcam device...")
            self._device_id = get_best_webcam_device(VIDEO_WIDTH, VIDEO_HEIGHT)
            logger.info(f"Selected best webcam device ID: {self._device_id}")
        else:
            self._device_id = device_id
            
        self._cap = None
        
        # Define supported codecs to ensure compatibility
        self._supported_codecs = ["VP8", "H264"]
        
        # Set up a simple static image for fallback
        self._static_image = numpy.zeros((self.height, self.width, 3), dtype=numpy.uint8)
        self._static_image[:, :, 0] = 255  # Make it red for easy identification
        
        # Initialize webcam with retry logic
        self._initialize_webcam()
        
    def _initialize_webcam(self):
        """Attempt to initialize the webcam with retry logic and device discovery."""
        # First try the specified device ID
        logger.info(f"Attempting to open webcam with device ID: {self._device_id}")
        
        # Release any existing capture if it exists
        if self._cap is not None:
            self._cap.release()
            logger.info("Released existing webcam capture")
        
        # Try to connect with the specified device ID
        self._cap = cv2.VideoCapture(self._device_id)
        
        # If that fails, try to find an available webcam by scanning other device IDs
        if not self._cap.isOpened():
            logger.warning(f"Failed to open webcam with device ID: {self._device_id}")
            
            # Try a few different device IDs
            for device_id in range(10):  # Try devices 0-9
                if device_id == self._device_id:
                    continue  # Skip the one we already tried
                
                logger.info(f"Trying alternative webcam device ID: {device_id}")
                self._cap = cv2.VideoCapture(device_id)
                
                if self._cap.isOpened():
                    logger.info(f"Successfully opened webcam with alternative device ID: {device_id}")
                    self._device_id = device_id
                    break
                else:
                    self._cap.release()
        
        # If we still couldn't open a webcam, raise an error
        if not self._cap.isOpened():
            logger.error(f"Failed to open any webcam device")
            raise RuntimeError("Could not open webcam with any available device ID")
        
        # Add a small delay after opening to ensure the device is ready
        import time
        time.sleep(1.0)  # Increased delay to 1 second for better stability
        
        # Set webcam properties
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)
        
        # Try to read a test frame to ensure the camera is working
        for _ in range(3):  # Try multiple times to get a frame
            ret, _ = self._cap.read()
            if ret:
                break
            time.sleep(0.2)  # Short delay between attempts
        
        if not ret:
            logger.error("Webcam opened but failed to capture test frame")
            self._cap.release()
            raise RuntimeError("Webcam opened but failed to capture test frame")
        
        # Get actual properties (may differ from requested)
        actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Webcam initialized with device ID {self._device_id}")
        logger.info(f"Requested resolution: {self.width}x{self.height}, fps: {self._fps}")
        logger.info(f"Actual resolution: {actual_width}x{actual_height}, fps: {actual_fps}")
    
    def __del__(self):
        """Release webcam when the object is garbage collected."""
        if hasattr(self, '_cap') and self._cap is not None:
            self._cap.release()
            logger.info("Webcam released")
    
    def get_codec_compatibility(self, remote_sdp):
        """
        Check if the remote SDP offer contains compatible codecs.
        Returns a tuple (compatible, message) where compatible is a boolean
        and message contains details if not compatible.
        """
        if not remote_sdp:
            return (False, "No remote SDP provided")
            
        # Simple SDP parsing to check for codecs
        remote_codecs = []
        
        # Look for codec information in the SDP
        lines = remote_sdp.split("\n")
        for line in lines:
            # Check for rtpmap entries (which define codecs)
            if line.startswith("a=rtpmap:"):
                # Extract codec name from rtpmap
                codec_info = line.split(" ")[1].split("/")[0].upper()
                remote_codecs.append(codec_info)
                logger.info(f"Found codec in SDP: {codec_info}")
                
            # Also check for fmtp lines which might contain specific codec parameters
            elif line.startswith("a=fmtp:") and "profile-level-id" in line:
                remote_codecs.append("H264")  # H.264 specific parameters 
                logger.info("Detected H.264 parameters in SDP")
                
        # If no specific codec info was found but we see a video section,
        # assume basic compatibility rather than rejecting
        if not remote_codecs and "m=video" in remote_sdp:
            logger.info("No specific codec info found, but video section exists. Assuming compatibility.")
            return (True, "Assuming compatibility based on video section presence")
                
        # Check if we found any compatible codecs
        compatible_codecs = [c for c in remote_codecs if c in self._supported_codecs or c in ["H264", "VP8"]]
        
        if compatible_codecs:
            return (True, f"Found compatible codecs: {', '.join(compatible_codecs)}")
        elif remote_codecs:
            # If we found codecs but none are compatible, return false
            return (False, f"Found incompatible codecs: {', '.join(remote_codecs)}")
        else:
            # More permissive: if we have a video section but couldn't parse codecs, assume it's OK
            # Most browsers will support at least H.264 or VP8
            return (True, "No video codecs explicitly found in remote SDP, assuming default compatibility")
    
    async def recv(self):
        pts, time_base = await self._next_timestamp()
        
        try:
            # Check if webcam is still open, if not try to reinitialize
            if not self._cap.isOpened():
                logger.warning("Webcam connection lost, attempting to reconnect...")
                try:
                    self._initialize_webcam()
                except Exception as e:
                    logger.error(f"Failed to reconnect to webcam: {e}")
                    raise RuntimeError("Failed to reconnect to webcam")
            
            # Capture frame from webcam
            ret, img = self._cap.read()
            
            if not ret:
                logger.warning("Failed to capture frame, attempting to reconnect...")
                try:
                    # Close and reopen the camera
                    self._cap.release()
                    self._initialize_webcam()
                    # Try to read again
                    ret, img = self._cap.read()
                    if not ret:
                        raise RuntimeError("Still failed to capture frame after reconnect")
                except Exception as e:
                    logger.error(f"Failed to reconnect to webcam: {e}")
                    raise RuntimeError(f"Failed to capture frame and reconnect: {e}")
            
            # Resize the frame if needed to match expected dimensions
            if img.shape[1] != self.width or img.shape[0] != self.height:
                img = cv2.resize(img, (self.width, self.height))
            
            # Add timestamp to the frame
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(
                img, 
                f"PiBoat - {timestamp}", 
                (20, 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.8, 
                (255, 255, 255), 
                2
            )
            
            # Create VideoFrame from numpy array
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            frame.pts = pts
            frame.time_base = time_base
            return frame
                
        except Exception as e:
            logger.error(f"Error capturing webcam frame: {e}")
            # Try one more time to reconnect
            try:
                logger.info("Attempting emergency webcam reconnection...")
                self._cap.release()
                import time
                time.sleep(1)  # Give more time for the device to be released
                self._initialize_webcam()
                
                # If we reconnected successfully, try to get a frame again
                ret, img = self._cap.read()
                if ret:
                    # Resize the frame if needed to match expected dimensions
                    if img.shape[1] != self.width or img.shape[0] != self.height:
                        img = cv2.resize(img, (self.width, self.height))
                        
                    # Add timestamp to the frame
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(
                        img, 
                        f"PiBoat - {timestamp}", 
                        (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.8, 
                        (255, 255, 255), 
                        2
                    )
                    
                    # Create VideoFrame from numpy array
                    frame = VideoFrame.from_ndarray(img, format="bgr24")
                    frame.pts = pts
                    frame.time_base = time_base
                    return frame
                    
            except Exception as reconnect_error:
                logger.error(f"Emergency webcam reconnection failed: {reconnect_error}")
                
            # At this point, we have no choice but to raise the error
            raise RuntimeError(f"Unrecoverable webcam error: {e}")
    
    async def _next_timestamp(self):
        """Generate the next frame timestamp."""
        self._timestamp += int(90000 / self._fps)
        return self._timestamp, self._time_base 