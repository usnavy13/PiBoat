import fractions
import logging
import math
from datetime import datetime

import cv2
import numpy
from aiortc import VideoStreamTrack
from av import VideoFrame

from piboat.config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS

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