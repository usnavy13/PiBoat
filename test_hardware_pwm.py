#!/usr/bin/env python3
from rpi_hardware_pwm import HardwarePWM
import time
import sys

# Define which Raspberry Pi model you have
# For Raspberry Pi 1/2/3/4, use CHIP = 0
# For Raspberry Pi 5, use CHIP = 0 for GPIO_12 and GPIO_13
#              or use CHIP = 2 for GPIO_18 and GPIO_19
CHIP = 2  # Using CHIP = 0 for Raspberry Pi 5 with GPIO_12 and GPIO_13

# Define PWM channels
# For Pi 1/2/3/4: Channel 0 = GPIO_18, Channel 1 = GPIO_1912

# For Pi 5: Channel 0 = GPIO_12, Channel 1 = GPIO_13 (if CHIP=0)
#          Channel 2 = GPIO_18, Channel 3 = GPIO_19 (if CHIP=2)
RUDDER_CHANNEL = 3 
THRUST_CHANNEL = 2    

# Define PWM frequency (Hz)
# Servo and ESC typically operate at 50Hz (20ms period)
PWM_FREQUENCY = 50

# Class to manage the hardware PWM instances
class PWMController:
    def __init__(self):
        self.rudder_pwm = None
        self.thrust_pwm = None
        self.initialized = False
        self.current_thrust = 0  # Keep track of current thrust level
    
    def initialize(self):
        try:
            # Initialize rudder PWM (servo)
            self.rudder_pwm = HardwarePWM(pwm_channel=RUDDER_CHANNEL, hz=PWM_FREQUENCY, chip=CHIP)
            self.rudder_pwm.start(0)  # Start with 0% duty cycle
            
            # Initialize thrust PWM (ESC)
            self.thrust_pwm = HardwarePWM(pwm_channel=THRUST_CHANNEL, hz=PWM_FREQUENCY, chip=CHIP)
            self.thrust_pwm.start(7.5)  # Start with neutral position (7.5% duty cycle = 1.5ms pulse)
            
            self.initialized = True
            print("Boat control system initialized")
            return True
        except Exception as e:
            print(f"Error initializing PWM: {e}")
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
    
    def set_rudder_position(self, degrees):
        """
        Set the rudder position based on degrees:
        -135 corresponds to full port (left) position (500µs pulse)
        0 corresponds to center position (1500µs pulse)
        135 corresponds to full starboard (right) position (2500µs pulse)
        
        Total range is 270 degrees.
        """
        if not self.initialized:
            print("Control system not initialized")
            return
            
        if degrees < -135 or degrees > 135:
            print("Rudder position must be between -135 and 135 degrees")
            return
        
        # Convert degrees to duty cycle
        duty_cycle = self.degrees_to_duty_cycle(degrees)
        
        # Set the PWM duty cycle
        self.rudder_pwm.change_duty_cycle(duty_cycle)
        print(f"Rudder: {degrees}° ({'port' if degrees < 0 else 'starboard' if degrees > 0 else 'center'})")
        
        # Give the servo time to move to position
        time.sleep(0.3)
    
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
    
    def set_thrust(self, speed, ramp_time=1.0, step_size=2.0):
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
            print("Control system not initialized")
            return
            
        if speed < -100 or speed > 100:
            print("Thrust must be between -100 and 100 percent")
            return
        
        # Check if there's a need to ramp (if speed change is significant)
        if abs(speed - self.current_thrust) <= step_size:
            duty_cycle = self.speed_to_duty_cycle(speed)
            self.thrust_pwm.change_duty_cycle(duty_cycle)
            self.current_thrust = speed
            print(f"Thrust: {speed}% ({'reverse' if speed < 0 else 'forward' if speed > 0 else 'stop'})")
            return
            
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
        print(f"Adjusting thrust from {self.current_thrust}% to {speed}%...")
        
        for i in range(1, num_steps + 1):
            # Calculate intermediate speed
            if i < num_steps:
                current = self.current_thrust + (i * step_size * step_direction)
            else:
                current = speed  # Ensure we end exactly at target speed
                
            # Apply the speed
            duty_cycle = self.speed_to_duty_cycle(current)
            self.thrust_pwm.change_duty_cycle(duty_cycle)
            
            # Only print progress at 25%, 50%, 75% and completion
            if i == num_steps or i % max(1, int(num_steps/4)) == 0:
                print(f"  Thrust: {current:.1f}%")
            
            # Wait before next step
            time.sleep(step_delay)
        
        # Update current thrust
        self.current_thrust = speed
        print(f"Thrust set to {speed}% ({'reverse' if speed < 0 else 'forward' if speed > 0 else 'stop'})")
    
    def cleanup(self):
        """Stop PWM and release resources"""
        if self.initialized:
            if self.rudder_pwm:
                self.rudder_pwm.stop()
            if self.thrust_pwm:
                self.thrust_pwm.stop()
            self.initialized = False
            print("Boat control system shutdown complete")


# Main program
if __name__ == "__main__":
    pwm_controller = PWMController()
    
    if not pwm_controller.initialize():
        print("Failed to initialize boat control system. Exiting...")
        sys.exit(1)
    
    # Main program loop for user input
    print("PiBoat Control System")
    print("\nMenu Options:")
    print("1 - Control Rudder")
    print("2 - Control Propeller Thrust")
    print("q - Quit program")
    
    try:
        while True:
            # Get mode selection
            mode = input("\nSelect mode (1-Rudder, 2-Thrust, q-Quit): ")
            
            if mode.lower() == 'q':
                break
            
            elif mode == '1':
                # Rudder control mode
                print("\nRudder Control Mode:")
                print("  Range: -135 to 135 degrees")
                print("  -135 = full port (left)")
                print("  0 = center")
                print("  135 = full starboard (right)")
                print("  Enter 'b' to go back to main menu")
                
                while True:
                    position_input = input("\nEnter rudder position (-135 to 135 degrees): ")
                    
                    if position_input.lower() == 'b':
                        break
                    
                    try:
                        degrees = float(position_input)
                        pwm_controller.set_rudder_position(degrees)
                    except ValueError:
                        print("Invalid input. Please enter a number between -135 and 135.")
            
            elif mode == '2':
                # Thrust control mode
                print("\nPropeller Thrust Control:")
                print("  Range: -100 to 100 percent")
                print("  -100 = full reverse")
                print("  0 = stop")
                print("  100 = full forward")
                print("  Enter 'b' to go back to main menu")
                print("  Enter format: 'thrust [ramp_time]' (e.g., '50 2.5' for 50% over 2.5 seconds)")
                
                while True:
                    thrust_input = input("\nEnter thrust (-100 to 100 percent) [optional: ramp time in seconds]: ")
                    
                    if thrust_input.lower() == 'b':
                        break
                    
                    try:
                        parts = thrust_input.split()
                        thrust = float(parts[0])
                        
                        # Check if ramp time was provided
                        ramp_time = 1.0  # Default ramp time
                        if len(parts) > 1:
                            ramp_time = float(parts[1])
                            
                        pwm_controller.set_thrust(thrust, ramp_time)
                    except ValueError:
                        print("Invalid input. Please enter a number between -100 and 100.")
            
            else:
                print("Invalid option. Please select 1, 2, or q.")
    
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
        
    finally:
        # Clean up no matter what
        pwm_controller.cleanup() 