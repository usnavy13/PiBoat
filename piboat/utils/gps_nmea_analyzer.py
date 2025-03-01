#!/usr/bin/env python3
"""
Advanced script to read and interpret raw NMEA data from the GPS device.
This script will show raw NMEA sentences and provide basic interpretation
of common sentence types (GGA, RMC, GSV, etc.).
"""

import serial
import time
import argparse
import sys
import re
from datetime import datetime

# NMEA sentence interpreters
def parse_gga(parts):
    """Parse GGA sentence (Global Positioning System Fix Data)"""
    if len(parts) < 15:
        return "Invalid GGA sentence (too few parts)"
    
    try:
        time_str = parts[1]
        lat = parts[2]
        lat_dir = parts[3]
        lon = parts[4]
        lon_dir = parts[5]
        fix_quality = parts[6]
        satellites = parts[7]
        hdop = parts[8]
        altitude = parts[9]
        altitude_units = parts[10]
        
        # Format latitude and longitude if present
        lat_str = "N/A"
        lon_str = "N/A"
        if lat and lon:
            lat_deg = float(lat[:2])
            lat_min = float(lat[2:])
            lat_decimal = lat_deg + lat_min / 60
            if lat_dir == "S":
                lat_decimal = -lat_decimal
                
            lon_deg = float(lon[:3])
            lon_min = float(lon[3:])
            lon_decimal = lon_deg + lon_min / 60
            if lon_dir == "W":
                lon_decimal = -lon_decimal
                
            lat_str = f"{lat_decimal:.6f}° {lat_dir}"
            lon_str = f"{lon_decimal:.6f}° {lon_dir}"
        
        # Fix quality interpretation
        fix_types = {
            "0": "No fix",
            "1": "GPS fix",
            "2": "DGPS fix",
            "3": "PPS fix",
            "4": "Real Time Kinematic",
            "5": "Float RTK",
            "6": "Estimated",
            "7": "Manual input",
            "8": "Simulation"
        }
        
        fix_desc = fix_types.get(fix_quality, f"Unknown ({fix_quality})")
        
        return f"""
  Time: {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]} UTC
  Position: {lat_str}, {lon_str}
  Fix: {fix_desc}
  Satellites: {satellites}
  HDOP: {hdop}
  Altitude: {altitude} {altitude_units}
"""
    except Exception as e:
        return f"Error parsing GGA: {str(e)}"

def parse_rmc(parts):
    """Parse RMC sentence (Recommended Minimum Navigation Information)"""
    if len(parts) < 12:
        return "Invalid RMC sentence (too few parts)"
    
    try:
        time_str = parts[1]
        status = parts[2]  # A=active, V=void
        lat = parts[3]
        lat_dir = parts[4]
        lon = parts[5]
        lon_dir = parts[6]
        speed = parts[7]
        course = parts[8]
        date = parts[9]
        
        # Format date if present
        date_str = "N/A"
        if date:
            day = date[:2]
            month = date[2:4]
            year = date[4:6]
            date_str = f"20{year}-{month}-{day}"
        
        # Status interpretation
        status_desc = "Active" if status == "A" else "Void (warning)"
        
        return f"""
  Status: {status_desc}
  Date: {date_str}
  Time: {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]} UTC
  Speed: {speed} knots
  Course: {course}°
"""
    except Exception as e:
        return f"Error parsing RMC: {str(e)}"

def parse_gsv(parts):
    """Parse GSV sentence (Satellites in View)"""
    if len(parts) < 4:
        return "Invalid GSV sentence (too few parts)"
    
    try:
        total_msgs = parts[1]
        msg_num = parts[2]
        satellites_in_view = parts[3]
        
        satellite_info = []
        
        # Each satellite takes 4 fields: PRN, elevation, azimuth, SNR
        for i in range(4, len(parts), 4):
            if i+3 < len(parts):
                prn = parts[i]
                elevation = parts[i+1]
                azimuth = parts[i+2]
                snr = parts[i+3]
                
                if prn:
                    sat_str = f"Satellite #{prn}: Elevation {elevation}°, Azimuth {azimuth}°, SNR {snr}dB"
                    satellite_info.append(sat_str)
        
        satellites_str = "\n    ".join(satellite_info) if satellite_info else "None"
        
        return f"""
  Message: {msg_num} of {total_msgs}
  Satellites in view: {satellites_in_view}
  Satellite details:
    {satellites_str}
"""
    except Exception as e:
        return f"Error parsing GSV: {str(e)}"

def parse_gsa(parts):
    """Parse GSA sentence (GPS DOP and active satellites)"""
    if len(parts) < 18:
        return "Invalid GSA sentence (too few parts)"
    
    try:
        mode1 = parts[1]  # M=Manual, A=Automatic
        mode2 = parts[2]  # Fix type: 1=no fix, 2=2D, 3=3D
        
        # Get all active satellite PRNs
        active_sats = []
        for i in range(3, 15):
            if i < len(parts) and parts[i]:
                active_sats.append(parts[i])
        
        # Position dilution of precision
        pdop = parts[15] if len(parts) > 15 else "N/A"
        hdop = parts[16] if len(parts) > 16 else "N/A"
        vdop = parts[17] if len(parts) > 17 else "N/A"
        
        # Mode interpretations
        mode1_desc = "Automatic" if mode1 == "A" else "Manual" if mode1 == "M" else f"Unknown ({mode1})"
        
        mode2_map = {
            "1": "No Fix",
            "2": "2D Fix",
            "3": "3D Fix"
        }
        mode2_desc = mode2_map.get(mode2, f"Unknown ({mode2})")
        
        return f"""
  Mode: {mode1_desc}, Fix Type: {mode2_desc}
  Active Satellites: {', '.join(active_sats) if active_sats else 'None'}
  PDOP: {pdop}, HDOP: {hdop}, VDOP: {vdop}
"""
    except Exception as e:
        return f"Error parsing GSA: {str(e)}"

def parse_vtg(parts):
    """Parse VTG sentence (Track Made Good and Ground Speed)"""
    if len(parts) < 10:
        return "Invalid VTG sentence (too few parts)"
    
    try:
        track_true = parts[1]  # Course in degrees True
        track_magnetic = parts[3]  # Course in degrees Magnetic
        speed_knots = parts[5]  # Speed in knots
        speed_kmh = parts[7]  # Speed in km/h
        
        return f"""
  Course (True): {track_true}°
  Course (Magnetic): {track_magnetic}°
  Speed: {speed_knots} knots, {speed_kmh} km/h
"""
    except Exception as e:
        return f"Error parsing VTG: {str(e)}"

def parse_gll(parts):
    """Parse GLL sentence (Geographic Position - Latitude/Longitude)"""
    if len(parts) < 7:
        return "Invalid GLL sentence (too few parts)"
    
    try:
        lat = parts[1]
        lat_dir = parts[2]
        lon = parts[3]
        lon_dir = parts[4]
        time_str = parts[5]
        status = parts[6]  # A=active, V=void
        
        # Format latitude and longitude if present
        lat_str = "N/A"
        lon_str = "N/A"
        if lat and lon:
            lat_deg = float(lat[:2])
            lat_min = float(lat[2:])
            lat_decimal = lat_deg + lat_min / 60
            if lat_dir == "S":
                lat_decimal = -lat_decimal
                
            lon_deg = float(lon[:3])
            lon_min = float(lon[3:])
            lon_decimal = lon_deg + lon_min / 60
            if lon_dir == "W":
                lon_decimal = -lon_decimal
                
            lat_str = f"{lat_decimal:.6f}° {lat_dir}"
            lon_str = f"{lon_decimal:.6f}° {lon_dir}"
        
        # Status interpretation
        status_desc = "Active" if status == "A" else "Void (warning)"
        
        return f"""
  Position: {lat_str}, {lon_str}
  Time: {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]} UTC
  Status: {status_desc}
"""
    except Exception as e:
        return f"Error parsing GLL: {str(e)}"

# Main NMEA parser
def parse_nmea(sentence):
    if not sentence.startswith('$'):
        return None, "Not a valid NMEA sentence (missing $ prefix)"
    
    # Verify checksum if present
    checksum_valid = True
    checksum_message = "No checksum"
    
    if '*' in sentence:
        sentence_parts = sentence.split('*')
        if len(sentence_parts) == 2:
            sentence_body = sentence_parts[0][1:]  # Remove the leading $
            checksum_hex = sentence_parts[1][:2]  # Get only the first two chars after *
            
            # Calculate checksum
            calculated_checksum = 0
            for char in sentence_body:
                calculated_checksum ^= ord(char)
            
            # Compare checksums
            try:
                if int(checksum_hex, 16) != calculated_checksum:
                    checksum_valid = False
                    checksum_message = f"Invalid (got {checksum_hex}, calculated {calculated_checksum:02X})"
                else:
                    checksum_message = "Valid"
            except ValueError:
                checksum_valid = False
                checksum_message = f"Invalid format: {checksum_hex}"
    
    # Parse the sentence type
    parts = sentence.split(',')
    if not parts:
        return None, "Empty NMEA sentence"
    
    sentence_type = parts[0][1:]  # Remove the $ prefix
    
    # Determine parser based on sentence type
    if sentence_type.endswith('GGA'):
        parser = parse_gga
    elif sentence_type.endswith('RMC'):
        parser = parse_rmc
    elif sentence_type.endswith('GSV'):
        parser = parse_gsv
    elif sentence_type.endswith('GSA'):
        parser = parse_gsa
    elif sentence_type.endswith('VTG'):
        parser = parse_vtg
    elif sentence_type.endswith('GLL'):
        parser = parse_gll
    else:
        return sentence_type, f"No detailed parser available for {sentence_type}"
    
    # Parse the sentence
    parsed_info = parser(parts)
    
    return sentence_type, parsed_info, checksum_message

def main():
    parser = argparse.ArgumentParser(description='Read and analyze raw GPS NMEA data')
    parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port for GPS device')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for serial connection')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    parser.add_argument('--raw-only', action='store_true', help='Show only raw NMEA sentences without interpretation')
    parser.add_argument('--hex', action='store_true', help='Show hex representation of each byte')
    parser.add_argument('--filter', help='Show only specific sentence types (comma-separated, e.g. GGA,RMC)')
    args = parser.parse_args()
    
    # Process filter argument
    sentence_filters = None
    if args.filter:
        sentence_filters = [f.strip().upper() for f in args.filter.split(',')]
    
    print(f"Opening GPS device on {args.port} at {args.baudrate} baud")
    
    try:
        # Open serial connection directly
        ser = serial.Serial(args.port, args.baudrate, timeout=1)
        
        print("Connection established.")
        if sentence_filters:
            print(f"Filtering for sentence types: {', '.join(sentence_filters)}")
        print("Reading NMEA sentences. Press Ctrl+C to exit.")
        print("=" * 80)
        
        start_time = time.time()
        while time.time() - start_time < args.duration:
            # Read a line from the serial port
            try:
                raw_line = ser.readline()
                
                # If no data, continue
                if not raw_line:
                    time.sleep(0.1)
                    continue
                
                # If hex view requested, show hex representation
                if args.hex:
                    hex_data = ' '.join([f"{b:02x}" for b in raw_line])
                    print(f"HEX: {hex_data}")
                
                # Try to decode as ASCII (NMEA uses ASCII)
                try:
                    line = raw_line.decode('ascii', errors='replace').strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Print raw NMEA
                    print(f"NMEA: {line}")
                    
                    # Parse and interpret if not in raw-only mode
                    if not args.raw_only and line.startswith('$'):
                        try:
                            sentence_type, parsed_info, checksum_info = parse_nmea(line)
                            
                            # Apply filtering if requested
                            if sentence_filters and not any(f in sentence_type for f in sentence_filters):
                                print("-" * 80)
                                continue
                            
                            print(f"Type: {sentence_type}, Checksum: {checksum_info}")
                            print(f"Interpretation: {parsed_info}")
                        except Exception as e:
                            print(f"Parser error: {str(e)}")
                    
                    print("-" * 80)
                    
                except UnicodeDecodeError:
                    print(f"Could not decode: {raw_line}")
                    print("-" * 80)
                    
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