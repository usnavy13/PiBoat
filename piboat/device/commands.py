import json
import logging
from datetime import datetime

logger = logging.getLogger("CommandHandler")

class CommandHandler:
    """
    Simplified command handler that only logs commands without implementing actual control logic.
    """
    def __init__(self, telemetry_generator, websocket):
        """
        Initialize the command handler.
        
        Args:
            telemetry_generator: Reference to the telemetry generator (not used in simplified version)
            websocket: WebSocket connection to send responses
        """
        self.telemetry = telemetry_generator
        self.websocket = websocket
        self.command_log = []
        logger.info("Simplified command handler initialized")
    
    async def handle_command(self, command):
        """
        Handle command messages from clients by logging them and sending acknowledgements.
        No actual command logic is implemented.
        
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
        
        # Simply acknowledge all commands as accepted
        command_type = command.get("command")
        logger.info(f"Command '{command_type}' logged (no action taken)")
        await self.acknowledge_command(command, "accepted")
    
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