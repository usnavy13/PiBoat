import atexit
from rpi_hardware_pwm import HardwarePWM
import time
import logging

logger = logging.getLogger("MotorController")

# Define which Raspberry Pi model you have
# For Raspberry Pi 1/2/3/4, use CHIP = 0
# For Raspberry Pi 5, use CHIP = 0 for GPIO_12 and GPIO_13
#              or use CHIP = 2 for GPIO_18 and GPIO_19
CHIP = 2  # Using CHIP = 2 for Raspberry Pi 5 with GPIO_18 and GPIO_19

# Define PWM channels
# For Pi 5 with CHIP=2: Channel 2 = GPIO_18, Channel 3 = GPIO_19
RUDDER_CHANNEL = 3 
THRUST_CHANNEL = 2    

# Define PWM frequency (Hz)
# Servo and ESC typically operate at 50Hz (20ms period)
PWM_FREQUENCY = 50

# Global variables to track PWM instances for emergency shutdown
_global_pwm_instances = []

# Emergency cleanup function that will be called at exit
def _emergency_pwm_cleanup():
    """Global emergency cleanup for all PWM instances at program exit"""
    global _global_pwm_instances
    
    if _global_pwm_instances:
        print("Performing emergency PWM cleanup at exit")
        for pwm_instance in _global_pwm_instances:
            try:
                # For thrust PWM, set to neutral position
                if pwm_instance.pwm_channel == THRUST_CHANNEL:
                    # 7.5% duty cycle = 1.5ms pulse = neutral position
                    pwm_instance.change_duty_cycle(7.5)
                
                # Stop the PWM
                pwm_instance.stop()
            except Exception as e:
                print(f"Error during emergency PWM cleanup: {e}")
        
        # Clear the list
        _global_pwm_instances = []

# Register the emergency cleanup function
atexit.register(_emergency_pwm_cleanup)

class MotorController:
    """
    Controls the boat's motors using hardware PWM for rudder (servo) and thrust (ESC)
    """
    def __init__(self):
        self.rudder_pwm = None
        self.thrust_pwm = None
        self.initialized = False
        self.current_thrust = 0  # Keep track of current thrust level
        self.current_rudder = 0  # Keep track of current rudder position in degrees
    
    def initialize(self):
        """Initialize the PWM hardware for rudder and thrust control"""
        try:
            # Initialize rudder PWM (servo)
            self.rudder_pwm = HardwarePWM(pwm_channel=RUDDER_CHANNEL, hz=PWM_FREQUENCY, chip=CHIP)
            self.rudder_pwm.start(0)  # Start with 0% duty cycle
            
            # Add to global list for emergency cleanup
            global _global_pwm_instances
            _global_pwm_instances.append(self.rudder_pwm)
            
            # Initialize thrust PWM (ESC)
            self.thrust_pwm = HardwarePWM(pwm_channel=THRUST_CHANNEL, hz=PWM_FREQUENCY, chip=CHIP)
            self.thrust_pwm.start(7.5)  # Start with neutral position (7.5% duty cycle = 1.5ms pulse)
            
            # Add to global list for emergency cleanup
            _global_pwm_instances.append(self.thrust_pwm)
            
            self.initialized = True
            logger.info("Boat motor control system initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing motor controller: {e}")
            return False
    
    def degrees_to_duty_cycle(self, degrees):
        """
        Convert degrees (-135 to 135) to duty cycle for a 270-degree servo
        
        For this specific 270-degree servo:
        - 500µs pulse width (2.5% duty cycle at 50Hz) for -135 degrees
        - 1500µs pulse width (7.5% duty cycle at 50Hz) for 0 degrees
        - 2500µs pulse width (12.5% duty cycle at 50Hz) for 135 degrees
        """
        # Map from [-135, 135] to [2.5, 12.5]
        duty_cycle = 7.5 + (degrees / 135.0) * 5.0
        
        # Ensure duty cycle is within bounds
        return max(2.5, min(duty_cycle, 12.5))
    
    def set_rudder(self, degrees):
        """
        Set the rudder position based on degrees:
        -135 corresponds to full port (left) position (500µs pulse)
        0 corresponds to center position (1500µs pulse)
        135 corresponds to full starboard (right) position (2500µs pulse)
        
        Total range is 270 degrees.
        """
        if not self.initialized:
            logger.warning("Motor control system not initialized")
            return False
            
        if degrees < -135 or degrees > 135:
            logger.warning("Rudder position must be between -135 and 135 degrees")
            return False
        
        try:
            # Convert degrees to duty cycle
            duty_cycle = self.degrees_to_duty_cycle(degrees)
            
            # Set the PWM duty cycle
            self.rudder_pwm.change_duty_cycle(duty_cycle)
            # Store current rudder position
            self.current_rudder = degrees
            logger.info(f"Rudder set to {degrees}° ({'port' if degrees < 0 else 'starboard' if degrees > 0 else 'center'})")
            return True
        except Exception as e:
            logger.error(f"Error setting rudder position: {e}")
            return False
    
    def speed_to_duty_cycle(self, speed):
        """
        Convert speed (-100 to 100) to duty cycle for a bi-directional ESC
        
        For this bi-directional ESC:
        - 1000µs pulse width (5.0% duty cycle at 50Hz) for -100% (full reverse)
        - 1500µs pulse width (7.5% duty cycle at 50Hz) for 0% (neutral)
        - 2000µs pulse width (10.0% duty cycle at 50Hz) for 100% (full forward)
        """
        # Map from [-100, 100] to [5.0, 10.0]
        duty_cycle = 7.5 + (speed / 100.0) * 2.5
        
        # Ensure duty cycle is within bounds
        return max(5.0, min(duty_cycle, 10.0))
    
    def set_throttle(self, speed, ramp_time=1.0, step_size=2.0):
        """
        Set the propeller thrust based on percentage with gradual ramping:
        -100 corresponds to full reverse thrust (1000µs pulse)
        0 corresponds to neutral/stop (1500µs pulse)
        100 corresponds to full forward thrust (2000µs pulse)
        
        Parameters:
        - speed: Target thrust (-100 to 100)
        - ramp_time: Time in seconds to ramp to target thrust
        - step_size: Size of each step when ramping (smaller = smoother but slower)
        """
        if not self.initialized:
            logger.warning("Motor control system not initialized")
            return False
            
        if speed < -100 or speed > 100:
            logger.warning("Thrust must be between -100 and 100 percent")
            return False
        
        try:
            # Check if there's a need to ramp (if speed change is significant)
            if abs(speed - self.current_thrust) <= step_size:
                duty_cycle = self.speed_to_duty_cycle(speed)
                self.thrust_pwm.change_duty_cycle(duty_cycle)
                self.current_thrust = speed
                logger.info(f"Thrust set to {speed}% ({'reverse' if speed < 0 else 'forward' if speed > 0 else 'stop'})")
                return True
                
            # Calculate number of steps needed for ramping
            speed_diff = speed - self.current_thrust
            num_steps = abs(int(speed_diff / step_size))
            if num_steps == 0:
                num_steps = 1
                
            # Calculate delay between steps
            step_delay = ramp_time / num_steps
            
            # Determine step direction and size
            step_direction = 1 if speed_diff > 0 else -1
            
            # Perform the ramping
            current = self.current_thrust
            logger.info(f"Adjusting thrust from {self.current_thrust}% to {speed}%...")
            
            for i in range(1, num_steps + 1):
                # Calculate intermediate speed
                if i < num_steps:
                    current = self.current_thrust + (i * step_size * step_direction)
                else:
                    current = speed  # Ensure we end exactly at target speed
                    
                # Apply the speed
                duty_cycle = self.speed_to_duty_cycle(current)
                self.thrust_pwm.change_duty_cycle(duty_cycle)
                
                # Only log progress at 25%, 50%, 75% and completion
                if i == num_steps or i % max(1, int(num_steps/4)) == 0:
                    logger.debug(f"  Thrust: {current:.1f}%")
                
                # Wait before next step
                time.sleep(step_delay)
            
            # Update current thrust
            self.current_thrust = speed
            logger.info(f"Thrust set to {speed}% ({'reverse' if speed < 0 else 'forward' if speed > 0 else 'stop'})")
            return True
        except Exception as e:
            logger.error(f"Error setting thrust: {e}")
            return False
    
    def stop(self):
        """Stop all motors by setting throttle to 0"""
        return self.set_throttle(0, ramp_time=1.0)
    
    def cleanup(self):
        """Stop PWM and release resources"""
        if self.initialized:
            try:
                # Stop thruster immediately (no ramping during emergency stop)
                if self.thrust_pwm:
                    # Set neutral throttle position directly with no ramping
                    duty_cycle = self.speed_to_duty_cycle(0)
                    self.thrust_pwm.change_duty_cycle(duty_cycle)
                    self.current_thrust = 0
                    logger.info("Emergency stop: Thruster set to neutral position")
                
                # Stop PWM
                if self.rudder_pwm:
                    self.rudder_pwm.stop()
                    # Remove from global list
                    global _global_pwm_instances
                    if self.rudder_pwm in _global_pwm_instances:
                        _global_pwm_instances.remove(self.rudder_pwm)
                
                if self.thrust_pwm:
                    self.thrust_pwm.stop()
                    # Remove from global list
                    if self.thrust_pwm in _global_pwm_instances:
                        _global_pwm_instances.remove(self.thrust_pwm)
                    
                self.initialized = False
                logger.info("Boat motor control system shutdown complete")
                return True
            except Exception as e:
                logger.error(f"Error during motor controller cleanup: {e}")
                return False 
    
    def get_motor_status(self):
        """Get current motor controller status"""
        return {
            'rudder_position': self.current_rudder,
            'throttle': self.current_thrust,
            'initialized': self.initialized
        } 