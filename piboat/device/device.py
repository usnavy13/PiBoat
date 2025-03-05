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
    def __init__(self, device_id, server_url, gps_port='/dev/ttyACM0'):
        self.device_id = device_id
        self.server_url = server_url.format(device_id=device_id)
        self.websocket = None
        self.running = False
        self.reconnect_interval = 5  # Initial reconnect interval in seconds
        self.max_reconnect_interval = 60  # Maximum reconnect interval
        
        # Initialize telemetry generator with real GPS data
        self.telemetry = TelemetryGenerator(gps_port=gps_port)
        
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
        # Keep attempting to run until explicitly stopped
        while True:
            if not await self.connect():
                # If connection fails, wait and retry
                reconnect_interval = self.reconnect_interval
                logger.info(f"Connection failed, retrying in {reconnect_interval} seconds...")
                await asyncio.sleep(reconnect_interval)
                
                # Exponential backoff with a maximum limit
                self.reconnect_interval = min(self.reconnect_interval * 1.5, self.max_reconnect_interval)
                continue
            
            # Reset reconnection interval on successful connection
            self.reconnect_interval = 5
            
            # Create a reconnection event that tasks can trigger
            reconnect_event = asyncio.Event()
            
            # Start tasks with access to the reconnection event
            telemetry_task = asyncio.create_task(self.telemetry_loop(reconnect_event))
            message_task = asyncio.create_task(self.message_handler(reconnect_event))
            reconnect_wait_task = asyncio.create_task(reconnect_event.wait())
            
            try:
                self.running = True
                
                # Wait for either task to complete or reconnect_event to be set
                done, pending = await asyncio.wait(
                    [telemetry_task, message_task, reconnect_wait_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Check if it was the reconnect event that completed
                if reconnect_wait_task in done:
                    logger.info("Reconnection event triggered, will reconnect")
                else:
                    # Log which task completed
                    for task in done:
                        if task is telemetry_task:
                            logger.info("Telemetry task completed")
                        elif task is message_task:
                            logger.info("Message handler task completed")
                
                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
            except asyncio.CancelledError:
                logger.info("Tasks cancelled, shutting down")
                self.running = False
                break  # Exit the main loop if tasks are explicitly cancelled
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
            finally:
                # Clean up resources but don't shut down completely
                await self.cleanup_for_reconnection()
                
            # Check if we should exit completely
            if not self.running:
                logger.info("Device explicitly stopped, exiting")
                break
            
            # If we reached here, connection was lost but we should reconnect
            reconnect_interval = self.reconnect_interval
            logger.info(f"Connection lost, attempting to reconnect in {reconnect_interval} seconds...")
            await asyncio.sleep(reconnect_interval)
            
            # Exponential backoff with a maximum limit
            self.reconnect_interval = min(self.reconnect_interval * 1.5, self.max_reconnect_interval)
            
    async def cleanup_for_reconnection(self):
        """Clean up resources for reconnection without full shutdown."""
        logger.info("Cleaning up for reconnection")
        
        # Close WebSocket connection if it exists
        if self.websocket is not None:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing websocket: {str(e)}")
            
        # Clear the websocket reference
        self.websocket = None
        
        # We don't shut down telemetry or WebRTC handlers completely
        # as they will be reused on reconnection
    
    async def telemetry_loop(self, reconnect_event=None):
        """Periodically send telemetry data to the server."""
        logger.info("Starting telemetry loop")
        
        last_gps_status = None
        
        while self.running:
            try:
                # Generate new telemetry data (keep the original format for internal use)
                telemetry = self.telemetry.generate_telemetry_data()
                
                # Enhanced logging for GPS status changes
                current_gps_status = None
                if 'status' in telemetry and 'gps' in telemetry['status']:
                    gps_info = telemetry['status']['gps']
                    current_gps_status = gps_info.get('status')
                    
                    # Log GPS status changes
                    if current_gps_status != last_gps_status:
                        logger.info(f"GPS status changed: {last_gps_status} -> {current_gps_status}")
                        if current_gps_status == 'acquiring':
                            logger.info(f"GPS is acquiring fix. Satellites: {gps_info.get('satellites')}")
                        elif current_gps_status == 'fix_acquired':
                            logger.info(f"GPS fix acquired! Position: {telemetry['position']['latitude']}, {telemetry['position']['longitude']}")
                    
                    # Log detailed GPS info periodically (every 10 sequences)
                    if telemetry['sequence'] % 10 == 0:
                        logger.info(f"GPS Status: {current_gps_status}, Fix: {gps_info.get('has_fix')}, Satellites: {gps_info.get('satellites')}")
                
                last_gps_status = current_gps_status
                
                # Generate telemetry in server format and send it if websocket is connected
                if self.websocket is not None:
                    try:
                        server_telemetry = self.telemetry.generate_server_telemetry_data()
                        await self.websocket.send(json.dumps(server_telemetry))
                        logger.debug(f"Sent telemetry data: sequence={server_telemetry['sequence']}, type={server_telemetry['type']}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Connection closed while sending telemetry")
                        if reconnect_event:
                            reconnect_event.set()
                        return  # Exit the function to trigger reconnection
                    except Exception as e:
                        logger.warning(f"Failed to send telemetry: {str(e)}")
                        # Continue running even if we can't send data
                else:
                    logger.debug("WebSocket not available, skipping telemetry send")
                
                # Wait for next telemetry interval
                await asyncio.sleep(TELEMETRY_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in telemetry loop: {str(e)}")
                if not self.running:
                    break
                await asyncio.sleep(1)  # Wait before retrying
    
    async def message_handler(self, reconnect_event=None):
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
                logger.warning("Connection closed by server, will attempt to reconnect")
                if reconnect_event:
                    reconnect_event.set()
                return  # Exit the function to trigger reconnection
            except Exception as e:
                logger.error(f"Error in message handler: {str(e)}")
                await asyncio.sleep(1)
    
    async def shutdown(self):
        """Shutdown the boat device and clean up resources."""
        logger.info("Shutting down boat device...")
        self.running = False
        
        # Shutdown video streaming
        if hasattr(self, 'webrtc_handler'):
            await self.webrtc_handler.shutdown()
        
        # Cleanup telemetry resources
        self.telemetry.shutdown()
        
        # Close WebSocket connection
        if self.websocket and self.websocket.open:
            await self.websocket.close()
            
        logger.info("Boat device shutdown completed") 