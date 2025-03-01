import asyncio
import json
import logging
import time
import websockets

from piboat.config import TELEMETRY_INTERVAL
from piboat.device.telemetry import TelemetryGenerator
from piboat.device.commands import CommandHandler
from piboat.webrtc.webrtc_handler import WebRTCHandler

logger = logging.getLogger("BoatDevice")

class BoatDevice:
    """
    Autonomous boat device that connects to the relay server,
    sends telemetry data, and streams video via WebRTC.
    """
    def __init__(self, device_id, server_url):
        self.device_id = device_id
        self.server_url = server_url.format(device_id=device_id)
        self.websocket = None
        self.running = False
        
        # Initialize telemetry generator
        self.telemetry = TelemetryGenerator()
        
        logger.info(f"Initialized boat device {device_id}")
    
    async def connect(self):
        """Connect to the WebSocket server."""
        logger.info(f"Connecting to server at {self.server_url}")
        
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info("Connected to WebSocket server")
            
            # Once connected, initialize the command and WebRTC handlers
            self.command_handler = CommandHandler(self.telemetry, self.websocket)
            self.webrtc_handler = WebRTCHandler(self.device_id, self.websocket)
            
            self.running = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            return False
    
    async def run(self):
        """Main execution loop."""
        if not await self.connect():
            return
        
        # Start tasks
        tasks = [
            asyncio.create_task(self.telemetry_loop()),
            asyncio.create_task(self.message_handler())
        ]
        
        try:
            self.running = True
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled, shutting down")
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
        finally:
            await self.shutdown()
    
    async def telemetry_loop(self):
        """Periodically send telemetry data to the server."""
        logger.info("Starting telemetry loop")
        
        while self.running:
            try:
                # Generate new telemetry data
                telemetry = self.telemetry.generate_telemetry_data()
                
                # Send telemetry data
                await self.websocket.send(json.dumps(telemetry))
                logger.debug(f"Sent telemetry data: sequence={telemetry['sequence']}")
                
                # Wait for next telemetry interval
                await asyncio.sleep(TELEMETRY_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in telemetry loop: {str(e)}")
                if not self.running:
                    break
                await asyncio.sleep(1)  # Wait before retrying
    
    async def message_handler(self):
        """Handle incoming messages from the server."""
        logger.info("Starting message handler")
        
        while self.running:
            try:
                # Receive message
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # Handle different message types
                message_type = data.get("type")
                
                if message_type == "webrtc":
                    await self.webrtc_handler.handle_message(data)
                elif message_type == "command":
                    await self.command_handler.handle_command(data)
                elif message_type == "ping":
                    # Respond to ping messages with a pong
                    pong = {
                        "type": "pong",
                        "timestamp": int(time.time() * 1000)
                    }
                    await self.websocket.send(json.dumps(pong))
                    logger.debug("Responded to ping with pong")
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed by server")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in message handler: {str(e)}")
                await asyncio.sleep(1)
    
    async def shutdown(self):
        """Clean shutdown of the device."""
        logger.info("Shutting down device")
        self.running = False
        
        # Close WebRTC connections
        if hasattr(self, 'webrtc_handler'):
            await self.webrtc_handler.close_all_connections()
        
        # Close websocket connection
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Closed WebSocket connection")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")
        
        logger.info("Shutdown complete") 