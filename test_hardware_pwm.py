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
SERVO_CHANNEL = 2  # Using Channel 0 for GPIO_12 on Pi 5
ESC_CHANNEL = 3    # Using Channel 1 for GPIO_13 on Pi 5

# Define PWM frequency (Hz)
# Servo and ESC typically operate at 50Hz (20ms period)
PWM_FREQUENCY = 50

# Class to manage the hardware PWM instances
class PWMController:
    def __init__(self):
        self.servo_pwm = None
        self.esc_pwm = None
        self.initialized = False
    
    def initialize(self):
        try:
            # Initialize servo PWM
            self.servo_pwm = HardwarePWM(pwm_channel=SERVO_CHANNEL, hz=PWM_FREQUENCY, chip=CHIP)
            self.servo_pwm.start(0)  # Start with 0% duty cycle
            
            # Initialize ESC PWM
            self.esc_pwm = HardwarePWM(pwm_channel=ESC_CHANNEL, hz=PWM_FREQUENCY, chip=CHIP)
            self.esc_pwm.start(7.5)  # Start with neutral position (7.5% duty cycle = 1.5ms pulse)
            
            self.initialized = True
            print("PWM controller initialized successfully")
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
    
    def set_servo_position(self, degrees):
        """
        Set the servo position based on degrees:
        -135 corresponds to minimum position (500µs pulse)
        0 corresponds to center position (1500µs pulse)
        135 corresponds to maximum position (2500µs pulse)
        
        Total range is 270 degrees.
        """
        if not self.initialized:
            print("PWM controller not initialized")
            return
            
        if degrees < -135 or degrees > 135:
            print("Position must be between -135 and 135 degrees")
            return
        
        # Convert degrees to duty cycle
        duty_cycle = self.degrees_to_duty_cycle(degrees)
        
        # Set the PWM duty cycle
        self.servo_pwm.change_duty_cycle(duty_cycle)
        
        pulse_width = duty_cycle/100*20000
        print(f"Servo moved to {degrees} degrees (duty cycle: {duty_cycle:.2f}%, pulse width: {pulse_width:.0f}µs)")
        
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
    
    def set_esc_speed(self, speed):
        """
        Set the ESC speed based on percentage:
        -100 corresponds to full reverse (1000µs pulse)
        0 corresponds to neutral/stop (1500µs pulse)
        100 corresponds to full forward (2000µs pulse)
        """
        if not self.initialized:
            print("PWM controller not initialized")
            return
            
        if speed < -100 or speed > 100:
            print("Speed must be between -100 and 100 percent")
            return
        
        # Convert speed to duty cycle
        duty_cycle = self.speed_to_duty_cycle(speed)
        
        # Set the PWM duty cycle
        self.esc_pwm.change_duty_cycle(duty_cycle)
        
        pulse_width = duty_cycle/100*20000
        print(f"ESC set to {speed}% speed (duty cycle: {duty_cycle:.2f}%, pulse width: {pulse_width:.0f}µs)")
        
        # Give the ESC time to adjust
        time.sleep(0.1)
    
    def cleanup(self):
        """Stop PWM and release resources"""
        if self.initialized:
            if self.servo_pwm:
                self.servo_pwm.stop()
            if self.esc_pwm:
                self.esc_pwm.stop()
            self.initialized = False
            print("PWM controller cleanup complete")


# Main program
if __name__ == "__main__":
    pwm_controller = PWMController()
    
    if not pwm_controller.initialize():
        print("Failed to initialize PWM controller. Exiting...")
        sys.exit(1)
    
    # Main program loop for user input
    print("Hardware PWM Control Program for 270° Servo and Bi-directional ESC")
    print("\nMenu Options:")
    print("1 - Control Servo")
    print("2 - Control ESC (Propeller)")
    print("q - Quit program")
    
    try:
        while True:
            # Get mode selection
            mode = input("\nSelect mode (1-Servo, 2-ESC, q-Quit): ")
            
            if mode.lower() == 'q':
                break
            
            elif mode == '1':
                # Servo control mode
                print("\nServo Control Mode:")
                print("  Range: -135 to 135 degrees")
                print("  -135 = minimum position (500µs pulse)")
                print("  0 = center position (1500µs pulse)")
                print("  135 = maximum position (2500µs pulse)")
                print("  Enter 'b' to go back to main menu")
                
                while True:
                    position_input = input("\nEnter servo position (-135 to 135 degrees): ")
                    
                    if position_input.lower() == 'b':
                        break
                    
                    try:
                        degrees = float(position_input)
                        pwm_controller.set_servo_position(degrees)
                    except ValueError:
                        print("Invalid input. Please enter a number between -135 and 135.")
            
            elif mode == '2':
                # ESC control mode
                print("\nESC Control Mode (Propeller):")
                print("  Range: -100 to 100 percent")
                print("  -100 = full reverse (1000µs pulse)")
                print("  0 = stop/neutral (1500µs pulse)")
                print("  100 = full forward (2000µs pulse)")
                print("  Enter 'b' to go back to main menu")
                
                while True:
                    speed_input = input("\nEnter ESC speed (-100 to 100 percent): ")
                    
                    if speed_input.lower() == 'b':
                        break
                    
                    try:
                        speed = float(speed_input)
                        pwm_controller.set_esc_speed(speed)
                    except ValueError:
                        print("Invalid input. Please enter a number between -100 and 100.")
            
            else:
                print("Invalid option. Please select 1, 2, or q.")
    
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
        
    finally:
        # Clean up no matter what
        pwm_controller.cleanup() 