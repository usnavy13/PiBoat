import json
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription

from piboat.webrtc.video import WebcamVideoTrack
from piboat.webrtc.webcam_utils import get_best_webcam_device
from piboat.config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS

logger = logging.getLogger("WebRTCHandler")

class WebRTCHandler:
    """
    Handles WebRTC signaling and connections.
    """
    def __init__(self, device_id, websocket):
        """
        Initialize the WebRTC handler.
        
        Args:
            device_id (str): Device ID for identification in signaling
            websocket: WebSocket connection for signaling
        """
        self.device_id = device_id
        self.websocket = websocket
        self.peer_connections = {}
        logger.info("WebRTC handler initialized")
    
    async def handle_message(self, message):
        """
        Handle WebRTC signaling messages.
        
        Args:
            message (dict): The WebRTC message
        """
        message_subtype = message.get("subtype")
        
        if message_subtype == "answer":
            await self._handle_answer(message)
        elif message_subtype == "ice_candidate":
            await self._handle_ice_candidate(message)
        elif message_subtype == "request_offer":
            await self._handle_request_offer(message)
        elif message_subtype == "offer":
            await self._handle_offer(message)
        elif message_subtype == "close":
            await self._handle_close(message)
        else:
            logger.warning(f"Unknown WebRTC message subtype: {message_subtype}")
    
    async def _handle_answer(self, message):
        """Handle SDP answer from a client."""
        client_id = message.get("clientId")
        if not client_id:
            logger.warning("Received answer without client ID")
            return
            
        pc = self.peer_connections.get(client_id)
        if not pc:
            logger.warning(f"No peer connection for client {client_id}")
            return
            
        # Apply the remote description
        sdp = message.get("sdp")
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type="answer")
        )
        logger.info(f"Set remote description from client {client_id}")
    
    async def _handle_ice_candidate(self, message):
        """Handle ICE candidate from a client."""
        client_id = message.get("clientId")
        candidate = message.get("candidate")
        
        if not client_id or not candidate:
            logger.warning("Invalid ICE candidate message")
            return
            
        pc = self.peer_connections.get(client_id)
        if not pc:
            logger.warning(f"No peer connection for client {client_id}")
            return
            
        await pc.addIceCandidate(candidate)
        logger.debug(f"Added ICE candidate from client {client_id}")
    
    async def _handle_request_offer(self, message):
        """Handle a request to create a WebRTC offer."""
        client_id = message.get("clientId")
        if not client_id:
            logger.warning("Received request_offer without client ID")
            return
            
        await self.create_webrtc_offer(client_id)
    
    async def _handle_offer(self, message):
        """Handle incoming offer from client."""
        # Get clientId from message - it might be in deviceId or clientId
        client_id = message.get("clientId")
        if not client_id:
            logger.info("No clientId found, checking alternative fields")
            client_id = message.get("client_id")
        
        if not client_id:
            logger.warning("Received offer without client ID")
            return
            
        logger.info(f"Received WebRTC offer from client {client_id}")
        
        # Create a new RTCPeerConnection with default configuration
        pc = RTCPeerConnection()
        self.peer_connections[client_id] = pc
        logger.info(f"Created peer connection for client {client_id}")
        
        # Set up the video track - use the webcam
        try:
            # Get the best webcam device ID
            device_id = get_best_webcam_device(VIDEO_WIDTH, VIDEO_HEIGHT)
            logger.info(f"Using webcam device ID: {device_id}")
            
            # Initialize the video track with the selected device
            video_track = WebcamVideoTrack(device_id=device_id)
            pc.addTrack(video_track)
            logger.info(f"Initialized video stream with {video_track.width}x{video_track.height} resolution at {video_track._fps}fps")
        except Exception as e:
            logger.error(f"Error initializing webcam: {str(e)}")
            # Send error to client
            error_response = {
                "type": "webrtc",
                "subtype": "error",
                "boatId": self.device_id,
                "clientId": client_id,
                "error": "webcam_initialization_failed",
                "message": f"Failed to initialize webcam: {str(e)}"
            }
            await self.websocket.send(json.dumps(error_response))
            
            # Clean up and return
            if client_id in self.peer_connections:
                await self.peer_connections[client_id].close()
                del self.peer_connections[client_id]
                logger.info(f"Closed connection with client {client_id} due to webcam initialization error")
            return
        
        # Set up ICE candidate handling
        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            await self._send_ice_candidate(client_id, candidate)
        
        # Apply the remote description (the offer)
        sdp = message.get("sdp")
        if not sdp:
            logger.warning("Received offer without SDP")
            return
            
        try:
            # Check codec compatibility first
            compatible, compatibility_message = video_track.get_codec_compatibility(sdp)
            logger.info(f"Codec compatibility check: {compatibility_message}")
            
            if not compatible:
                # Send error to client
                error_response = {
                    "type": "webrtc",
                    "subtype": "error",
                    "boatId": self.device_id,
                    "clientId": client_id,
                    "error": "codec_incompatible",
                    "message": compatibility_message
                }
                await self.websocket.send(json.dumps(error_response))
                logger.warning(f"Rejecting WebRTC offer due to codec incompatibility: {compatibility_message}")
                
                # Clean up and return
                if client_id in self.peer_connections:
                    await self.peer_connections[client_id].close()
                    del self.peer_connections[client_id]
                return
            
            # Set the remote description (the offer)
            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
            logger.info(f"Set remote offer from client {client_id}")
            
            try:
                # Create and set the answer - with explicit error handling
                answer = await pc.createAnswer()
                
                # Ensure we have valid media descriptions in the answer
                if not answer.sdp or "m=video" not in answer.sdp:
                    logger.warning("No video stream in answer, checking codec compatibility")
                    # We could add fallback codec handling here if needed
                    # For now, just log and let the process continue
                
                await pc.setLocalDescription(answer)
                
                # Send the answer to the client
                response = {
                    "type": "webrtc",
                    "subtype": "answer",
                    "boatId": self.device_id,
                    "clientId": client_id,
                    "sdp": pc.localDescription.sdp,
                    "sdpType": "answer"
                }
                await self.websocket.send(json.dumps(response))
                logger.info(f"Sent answer to client {client_id}")
                
            except ValueError as codec_error:
                # This is likely a codec negotiation error
                logger.error(f"Codec negotiation error: {str(codec_error)}")
                error_response = {
                    "type": "webrtc",
                    "subtype": "error",
                    "boatId": self.device_id,
                    "clientId": client_id,
                    "error": "codec_negotiation_failed",
                    "message": f"Failed to negotiate compatible video codec: {str(codec_error)}"
                }
                await self.websocket.send(json.dumps(error_response))
                raise  # Re-raise to trigger the cleanup in the outer exception handler
            
        except Exception as e:
            logger.error(f"Error processing WebRTC offer: {str(e)}")
            # Close the peer connection on error
            if client_id in self.peer_connections:
                await self.peer_connections[client_id].close()
                del self.peer_connections[client_id]
                logger.info(f"Closed connection with client {client_id} due to error")
    
    async def _handle_close(self, message):
        """Handle close request from a client."""
        client_id = message.get("clientId")
        if not client_id:
            logger.warning("Received close without client ID")
            return
            
        if client_id in self.peer_connections:
            pc = self.peer_connections[client_id]
            await pc.close()
            del self.peer_connections[client_id]
            logger.info(f"Closed connection with client {client_id}")
    
    async def create_webrtc_offer(self, client_id):
        """
        Create and send a WebRTC offer to a client.
        
        Args:
            client_id (str): Client ID to create the offer for
        """
        try:
            # Create a new RTCPeerConnection with default configuration
            pc = RTCPeerConnection()
            self.peer_connections[client_id] = pc
            logger.info(f"Created peer connection for client {client_id}")
            
            # Set up the video track with best available webcam
            try:
                # Get the best webcam device ID
                device_id = get_best_webcam_device(VIDEO_WIDTH, VIDEO_HEIGHT)
                logger.info(f"Using webcam device ID: {device_id}")
                
                # Initialize the video track with the selected device
                video_track = WebcamVideoTrack(device_id=device_id)
                pc.addTrack(video_track)
                logger.info(f"Initialized video stream with {video_track.width}x{video_track.height} resolution at {video_track._fps}fps")
            except Exception as e:
                logger.error(f"Error initializing webcam: {str(e)}")
                # Send error to client
                error_response = {
                    "type": "webrtc",
                    "subtype": "error",
                    "boatId": self.device_id,
                    "clientId": client_id,
                    "error": "webcam_initialization_failed",
                    "message": f"Failed to initialize webcam: {str(e)}"
                }
                await self.websocket.send(json.dumps(error_response))
                
                # Clean up and return
                if client_id in self.peer_connections:
                    await self.peer_connections[client_id].close()
                    del self.peer_connections[client_id]
                    logger.info(f"Closed connection with client {client_id} due to webcam initialization error")
                return
            
            # Set up ICE candidate handling
            @pc.on("icecandidate")
            async def on_icecandidate(candidate):
                await self._send_ice_candidate(client_id, candidate)
            
            # Create offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Send offer to client via relay server
            message = {
                "type": "webrtc",
                "subtype": "offer",
                "boatId": self.device_id,
                "clientId": client_id,
                "sdp": pc.localDescription.sdp
            }
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent WebRTC offer to client {client_id}")
        except Exception as e:
            logger.error(f"Error creating WebRTC offer: {str(e)}")
    
    async def _send_ice_candidate(self, client_id, candidate):
        """
        Send an ICE candidate to a client.
        
        Args:
            client_id (str): The client ID to send to
            candidate: The ICE candidate
        """
        if candidate:
            try:
                # Ensure all required properties exist
                if not hasattr(candidate, 'candidate') or not candidate.candidate:
                    logger.warning(f"Skipping invalid ICE candidate (missing candidate string)")
                    return
                    
                if not hasattr(candidate, 'sdpMid') or candidate.sdpMid is None:
                    logger.warning(f"ICE candidate missing sdpMid, using empty string")
                    sdpMid = ""
                else:
                    sdpMid = candidate.sdpMid
                    
                if not hasattr(candidate, 'sdpMLineIndex') or candidate.sdpMLineIndex is None:
                    logger.warning(f"ICE candidate missing sdpMLineIndex, using 0")
                    sdpMLineIndex = 0
                else:
                    sdpMLineIndex = candidate.sdpMLineIndex
                    
                message = {
                    "type": "webrtc",
                    "subtype": "ice_candidate",
                    "boatId": self.device_id,
                    "clientId": client_id,
                    "candidate": {
                        "candidate": candidate.candidate,
                        "sdpMid": sdpMid,
                        "sdpMLineIndex": sdpMLineIndex
                    }
                }
                await self.websocket.send(json.dumps(message))
                logger.debug(f"Sent ICE candidate to client {client_id}")
            except Exception as e:
                logger.warning(f"Error sending ICE candidate: {str(e)}")
    
    async def close_all_connections(self):
        """Close all peer connections when shutting down."""
        for client_id, pc in list(self.peer_connections.items()):
            try:
                await pc.close()
                logger.info(f"Closed connection with client {client_id}")
            except Exception as e:
                logger.warning(f"Error closing connection with client {client_id}: {str(e)}")
        
        self.peer_connections.clear() 