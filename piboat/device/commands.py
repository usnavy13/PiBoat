import json
import logging
import os
from datetime import datetime
from piboat.device.motor_controller import MotorController

logger = logging.getLogger("CommandHandler")

# Get the maximum rudder angle from environment variable (default to 45 degrees if not set)
MAX_RUDDER_ANGLE = float(os.environ.get("MAX_RUDDER_ANGLE", 45.0))

class CommandHandler:
    """
    Command handler that processes control commands and controls the boat hardware.
    """
    def __init__(self, telemetry_generator, websocket, motor_controller):
        """
        Initialize the command handler.
        
        Args:
            telemetry_generator: Reference to the telemetry generator
            websocket: WebSocket connection to send responses
            motor_controller: Existing motor controller instance to use
        """
        self.telemetry = telemetry_generator
        self.websocket = websocket
        self.command_log = []
        self.max_rudder_angle = MAX_RUDDER_ANGLE
        
        # Use the provided motor controller
        self.motor_controller = motor_controller
        self.motor_controller_initialized = self.motor_controller is not None
        
        if self.motor_controller_initialized:
            logger.info(f"Command handler initialized with motor control (max rudder angle: ±{self.max_rudder_angle}°)")
        else:
            logger.warning("Command handler initialized but no motor controller provided")
    
    async def handle_command(self, command):
        """
        Handle command messages from clients.
        
        Args:
            command (dict): The command message
        """
        # Log the command
        timestamp = datetime.now().isoformat()
        logged_command = {
            "timestamp": timestamp,
            "command": command
        }
        self.command_log.append(logged_command)
        
        # Log to console and file
        logger.info(f"Received command: {json.dumps(command)}")
        
        # Write to command log file
        with open("command_log.json", "a") as f:
            f.write(json.dumps(logged_command) + "\n")
        
        # Process the command
        command_type = command.get("command")
        data = command.get("data", {})
        status = "rejected"
        message = None
        
        if not self.motor_controller_initialized:
            message = "Motor controller not initialized"
            logger.error(f"Cannot process command '{command_type}': {message}")
        else:
            # Handle different command types
            if command_type == "set_rudder":
                # Get normalized position (-100 to 100)
                normalized_position = data.get("position", 0)
                
                # Ensure position is within bounds
                normalized_position = max(-100, min(normalized_position, 100))
                
                # Convert normalized position (-100 to 100) to actual degrees based on MAX_RUDDER_ANGLE
                degrees = (normalized_position / 100.0) * self.max_rudder_angle
                
                # Call motor controller with the actual degrees
                success = self.motor_controller.set_rudder(degrees)
                status = "accepted" if success else "rejected"
                if success:
                    logger.info(f"Rudder command: normalized position {normalized_position} → {degrees:.1f}° (max angle: ±{self.max_rudder_angle}°)")
                else:
                    message = "Failed to set rudder position"
            
            elif command_type == "set_throttle":
                throttle = data.get("throttle", 0)
                # Optional parameters
                ramp_time = data.get("ramp_time", 1.0)
                success = self.motor_controller.set_throttle(throttle, ramp_time)
                status = "accepted" if success else "rejected"
                if not success:
                    message = "Failed to set throttle"
            
            elif command_type == "stop":
                # Execute both commands concurrently - the motor controller will handle parallelization
                rudder_success = self.motor_controller.set_rudder(0)
                motor_success = self.motor_controller.set_throttle(0, ramp_time=1.0)
                success = motor_success and rudder_success
                status = "accepted" if success else "rejected"
                if not success:
                    if not rudder_success:
                        message = "Failed to center rudder"
                    elif not motor_success:
                        message = "Failed to stop motors"
                    else:
                        message = "Failed to execute stop command"
                if success:
                    logger.info("Stop command executed: motors stopping and rudder centered concurrently")
            
            else:
                logger.warning(f"Unknown command type: {command_type}")
                message = f"Unknown command type: {command_type}"
        
        # Send acknowledgement
        await self.acknowledge_command(command, status, message)
    
    async def acknowledge_command(self, command, status, message=None):
        """
        Send command acknowledgement back to the server.
        
        Args:
            command: The original command
            status: Status of the command (accepted, rejected, etc.)
            message: Optional message to include
        """
        command_id = command.get("command_id", "unknown")
        
        ack = {
            "type": "command_ack",
            "command_id": command_id,
            "status": status,
        }
        
        if message:
            ack["message"] = message
            
        await self.websocket.send(json.dumps(ack))
        logger.debug(f"Sent command acknowledgement: {status}")
    
    def cleanup(self):
        """Clean up resources used by the command handler"""
        if self.motor_controller_initialized:
            self.motor_controller.cleanup()
            logger.info("Command handler cleanup completed") 