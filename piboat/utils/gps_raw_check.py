#!/usr/bin/env python3
"""
Simple script to read raw data directly from the GPS device.
This bypasses any handlers and shows the raw NMEA sentences.
"""

import serial
import time
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='Read raw GPS data')
    parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port for GPS device')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for serial connection')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    parser.add_argument('--verbose', action='store_true', help='Show hex representation of each byte')
    args = parser.parse_args()
    
    print(f"Opening GPS device on {args.port} at {args.baudrate} baud")
    
    try:
        # Open serial connection directly
        ser = serial.Serial(args.port, args.baudrate, timeout=1)
        
        print("Connection established. Reading raw NMEA sentences...")
        print("Press Ctrl+C to exit")
        print("-" * 60)
        
        start_time = time.time()
        while time.time() - start_time < args.duration:
            # Read a line from the serial port
            try:
                raw_line = ser.readline()
                
                # If verbose, show hex representation
                if args.verbose:
                    hex_data = ' '.join([f"{b:02x}" for b in raw_line])
                    print(f"HEX: {hex_data}")
                
                # Try to decode as ASCII/UTF-8 (NMEA uses ASCII)
                try:
                    line = raw_line.decode('ascii', errors='replace').strip()
                    print(f"NMEA: {line}")
                except UnicodeDecodeError:
                    print(f"Could not decode: {raw_line}")
                    
            except serial.SerialException as e:
                print(f"Serial error: {e}")
                break
                
            # A short delay to not flood the console
            time.sleep(0.01)
            
    except serial.SerialException as e:
        print(f"Failed to open serial port: {e}")
        return
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial connection closed")
        
    print("Test completed")

if __name__ == "__main__":
    main() 