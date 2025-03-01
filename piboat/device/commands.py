import json
import logging
import math
import uuid
from datetime import datetime

logger = logging.getLogger("CommandHandler")

class CommandHandler:
    """
    Handles command messages from clients.
    """
    def __init__(self, telemetry_generator, websocket):
        """
        Initialize the command handler.
        
        Args:
            telemetry_generator: Reference to the telemetry generator for updating position
            websocket: WebSocket connection to send responses
        """
        self.telemetry = telemetry_generator
        self.websocket = websocket
        self.command_log = []
        logger.info("Command handler initialized")
    
    async def handle_command(self, command):
        """
        Handle command messages from clients.
        
        Args:
            command (dict): The command message
        """
        # Log the command for review
        timestamp = datetime.now().isoformat()
        logged_command = {
            "timestamp": timestamp,
            "command": command
        }
        self.command_log.append(logged_command)
        
        # Log to console and file
        logger.info(f"Received command: {json.dumps(command)}")
        
        # Write to a separate command log file
        with open("command_log.json", "a") as f:
            f.write(json.dumps(logged_command) + "\n")
        
        # Process different command types
        command_type = command.get("command")
        
        if command_type == "set_waypoint" or command_type == "set_waypoints":
            await self._handle_waypoint_command(command)
        elif command_type == "emergency_stop":
            await self._handle_emergency_stop(command)
        elif command_type == "set_speed":
            await self._handle_set_speed(command)
        elif command_type == "get_status":
            await self._handle_get_status(command)
        else:
            logger.warning(f"Unknown command type: {command_type}")
            await self.acknowledge_command(command, "rejected", f"Unknown command: {command_type}")
    
    async def _handle_waypoint_command(self, command):
        """Handle waypoint commands."""
        # Simulate accepting a waypoint command
        await self.acknowledge_command(command, "accepted")
        
        command_type = command.get("command")
        # In a real implementation, we would actually change course
        if command_type == "set_waypoint":
            waypoint = command.get("data", {})
            lat = waypoint.get("latitude")
            lon = waypoint.get("longitude")
            logger.info(f"Would navigate to waypoint: {lat}, {lon}")
            
            # Simulate changing course toward the waypoint
            if lat and lon:
                # Calculate heading to waypoint (simplified)
                dx = lon - self.telemetry.longitude
                dy = lat - self.telemetry.latitude
                new_heading = math.degrees(math.atan2(dx, dy)) % 360
                self.telemetry.heading = new_heading
                logger.info(f"Changing course to heading: {self.telemetry.heading}°")
        
        elif command_type == "set_waypoints":
            waypoints = command.get("data", {}).get("waypoints", [])
            logger.info(f"Would navigate through {len(waypoints)} waypoints")
            
            # If there are waypoints, simulate heading toward the first one
            if waypoints and len(waypoints) > 0:
                first = waypoints[0]
                lat = first.get("latitude")
                lon = first.get("longitude")
                
                if lat and lon:
                    # Calculate heading to waypoint (simplified)
                    dx = lon - self.telemetry.longitude
                    dy = lat - self.telemetry.latitude
                    new_heading = math.degrees(math.atan2(dx, dy)) % 360
                    self.telemetry.heading = new_heading
                    logger.info(f"Changing course to heading: {self.telemetry.heading}°")
    
    async def _handle_emergency_stop(self, command):
        """Handle emergency stop commands."""
        # Simulate emergency stop
        self.telemetry.speed = 0
        logger.info("EMERGENCY STOP command received - stopping immediately")
        await self.acknowledge_command(command, "accepted")
    
    async def _handle_set_speed(self, command):
        """Handle speed change commands."""
        # Simulate changing speed
        new_speed = command.get("data", {}).get("speed", self.telemetry.speed)
        logger.info(f"Changing speed from {self.telemetry.speed} to {new_speed} knots")
        self.telemetry.speed = new_speed
        await self.acknowledge_command(command, "accepted")
    
    async def _handle_get_status(self, command):
        """Handle status request commands."""
        # Respond with current status
        status_data = {
            "type": "status_response",
            "command_id": command.get("command_id", str(uuid.uuid4())),
            "device_id": command.get("device_id", "unknown"),
            "data": self.telemetry.get_current_status()
        }
        await self.websocket.send(json.dumps(status_data))
        logger.info("Sent status response")
        await self.acknowledge_command(command, "accepted")
    
    async def acknowledge_command(self, command, status, message=None):
        """
        Send command acknowledgement back to the server.
        
        Args:
            command: The original command
            status: Status of the command (accepted, rejected, etc.)
            message: Optional message to include
        """
        command_id = command.get("command_id", str(uuid.uuid4()))
        
        ack = {
            "type": "command_ack",
            "command_id": command_id,
            "status": status,
        }
        
        if message:
            ack["message"] = message
            
        await self.websocket.send(json.dumps(ack))
        logger.debug(f"Sent command acknowledgement: {status}") 