"""
AI Field Analyzer v2.0 - FIXED GPS Anti-Spoofing Sensor Management System
-----------------------------------------------------------------------------------
CPU performance optimized version with BMP390 support and GPS anti-spoofing.
- BMP390 polling reduced to 20 seconds
- Cached calculations for expensive operations
- GPS anti-spoofing with confidence levels
- GPS-Pressure altitude fusion for spoofing detection
- Real-time GPS time synchronization
- FIXED: GPS location detector variable reference errors

© 2025 Apollo Timbers. MIT License.
"""

import time
import board
import busio
import digitalio
import microcontroller
import adafruit_scd4x
import adafruit_tsl2591
import adafruit_bmp3xx
import gc
import struct
import math

# =============================================================================
# GPS ANTI-SPOOFING MODULE
# =============================================================================

class GPSParser:
    def __init__(self, i2c, address=0x42):
        self.i2c = i2c
        self.address = address
        self.latitude = None
        self.longitude = None
        self.satellites = 0
        self.satellites_tracked = 0
        self.has_fix = False
        self.buffer = ""
        self.debug_msg = "Starting..."
        self.fix_quality = "0"
        self.altitude_m = 0
        self.speed_knots = 0
        self.course = None
        self.hdop = 99.9
        self.last_positions = []
        self.signal_strength = []
        self.confidence_level = 0
        self.gps_time = None
        self.date = None
        self.raw_confidence = 0
        self.altitude_comparison = None

    def read_data(self):
        try:
            while not self.i2c.try_lock():
                time.sleep(0.01)
            try:
                result = bytearray(255)
                self.i2c.readfrom_into(self.address, result)
                
                text = ""
                for b in result:
                    if b != 0 and 32 <= b <= 126:
                        text += chr(b)
                    elif b == 10 or b == 13:
                        text += chr(b)
                
                self.buffer += text
                
                while '\n' in self.buffer:
                    newline_pos = self.buffer.find('\n')
                    line = self.buffer[:newline_pos]
                    self.buffer = self.buffer[newline_pos+1:]
                    line = line.strip()
                    if line.startswith('$'):
                        self.process_line(line)
            finally:
                self.i2c.unlock()
            return True
        except Exception as e:
            self.debug_msg = f"I2C error: {str(e)[:15]}"
            try:
                self.i2c.unlock()
            except:
                pass
            return False

    def process_line(self, line):
        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
            self.parse_gga(line)
        elif line.startswith('$GPGSV') or line.startswith('$GNGSV'):
            self.parse_gsv(line)
        elif line.startswith('$GPRMC') or line.startswith('$GNRMC'):
            self.parse_rmc(line)
        
        self.update_confidence()

    def parse_gga(self, sentence):
        try:
            parts = sentence.split(',')
            if len(parts) < 15:
                self.debug_msg = f"GGA short: {len(parts)}"
                return

            if parts[1] and len(parts[1]) >= 6:
                time_str = parts[1]
                hour = int(time_str[:2])
                minute = int(time_str[2:4])
                second = int(time_str[4:6])
                self.gps_time = f"{hour:02d}:{minute:02d}:{second:02d}"

            self.fix_quality = parts[6]
            self.has_fix = self.fix_quality in ['1', '2', '3', '4', '5', '6']
            
            if self.fix_quality == '0':
                self.debug_msg = "No fix - searching"
            elif self.fix_quality == '1':
                self.debug_msg = "GPS fix OK!"
            else:
                self.debug_msg = f"Fix quality: {self.fix_quality}"

            if parts[7]:
                self.satellites = int(parts[7])

            if parts[8]:
                self.hdop = float(parts[8])

            if parts[9]:
                self.altitude_m = float(parts[9])

            lat_str = parts[2]
            lat_dir = parts[3]
            if lat_str and lat_dir:
                lat_deg = float(lat_str[:2])
                lat_min = float(lat_str[2:])
                new_lat = lat_deg + lat_min / 60.0
                if lat_dir == 'S':
                    new_lat = -new_lat
                
                if self.latitude is not None:
                    self.last_positions.append((self.latitude, self.longitude, time.time()))
                    if len(self.last_positions) > 10:
                        self.last_positions.pop(0)
                
                self.latitude = new_lat

            lon_str = parts[4]
            lon_dir = parts[5]
            if lon_str and lon_dir:
                lon_deg = float(lon_str[:3])
                lon_min = float(lon_str[3:])
                self.longitude = lon_deg + lon_min / 60.0
                if lon_dir == 'W':
                    self.longitude = -self.longitude
                
        except Exception as e:
            self.debug_msg = f"GGA error: {str(e)[:12]}"

    def parse_gsv(self, sentence):
        try:
            parts = sentence.split(',')
            if len(parts) >= 4 and parts[3]:
                self.satellites_tracked = int(parts[3])
            
            if len(parts) >= 8:
                for i in range(7, len(parts), 4):
                    if i < len(parts) and parts[i]:
                        try:
                            snr = int(parts[i])
                            self.signal_strength.append(snr)
                            if len(self.signal_strength) > 20:
                                self.signal_strength.pop(0)
                        except:
                            pass
        except:
            pass

    def parse_rmc(self, sentence):
        try:
            parts = sentence.split(',')
            if len(parts) >= 10:
                if parts[7]:
                    self.speed_knots = float(parts[7])
                
                if parts[8]:
                    self.course = float(parts[8])
                
                if parts[9] and len(parts[9]) == 6:
                    date_str = parts[9]
                    day = int(date_str[:2])
                    month = int(date_str[2:4])
                    year = 2000 + int(date_str[4:6])
                    self.date = f"{day:02d}/{month:02d}/{year}"
        except:
            pass

    def update_confidence(self):
        confidence = 100
        threats = []
        
        if self.latitude and self.longitude:
            if abs(self.latitude) > 90 or abs(self.longitude) > 180:
                confidence -= 30
                threats.append("BAD_COORDS")
        
        if self.altitude_m > 50000 or self.altitude_m < -500:
            confidence -= 20
            threats.append("BAD_ALT")
        
        if self.speed_knots > 1000:
            confidence -= 20
            threats.append("BAD_SPEED")
        
        if self.has_fix and self.satellites < 4:
            confidence -= 25
            threats.append("LOW_SATS")
        
        if self.hdop > 10:
            confidence -= 15
            threats.append("HIGH_HDOP")
        elif self.hdop > 5:
            confidence -= 5
        
        if len(self.signal_strength) > 5:
            avg_snr = sum(self.signal_strength) / len(self.signal_strength)
            if avg_snr < 10:
                confidence -= 20
                threats.append("WEAK_SIG")
            elif avg_snr < 20:
                confidence -= 10
        
        if len(self.last_positions) > 3:
            pos1 = self.last_positions[-1]
            pos2 = self.last_positions[-3]
            if pos1[2] - pos2[2] > 0:
                lat_diff = abs(pos1[0] - pos2[0])
                lon_diff = abs(pos1[1] - pos2[1])
                distance = (lat_diff * lat_diff + lon_diff * lon_diff) ** 0.5
                time_diff = pos1[2] - pos2[2]
                speed_calc = distance * 111000 / time_diff
                if speed_calc > 200:
                    confidence -= 15
                    threats.append("FAST_MOVE")
        
        self.raw_confidence = confidence
        self.confidence_level = max(0, min(100, confidence))
        
        if self.confidence_level >= 90:
            self.debug_msg = "HIGH confidence"
        elif self.confidence_level >= 70:
            self.debug_msg = "MEDIUM confidence"
        elif self.confidence_level >= 50:
            self.debug_msg = "LOW confidence"
        else:
            self.debug_msg = f"THREAT: {threats[0] if threats else 'UNKNOWN'}"

    def update_confidence_with_pressure_fusion(self, pressure_altitude_m, pressure_sensor_healthy):
        confidence = self.raw_confidence
        threats = []
        
        if (pressure_sensor_healthy and 
            pressure_altitude_m is not None and 
            self.altitude_m is not None and 
            self.has_fix):
            
            altitude_diff = abs(self.altitude_m - pressure_altitude_m)
            
            if altitude_diff > 1000:
                confidence -= 25
                threats.append("ALT_SPOOF_MAJOR")
                self.debug_msg = f"MAJOR altitude spoofing: {altitude_diff:.0f}m diff"
            elif altitude_diff > 500:
                confidence -= 15
                threats.append("ALT_SPOOF_MOD")
                self.debug_msg = f"Moderate altitude spoofing: {altitude_diff:.0f}m diff"
            elif altitude_diff > 200:
                confidence -= 8
                threats.append("ALT_SPOOF_MIN")
                self.debug_msg = f"Minor altitude spoofing: {altitude_diff:.0f}m diff"
            elif altitude_diff > 100:
                confidence -= 3
                threats.append("ALT_SUSPICIOUS")
            else:
                confidence += 2
                confidence = min(100, confidence)
        
        self.confidence_level = max(0, min(100, confidence))
        
        self.altitude_comparison = {
            'gps_altitude': self.altitude_m,
            'pressure_altitude': pressure_altitude_m,
            'difference': abs(self.altitude_m - pressure_altitude_m) if (self.altitude_m and pressure_altitude_m) else None,
            'pressure_sensor_healthy': pressure_sensor_healthy,
            'fusion_active': pressure_sensor_healthy and pressure_altitude_m is not None
        }
        
        return threats

    def apply_pressure_fusion(self, pressure_altitude_m, pressure_sensor_healthy):
        return self.update_confidence_with_pressure_fusion(pressure_altitude_m, pressure_sensor_healthy)

# =============================================================================
# GPS HELPER FUNCTIONS
# =============================================================================

def init_gps():
    try:
        # This function is now deprecated - GPS uses shared I2C bus
        print("⚠️ init_gps() deprecated - GPS now uses shared I2C bus")
        return None
    except Exception as e:
        print(f"GPS initialization error: {e}")
        return None

def get_gps_data(gps):
    if not gps:
        return None
    
    try:
        if gps.read_data():
            return {
                'latitude': gps.latitude,
                'longitude': gps.longitude,
                'altitude_m': gps.altitude_m,
                'speed_knots': gps.speed_knots,
                'course': gps.course,
                'satellites': gps.satellites,
                'satellites_tracked': gps.satellites_tracked,
                'has_fix': gps.has_fix,
                'fix_quality': gps.fix_quality,
                'hdop': gps.hdop,
                'confidence_level': gps.confidence_level,
                'gps_time': gps.gps_time,
                'date': gps.date,
                'debug_msg': gps.debug_msg
            }
        else:
            return None
    except Exception as e:
        print(f"GPS read error: {e}")
        return None

# =============================================================================
# FIXED GPS LOCATION DETECTOR
# =============================================================================
class GPSLocationDetector:
    def __init__(self):
        self.gps_history = []
        self.current_satellites = 0
        self.current_speed_kmh = 0.0
        self.current_location = "OUTDOOR"
        self.location_confidence = 50
        self.movement_confidence = 0
        self.last_update = 0
        self.MAX_HISTORY = 10
        self.lux_history = []
        self.co2_history = []
        self.force_location = None
        self.force_until = 0
        self.last_vehicle_time = 0
        self.last_vehicle_coords = None
        self.vehicle_sticky_duration = 30  # seconds to hold vehicle mode after stopping
        self.vehicle_sticky_distance = 1.5  # meters threshold to drop vehicle mode

        # Enhanced sensor fusion data
        self.current_co2 = 400
        self.current_lux = 0
        self.current_pressure = 1013.25
        self.current_humidity = 50
        self.location_history = []
        self.MAX_LOCATION_HISTORY = 5
        
        # FIXED: Initialize GPS coordinates properly
        self.current_latitude = None
        self.current_longitude = None

        self.LOCATION_STRINGS = {
            "OUTDOOR": "OUTDOOR",
            "INDOOR": "INDOOR",
            "VEHICLE": "VEHICLE",
            "CAVE": "CAVE"
        }

        print("📍 Enhanced GPS Location Detector initialized")

    def update_gps_data(self, satellites, speed_kmh, co2=400, lux=0, humidity=50.0, pressure_hpa=1013.25, latitude=None, longitude=None):
        """
        Enhanced location detection with explicit, verbose multi-sensor fusion.
        FIXED: Added latitude/longitude parameters to prevent variable reference errors
        """
        current_time = time.monotonic()
        
        # FIXED: Update GPS coordinates if provided
        if latitude is not None:
            self.current_latitude = latitude
        if longitude is not None:
            self.current_longitude = longitude

        # Track histories for delta checks
        self.lux_history.append((current_time, lux))
        self.co2_history.append((current_time, co2))

        # Keep only last 5 entries
        if len(self.lux_history) > 5:
            self.lux_history.pop(0)
        if len(self.co2_history) > 5:
            self.co2_history.pop(0)

        # --- Force OUTDOOR if GPS sats high and lux increases fast ---
        if satellites >= 10 and len(self.lux_history) >= 2:
            dt = self.lux_history[-1][0] - self.lux_history[-2][0]
            d_lux = self.lux_history[-1][1] - self.lux_history[-2][1]
            if dt <= 2.5 and d_lux > 1000:
                self.force_location = "OUTDOOR"
                self.force_until = current_time + 5  # seconds to hold override
                print("🟩 Hard override: OUTDOOR (lux jump + GPS)")

        # --- Force INDOOR if CO2 jumps fast ---
        if len(self.co2_history) >= 2:
            dt = self.co2_history[-1][0] - self.co2_history[-2][0]
            d_co2 = self.co2_history[-1][1] - self.co2_history[-2][1]
            if dt <= 3.5 and d_co2 > 300:
                self.force_location = "INDOOR"
                self.force_until = current_time + 5
                print("🟥 Hard override: INDOOR (CO2 jump)")

        self.current_satellites = satellites
        self.current_speed_kmh = speed_kmh
        self.current_co2 = co2
        self.current_lux = lux
        self.current_humidity = humidity
        self.current_pressure = pressure_hpa

        if len(self.gps_history) >= self.MAX_HISTORY:
            self.gps_history.pop(0)
        self.gps_history.append((current_time, satellites, speed_kmh))

        location_scores = {
            "OUTDOOR": 0,
            "INDOOR": 0,
            "VEHICLE": 0,
            "CAVE": 0
        }
        debug = []

        # -------- Speed (PRIMARY, 35%) --------
        if speed_kmh > 12:
            location_scores["VEHICLE"] += 35
            debug.append("Speed: VEHICLE (+35)")
        elif speed_kmh > 8:
            location_scores["VEHICLE"] += 25
            location_scores["OUTDOOR"] += 7
            debug.append("Speed: likely VEHICLE (+25), possibly OUTDOOR (+7)")
        elif speed_kmh > 5:
            location_scores["OUTDOOR"] += 22
            debug.append("Speed: brisk OUTDOOR (+22)")
        elif speed_kmh > 2:
            location_scores["OUTDOOR"] += 12
            location_scores["INDOOR"] += 3
            debug.append("Speed: walking OUTDOOR (+12), maybe INDOOR (+3)")
        else:
            location_scores["INDOOR"] += 10
            location_scores["OUTDOOR"] += 6
            debug.append("Speed: stationary, INDOOR (+10), possible OUTDOOR (+6)")

        # -------- CO2 (MODERATE, 15%) --------
        if co2 > 1800:
            location_scores["INDOOR"] += 15
            debug.append("CO2: very high, INDOOR (+15)")
        elif co2 > 1200:
            location_scores["INDOOR"] += 10
            location_scores["VEHICLE"] += 3
            debug.append("CO2: high, INDOOR (+10), possible VEHICLE (+3)")
        elif co2 > 800:
            location_scores["INDOOR"] += 5
            location_scores["OUTDOOR"] += 4
            debug.append("CO2: moderate, INDOOR (+5), OUTDOOR (+4)")
        else:
            location_scores["OUTDOOR"] += 7
            debug.append("CO2: low, OUTDOOR (+7)")

        # -------- Light (MODERATE, 15%) --------
        if lux > 15000:
            location_scores["OUTDOOR"] += 15
            debug.append("Light: very bright, OUTDOOR (+15)")
        elif lux > 3000:
            location_scores["OUTDOOR"] += 8
            location_scores["INDOOR"] += 2
            debug.append("Light: bright, OUTDOOR (+8), possible INDOOR (+2)")
        elif lux > 300:
            location_scores["INDOOR"] += 7
            location_scores["OUTDOOR"] += 2
            debug.append("Light: indoor levels, INDOOR (+7), possible OUTDOOR (+2)")
        elif lux > 50:
            location_scores["INDOOR"] += 6
            location_scores["CAVE"] += 2
            debug.append("Light: dim, INDOOR (+6), possible CAVE (+2)")
        else:
            location_scores["CAVE"] += 10
            debug.append("Light: very dark, CAVE (+10)")

        # -------- Humidity (15%) --------
        if humidity > 65:
            location_scores["OUTDOOR"] += 11
            debug.append("Humidity: high, OUTDOOR (+11)")
        elif humidity > 50:
            location_scores["OUTDOOR"] += 7
            location_scores["INDOOR"] += 2
            debug.append("Humidity: moderate, OUTDOOR (+7), possible INDOOR (+2)")
        elif humidity > 35:
            location_scores["INDOOR"] += 10
            debug.append("Humidity: low, INDOOR (+10)")
        else:
            location_scores["INDOOR"] += 8
            location_scores["CAVE"] += 3
            debug.append("Humidity: very low, INDOOR (+8), possible CAVE (+3)")

        # -------- GPS Satellites (20%) --------
        if satellites >= 7:
            location_scores["OUTDOOR"] += 12
            debug.append("GPS: strong signal, OUTDOOR (+12)")
        elif satellites >= 4:
            location_scores["OUTDOOR"] += 5
            debug.append("GPS: moderate, OUTDOOR (+5)")
        elif satellites >= 2:
            location_scores["INDOOR"] += 5
            debug.append("GPS: weak, INDOOR (+5)")
        else:
            # Check other signals: only penalize if co2/humidity/light are also "indoorish"
            if (co2 > 900 or humidity < 55 or lux < 350):
                location_scores["CAVE"] += 13
                location_scores["INDOOR"] += 7
                debug.append("GPS: no fix, and other cues suggest INDOOR/CAVE (+13/+7)")
            else:
                location_scores["OUTDOOR"] += 3
                debug.append("GPS: no fix, but other cues are outdoor, OUTDOOR (+3)")

        # --------- Collate Results ---------
        best_location = max(location_scores, key=location_scores.get)
        best_score = location_scores[best_location]
        self.location_history.append(best_location)
        if len(self.location_history) > self.MAX_LOCATION_HISTORY:
            self.location_history.pop(0)

        # -- Sticky vehicle logic --
        # Save vehicle state if detected
        if best_location == "VEHICLE" and speed_kmh > 6:
            self.last_vehicle_time = current_time
            self.last_vehicle_coords = (self.current_latitude, self.current_longitude)
        elif (self.current_location == "VEHICLE" or best_location == "VEHICLE"):
            # Check if we've recently been in vehicle mode
            if current_time - self.last_vehicle_time < self.vehicle_sticky_duration:
                moved = False
                if self.current_latitude is not None and self.current_longitude is not None and self.last_vehicle_coords:
                    # Simple distance calculation
                    lat1, lon1 = self.last_vehicle_coords
                    lat2, lon2 = self.current_latitude, self.current_longitude
                    if None not in (lat1, lon1, lat2, lon2):
                        # Approx: 1 deg latitude ~ 111111 meters
                        dlat = (lat2 - lat1) * 111111
                        dlon = (lon2 - lon1) * 111111 * math.cos(math.radians(lat1))
                        distance = (dlat ** 2 + dlon ** 2) ** 0.5
                        if distance > self.vehicle_sticky_distance:
                            moved = True
                    else:
                        distance = 0
                        moved = False
                else:
                    distance = 0
                    moved = False

                if not moved:
                    self.current_location = "VEHICLE"
                    self.location_confidence = max(self.location_confidence, 85)
                    print(f"🚌 Sticky VEHICLE mode (stop sign): {distance:.2f} m moved")
                    return  # Early exit if sticky

        # Smoothing: Use the most common recent location
        stable_location = max(set(self.location_history), key=self.location_history.count)
        if self.location_history.count(stable_location) > 2:
            self.current_location = stable_location
            self.location_confidence = min(95, best_score + 8)
        else:
            self.current_location = best_location
            self.location_confidence = best_score
            
        # --- Apply force override if active ---
        if self.force_location and current_time <= self.force_until:
            self.current_location = self.force_location
            self.location_confidence = 99
            print(f"⚡ Forced location: {self.current_location} ({self.location_confidence}%) [hybrid threshold]")
        elif self.force_location and current_time > self.force_until:
            self.force_location = None  # Clear override when time is up

        self.last_update = current_time

        # Verbose debug output
        print("---- LOCATION DECISION DEBUG ----")
        print(f"Satellites: {satellites}, Speed: {speed_kmh:.1f} km/h, CO2: {co2}, Lux: {lux}, Humidity: {humidity:.1f}")
        for msg in debug:
            print("   " + msg)
        print(f"   Location scores: {location_scores}")
        print(f"   Best: {best_location} ({best_score}%), Stable: {stable_location} (x{self.location_history.count(stable_location)})")
        print(f"   Final decision: {self.current_location} ({self.location_confidence}%)\n")
        
    def get_location_info(self):
        """
        Returns a dict with the current location and scoring details.
        """
        return {
            'location': self.current_location,
            'confidence': self.location_confidence,
            'gps_satellites': self.current_satellites,
            'gps_speed_kmh': self.current_speed_kmh,
            'gps_fix': self.current_satellites >= 3,
            'stationary_time': 0,
            'time_since_change': 0,
            'location_stable': self.location_history.count(self.current_location) > 2
        }
        
    def get_gps_quality_description(self):
        if self.current_satellites >= 8:
            return "EXCELLENT"
        elif self.current_satellites >= 6:
            return "GOOD"
        elif self.current_satellites >= 4:
            return "FAIR"
        elif self.current_satellites >= 1:
            return "POOR"
        else:
            return "NO_SIGNAL"

# =============================================================================
# OPTIMIZED SENSOR MANAGER WITH FIXED GPS ANTI-SPOOFING
# =============================================================================

class AIFieldSensorManager:
    def __init__(self):
        # Hardware sensor instances
        self.i2c = None
        self.scd41 = None
        self.tsl = None
        self.bmp390 = None
        
        # GPS Anti-Spoofing System
        self.gps = None
        self.gps_data = None
        self.gps_last_update = 0
        self.GPS_UPDATE_INTERVAL = 1
        
        # Hardware pins
        self.geiger_pin = None
        self.piezo_pin = None
        self.battery_low_pin = None
        self.button = None
        self.flashlight = None
        
        # Enhanced systems
        self.gps_location_detector = GPSLocationDetector()
        
        # Location state
        self.current_location = "OUTDOOR"
        self.location_confidence = 50
        self.gps_available = False
        
        # Polling configuration
        self.location_polling_config = {
            "OUTDOOR": {"gps": 1, "air": 5, "light": 2, "pressure": 20, "radiation": 1},
            "INDOOR":  {"gps": 5, "air": 3, "light": 2, "pressure": 30, "radiation": 1},
            "VEHICLE": {"gps": 1, "air": 8, "light": 4, "pressure": 0, "radiation": 1},
            "CAVE":    {"gps": 10, "air": 2, "light": 20, "pressure": 30, "radiation": 1}
        }
        
        self.last_poll_times = {
            "gps": 0, "air": 0, "light": 0, "pressure": 0, "radiation": 0
        }
        
        # Sensor data
        self.co2 = 400
        self.voc = 0
        self.temperature = 25.0
        self.humidity = 50.0
        self.lux = 0
        self.pressure_hpa = 1013.25
        self.altitude_m = 0
        
        # Sensor health tracking
        self.sensor_status = {
            'scd41': False,
            'tsl2591': False,
            'bmp390': False,
            'geiger': False,
            'battery': False,
            'i2c_bus': False,
            'gps': False
        }
        
        self.sensor_last_success = {
            'scd41': 0,
            'tsl2591': 0,
            'bmp390': 0,
            'geiger': 0,
            'battery': 0,
            'gps': 0
        }
        
        self.SENSOR_TIMEOUT = 30
        
        # BMP390 optimization
        self.altitude_calculation_counter = 0
        self.altitude_cache_interval = 5
        self.cached_bmp390_temp = 25.0
        self.bmp390_temp_counter = 0
        self.bmp390_temp_cache_interval = 3
        
        # Radiation detection
        self.pulse_count = 0
        self.cpm = 0
        self.usv_h = 0.0
        self.alpha = 53.032
        self.radiation_warmup_start = 0
        self.radiation_count_start = 0
        self.count_duration = 120
        self.last_pulse_time = 0
        self.previous_geiger_state = True
        
        # System monitoring
        self.battery_low = False
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.cpu_temp = 25.0
        self.loop_times = []
        self.avg_loop_time = 0.0
        self.max_loop_time = 0.0
        self.battery_usage_estimate = 100
        
        self.performance_update_time = 0
        self.PERFORMANCE_UPDATE_INTERVAL = 15
        
        self.air_quality_last_update = 0
        self.light_last_update = 0
        self.pressure_last_update = 0
        self.battery_check_time = 0
        
        self.STATUS_STRINGS = {
            True: "READY",
            False: "WARMUP"
        }
        
        self.RADIATION_WARMUP = 120
        self.BATTERY_CHECK_INTERVAL = 60
        
        print("🔧 AI Field Sensor Manager v2.0 with FIXED GPS Anti-Spoofing Initialized")

    def initialize_gps(self):
        try:
            # Use the same I2C bus as other sensors - GPS has unique address 0x42
            if self.i2c is None:
                print("❌ GPS initialization failed: I2C bus not initialized")
                return False
                
            self.gps = GPSParser(self.i2c)  # Use existing I2C bus
            if self.gps:
                self.sensor_status['gps'] = True
                self.gps_available = True
                print("✅ GPS Anti-Spoofing module initialized on shared I2C bus")
                return True
            else:
                print("❌ GPS Anti-Spoofing module failed to initialize")
                self.sensor_status['gps'] = False
                return False
        except Exception as e:
            print(f"❌ GPS initialization error: {e}")
            self.sensor_status['gps'] = False
            return False

    def initialize_hardware_pins(self):
        try:
            self.geiger_pin = digitalio.DigitalInOut(board.GP7)
            self.geiger_pin.switch_to_input(pull=digitalio.Pull.UP)
        
            self.piezo_pin = digitalio.DigitalInOut(board.GP20)
            self.piezo_pin.switch_to_output()
        
            self.button = digitalio.DigitalInOut(board.GP3)
            self.button.switch_to_input(pull=digitalio.Pull.UP)
        
            self.flashlight = digitalio.DigitalInOut(board.GP2)
            self.flashlight.switch_to_output()
            self.flashlight.value = False
        
            self.battery_low_pin = digitalio.DigitalInOut(board.GP0)
            self.battery_low_pin.switch_to_input(pull=digitalio.Pull.UP)
        
            current_time = time.monotonic()
            self.radiation_warmup_start = current_time
            self.radiation_count_start = current_time
            
            self.sensor_status['geiger'] = True
            self.sensor_status['battery'] = True
        
            print("✅ Hardware pins initialized")
            return True
        
        except Exception as e:
            print(f"❌ Hardware pin initialization failed: {e}")
            self.sensor_status['geiger'] = False
            self.sensor_status['battery'] = False
            return False

    def initialize_i2c_sensors(self):
        sensors_initialized = 0
        total_sensors = 3
        
        try:
            self.i2c = busio.I2C(board.GP5, board.GP4)
            self.sensor_status['i2c_bus'] = True
            print("✅ I2C bus initialized")
            
            # SCD41
            try:
                self.scd41 = adafruit_scd4x.SCD4X(self.i2c)
                self.scd41.start_periodic_measurement()
                self.sensor_status['scd41'] = True
                sensors_initialized += 1
                print("✅ SCD41 air quality sensor ready")
            except Exception as e:
                print(f"❌ SCD41 initialization failed: {e}")
                self.scd41 = None
                self.sensor_status['scd41'] = False
            
            # TSL2591
            try:
                self.tsl = adafruit_tsl2591.TSL2591(self.i2c)
                self.tsl.gain = adafruit_tsl2591.GAIN_LOW
                self.tsl.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
                self.sensor_status['tsl2591'] = True
                sensors_initialized += 1
                print("✅ TSL2591 light sensor ready")
            except Exception as e:
                print(f"❌ TSL2591 initialization failed: {e}")
                self.tsl = None
                self.sensor_status['tsl2591'] = False
            
            # BMP390
            try:
                self.bmp390 = adafruit_bmp3xx.BMP3XX_I2C(self.i2c)
                
                self.bmp390.pressure_oversampling = 2
                self.bmp390.temperature_oversampling = 1
                self.bmp390.filter_coefficient = 4
                self.bmp390.standby_time = 10
                self.bmp390.sea_level_pressure = 1013.25
                
                self.pressure_hpa = self.bmp390.pressure
                self.altitude_m = self.bmp390.altitude
                self.cached_bmp390_temp = self.bmp390.temperature
                
                self.sensor_status['bmp390'] = True
                sensors_initialized += 1
                print(f"✅ BMP390 ready - {self.pressure_hpa:.1f} hPa, {self.altitude_m:.1f}m")
                
            except Exception as e:
                print(f"❌ BMP390 initialization failed: {e}")
                self.bmp390 = None
                self.sensor_status['bmp390'] = False
                
        except Exception as e:
            print(f"❌ I2C bus initialization failed: {e}")
            self.sensor_status['i2c_bus'] = False
            return False
        
        success_rate = (sensors_initialized / total_sensors) * 100
        print(f"📊 Sensor initialization: {sensors_initialized}/{total_sensors} ({success_rate:.0f}%)")
        
        return sensors_initialized > 0

    def initialize_all_sensors(self):
        print("🚀 Starting AI Field Analyzer v2.0 with FIXED GPS Anti-Spoofing...")
        
        success_count = 0
        total_steps = 3
        
        if self.initialize_hardware_pins():
            success_count += 1
            print("✅ Step 1/3: Hardware pins initialized")
        else:
            print("❌ Step 1/3: Hardware pin initialization failed")
        
        if self.initialize_i2c_sensors():
            success_count += 1
            print("✅ Step 2/3: I2C sensors initialized")
        else:
            print("❌ Step 2/3: I2C sensor initialization failed")
        
        if self.initialize_gps():
            success_count += 1
            print("✅ Step 3/3: GPS Anti-Spoofing initialized")
        else:
            print("❌ Step 3/3: GPS Anti-Spoofing initialization failed")
        
        success_rate = (success_count / total_steps) * 100
        print(f"📊 System initialization: {success_count}/{total_steps} ({success_rate:.0f}%)")
        
        return success_count >= 2

    def update_gps_data(self):
        current_time = time.monotonic()
        
        if current_time - self.gps_last_update < self.GPS_UPDATE_INTERVAL:
            return False
            
        if not self.gps:
            return False
        
        try:
            self.gps_data = get_gps_data(self.gps)
            if self.gps_data:
                # Apply pressure sensor fusion
                if self.bmp390 and self.sensor_status.get('bmp390', False):
                    pressure_altitude = self.altitude_m
                    pressure_healthy = True
                else:
                    pressure_altitude = None
                    pressure_healthy = False
                
                fusion_threats = self.gps.apply_pressure_fusion(pressure_altitude, pressure_healthy)
                
                self.gps_data['confidence_level'] = self.gps.confidence_level
                self.gps_data['fusion_threats'] = fusion_threats
                self.gps_data['pressure_fusion_active'] = pressure_healthy
                
                self.sensor_status['gps'] = True
                self.sensor_last_success['gps'] = current_time
                self.gps_last_update = current_time
                
                satellites = self.gps_data.get('satellites', 0)
                speed_kmh = self.gps_data.get('speed_knots', 0) * 1.852
                
                # FIXED: Pass GPS coordinates to location detector
                latitude = self.gps_data.get('latitude')
                longitude = self.gps_data.get('longitude')
                
                # Enhanced location detection with multi-sensor fusion
                self.gps_location_detector.update_gps_data(
                    satellites,
                    speed_kmh,
                    co2=self.co2 if self.co2 else 400,
                    lux=self.lux if self.lux else 0,
                    pressure_hpa=self.pressure_hpa if self.pressure_hpa else 1013.25,
                    humidity=self.humidity if self.humidity else 50,
                    latitude=latitude,
                    longitude=longitude
                )
                
                location_info = self.gps_location_detector.get_location_info()
                self.current_location = location_info['location']
                self.location_confidence = location_info['confidence']
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"❌ GPS update error: {e}")
            self.sensor_status['gps'] = False
            return False

    def _simulate_gps_satellites(self):
        lux = self.lux
        if lux > 1000:
            return 8
        elif lux > 300:
            return 2
        else:
            return 0

    def _calculate_battery_usage_fast(self):
        if self.current_location == "OUTDOOR":
            return 70
        elif self.current_location == "VEHICLE":
            return 75
        else:
            return 85

    def update_gps_and_location(self):
        current_time = time.monotonic()
        
        if self.gps and self.update_gps_data():
            location_info = self.gps_location_detector.get_location_info()
            self.current_location = location_info['location']
            self.location_confidence = location_info['confidence']
        else:
            if current_time - self.gps_last_update < self.GPS_UPDATE_INTERVAL:
                return
            
            try:
                satellites = self._simulate_gps_satellites()
                speed_kmh = 0.0
                
                # FIXED: Enhanced fallback location detection with proper GPS coordinates
                self.gps_location_detector.update_gps_data(
                    satellites,
                    speed_kmh,
                    co2=self.co2 if self.co2 else 400,
                    lux=self.lux if self.lux else 0,
                    pressure_hpa=self.pressure_hpa if self.pressure_hpa else 1013.25,
                    humidity=self.humidity if self.humidity else 50,
                    latitude=None,  # No GPS data in fallback mode
                    longitude=None
                )
                location_info = self.gps_location_detector.get_location_info()
                self.current_location = location_info['location']
                self.location_confidence = location_info['confidence']
                
                self.battery_usage_estimate = self._calculate_battery_usage_fast()
                
                self.gps_last_update = current_time
                
            except Exception as e:
                print(f"⚠️ GPS/Location update error: {e}")

    def _should_update_sensor(self, sensor_name, interval):
        if interval <= 0:
            return False
        
        current_time = time.monotonic()
        last_update = self.last_poll_times.get(sensor_name, 0)
        
        if current_time - last_update >= interval:
            self.last_poll_times[sensor_name] = current_time
            return True
        
        return False

    def update_radiation_detection(self):
        if self.geiger_pin is None or self.piezo_pin is None:
            self.sensor_status['geiger'] = False
            return False
        
        current_time = time.monotonic()
        
        try:
            current_geiger_state = self.geiger_pin.value
        except Exception as e:
            print(f"❌ Geiger pin read error: {e}")
            self.sensor_status['geiger'] = False
            return False

        if self.previous_geiger_state and not current_geiger_state and current_time - self.last_pulse_time > 0.001:
            self.pulse_count += 1
            self.last_pulse_time = current_time
            
            try:
                self.piezo_pin.value = True
                self.piezo_pin.value = False
            except Exception as e:
                print(f"⚠️ Piezo error: {e}")
            
            self.sensor_status['geiger'] = True
            self.sensor_last_success['geiger'] = current_time

        self.previous_geiger_state = current_geiger_state

        if current_time - self.radiation_count_start >= self.count_duration:
            self.cpm = self.pulse_count
            self.usv_h = self.cpm / self.alpha
            self.pulse_count = 0
            self.radiation_count_start = current_time

        if current_time - self.sensor_last_success.get('geiger', current_time) > 300:
            if self.is_radiation_ready() and self.cpm == 0:
                print("⚠️ Geiger counter: No pulses detected for 5+ minutes")
        
        return True

    def is_radiation_ready(self):
        elapsed = time.monotonic() - self.radiation_warmup_start
        return elapsed >= self.RADIATION_WARMUP

    def update_air_quality(self):
        if self.scd41:
            try:
                if self.scd41.data_ready:
                    self.co2 = self.scd41.CO2
                    self.temperature = self.scd41.temperature
                    self.humidity = self.scd41.relative_humidity
                    
                    co2_factor = max(0, self.co2 - 400)
                    humidity_factor = max(0, self.humidity - 40)
                    self.voc = int(co2_factor * 1.5 + humidity_factor * 5)
                    
                    self.sensor_status['scd41'] = True
                    self.sensor_last_success['scd41'] = time.monotonic()
                    return True
                else:
                    return False
                    
            except Exception as e:
                print(f"❌ SCD41 read error: {e}")
                self.sensor_status['scd41'] = False
                self.co2 = None
                self.temperature = None  
                self.humidity = None
                self.voc = None
                return False
        else:
            self.sensor_status['scd41'] = False
            self.co2 = None
            self.temperature = None
            self.humidity = None
            self.voc = None
            return False

    def update_light_sensor(self):
        if self.tsl:
            try:
                lux_reading = self.tsl.lux
                self.lux = 120000 if lux_reading is None else lux_reading
                
                self.sensor_status['tsl2591'] = True
                self.sensor_last_success['tsl2591'] = time.monotonic()
                return True
                
            except Exception as e:
                print(f"❌ TSL2591 read error: {e}")
                self.sensor_status['tsl2591'] = False
                self.lux = None
                return False
        else:
            self.sensor_status['tsl2591'] = False
            self.lux = None
            return False

    def update_pressure_sensor(self):
        if self.bmp390:
            try:
                self.pressure_hpa = self.bmp390.pressure
                
                self.altitude_calculation_counter += 1
                if self.altitude_calculation_counter >= self.altitude_cache_interval:
                    self.altitude_m = self.bmp390.altitude
                    self.altitude_calculation_counter = 0
                
                self.bmp390_temp_counter += 1
                if self.bmp390_temp_counter >= self.bmp390_temp_cache_interval:
                    self.cached_bmp390_temp = self.bmp390.temperature
                    self.bmp390_temp_counter = 0
                
                self.sensor_status['bmp390'] = True
                self.sensor_last_success['bmp390'] = time.monotonic()
                return True
                
            except Exception as e:
                print(f"❌ BMP390 read error: {e}")
                self.sensor_status['bmp390'] = False
                self.pressure_hpa = None
                self.altitude_m = None
                self.cached_bmp390_temp = None
                return False
        else:
            self.sensor_status['bmp390'] = False
            self.pressure_hpa = None
            self.altitude_m = None
            self.cached_bmp390_temp = None
            return False

    def update_system_performance(self, loop_times=None):
        current_time = time.monotonic()
        
        if current_time - self.performance_update_time < self.PERFORMANCE_UPDATE_INTERVAL:
            return False
        
        try:
            self.cpu_temp = microcontroller.cpu.temperature
        except:
            self.cpu_temp = 25.0
        
        try:
            gc.collect()
            total_memory = gc.mem_alloc() + gc.mem_free()
            used_memory = gc.mem_alloc()
            self.memory_usage = (used_memory / total_memory) * 100
        except:
            self.memory_usage = 50
        
        if loop_times:
            self.loop_times = loop_times[-10:]
            if self.loop_times:
                self.avg_loop_time = sum(self.loop_times) / len(self.loop_times)
                self.max_loop_time = max(self.loop_times)
                self.cpu_usage = min(100, self.avg_loop_time * 2000)
        else:
            self.cpu_usage = 25
        
        self.performance_update_time = current_time
        return True

    def check_battery_status(self):
        if self.battery_low_pin is None:
            self.sensor_status['battery'] = False
            return None
        
        current_time = time.monotonic()
        
        if current_time - self.battery_check_time < self.BATTERY_CHECK_INTERVAL:
            return self.battery_low
        
        try:
            self.battery_low = not self.battery_low_pin.value
            self.battery_check_time = current_time
            
            self.sensor_status['battery'] = True
            self.sensor_last_success['battery'] = current_time
            return self.battery_low
            
        except Exception as e:
            print(f"❌ Battery monitoring error: {e}")
            self.sensor_status['battery'] = False
            self.battery_low = None
            return None

    def check_sensor_timeouts(self):
        current_time = time.monotonic()
        
        for sensor_name, last_success in self.sensor_last_success.items():
            if last_success > 0:
                time_since_success = current_time - last_success
                
                if time_since_success > self.SENSOR_TIMEOUT:
                    self.sensor_status[sensor_name] = False
                    
                    if sensor_name == 'scd41':
                        self.co2 = None
                        self.temperature = None
                        self.humidity = None
                        self.voc = None
                    elif sensor_name == 'tsl2591':
                        self.lux = None
                    elif sensor_name == 'bmp390':
                        self.pressure_hpa = None
                        self.altitude_m = None
                        self.cached_bmp390_temp = None

    def get_sensor_health_summary(self):
        online_sensors = sum(1 for status in self.sensor_status.values() if status)
        total_sensors = len(self.sensor_status)
        
        failed_sensors = [name.upper() for name, status in self.sensor_status.items() if not status]
        
        return {
            'online_count': online_sensors,
            'total_count': total_sensors,
            'health_percentage': (online_sensors / total_sensors) * 100,
            'failed_sensors': failed_sensors,
            'all_healthy': len(failed_sensors) == 0,
            'critical_failure': 'scd41' in [s.lower() for s in failed_sensors] or 'i2c_bus' in [s.lower() for s in failed_sensors]
        }

    def set_sea_level_pressure(self, pressure_hpa):
        if self.bmp390:
            self.bmp390.sea_level_pressure = pressure_hpa
            print(f"📊 Sea level pressure set to {pressure_hpa:.1f} hPa")

    def get_temperature_with_smart_failover(self):
        bmp390_temp = self.cached_bmp390_temp
        scd41_temp = self.temperature
        
        scd41_in_range = (scd41_temp is not None and -10 <= scd41_temp <= 60)
        
        if (bmp390_temp is not None and scd41_temp is not None and scd41_in_range):
            weighted_temp = (bmp390_temp * 0.65 + scd41_temp * 0.35)
            return weighted_temp, "FUSED"
        elif bmp390_temp is not None:
            return bmp390_temp, "BMP390"
        elif scd41_temp is not None and scd41_in_range:
            return scd41_temp, "SCD41"
        elif scd41_temp is not None and not scd41_in_range:
            print(f"⚠️ SCD41 temperature {scd41_temp:.1f}°C outside range")
            return None, "SCD41_OUT_OF_RANGE"
        else:
            return None, "FAILED"

    def get_temperature_sensor_status(self):
        bmp390_temp = self.cached_bmp390_temp
        scd41_temp = self.temperature
        
        status = {
            'bmp390_available': bmp390_temp is not None,
            'bmp390_temp': bmp390_temp,
            'scd41_available': scd41_temp is not None,
            'scd41_temp': scd41_temp,
            'scd41_in_range': (scd41_temp is not None and -10 <= scd41_temp <= 60),
            'active_sensors': 0,
            'primary_sensor': None,
            'temperature_source': None
        }
        
        if status['bmp390_available']:
            status['active_sensors'] += 1
        if status['scd41_available'] and status['scd41_in_range']:
            status['active_sensors'] += 1
        
        temp_value, temp_source = self.get_temperature_with_smart_failover()
        status['primary_sensor'] = temp_source
        status['temperature_source'] = temp_source
        status['final_temperature'] = temp_value
        
        return status

    def update_all_sensors(self, loop_times=None):
        self.update_radiation_detection()
        self.update_gps_and_location()
        
        config = self.location_polling_config[self.current_location]
        
        if self._should_update_sensor("air", config["air"]):
            self.update_air_quality()
        
        if self._should_update_sensor("light", config["light"]):
            self.update_light_sensor()
        
        if self._should_update_sensor("pressure", config["pressure"]):
            self.update_pressure_sensor()
        
        self.update_system_performance(loop_times)
        self.check_battery_status()
        self.check_sensor_timeouts()
        
        return True

    def _get_gps_threat_level(self):
        if not self.gps_data:
            return "UNAVAILABLE"
        
        confidence = self.gps_data.get('confidence_level', 0)
        
        if confidence >= 90:
            return "SECURE"
        elif confidence >= 70:
            return "CAUTION"
        elif confidence >= 50:
            return "WARNING"
        else:
            return "THREAT"

    def get_all_sensor_data(self):
        location_info = self.gps_location_detector.get_location_info()
        bmp390_temp = self.cached_bmp390_temp if self.bmp390 else None
        
        # GPS data with pressure fusion
        gps_info = {}
        if self.gps_data:
            gps_info = {
                'gps_latitude': self.gps_data.get('latitude'),
                'gps_longitude': self.gps_data.get('longitude'),
                'gps_altitude_m': self.gps_data.get('altitude_m'),
                'gps_speed_knots': self.gps_data.get('speed_knots'),
                'gps_course': self.gps_data.get('course'),
                'gps_satellites': self.gps_data.get('satellites', 0),
                'gps_satellites_tracked': self.gps_data.get('satellites_tracked', 0),
                'gps_has_fix': self.gps_data.get('has_fix', False),
                'gps_fix_quality': self.gps_data.get('fix_quality', '0'),
                'gps_hdop': self.gps_data.get('hdop', 99.9),
                'gps_confidence_level': self.gps_data.get('confidence_level', 0),
                'gps_time': self.gps_data.get('gps_time'),
                'gps_date': self.gps_data.get('date'),
                'gps_debug_msg': self.gps_data.get('debug_msg', 'No GPS data'),
                'gps_anti_spoofing_status': self._get_gps_threat_level(),
                'gps_available': True,
                'gps_pressure_fusion_active': self.gps_data.get('pressure_fusion_active', False),
                'gps_fusion_threats': self.gps_data.get('fusion_threats', []),
                'gps_altitude_comparison': getattr(self.gps, 'altitude_comparison', None)
            }
        else:
            gps_info = {
                'gps_latitude': None,
                'gps_longitude': None,
                'gps_altitude_m': None,
                'gps_speed_knots': None,
                'gps_course': None,
                'gps_satellites': location_info['gps_satellites'],
                'gps_satellites_tracked': location_info['gps_satellites'],
                'gps_has_fix': location_info['gps_fix'],
                'gps_fix_quality': '0',
                'gps_hdop': 99.9,
                'gps_confidence_level': 0,
                'gps_time': None,
                'gps_date': None,
                'gps_debug_msg': 'GPS hardware not available',
                'gps_anti_spoofing_status': 'UNAVAILABLE',
                'gps_available': False,
                'gps_pressure_fusion_active': False,
                'gps_fusion_threats': [],
                'gps_altitude_comparison': None
            }
        
        base_data = {
            'co2': self.co2,
            'voc': self.voc,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'lux': self.lux,
            'pressure_hpa': self.pressure_hpa,
            'altitude_m': self.altitude_m,
            'cpm': self.cpm,
            'usv_h': self.usv_h,
            'radiation_ready': self.is_radiation_ready(),
            'battery_low': self.battery_low,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'cpu_temp': self.cpu_temp,
            'avg_loop_time': self.avg_loop_time,
            'max_loop_time': self.max_loop_time,
            'bmp390_temperature': bmp390_temp,
            'sea_level_pressure': self.bmp390.sea_level_pressure if self.bmp390 else 1013.25,
            'current_location': location_info['location'],
            'location_confidence': location_info['confidence'],
            'location_description': f"{location_info['location']} ({location_info['confidence']}%)",
            'gps_quality': self.gps_location_detector.get_gps_quality_description(),
            'battery_usage_estimate': self.battery_usage_estimate,
        }
        
        base_data.update(gps_info)
        return base_data

    def run_diagnostics(self):
        print("\n🔧 FIXED GPS Anti-Spoofing System Diagnostics")
        print("=" * 70)
        
        # Sensor health
        print("\n📡 SENSOR HEALTH STATUS:")
        for sensor_name, status in self.sensor_status.items():
            icon = "✅" if status else "❌"
            last_success = self.sensor_last_success.get(sensor_name, 0)
            if last_success > 0:
                time_since = time.monotonic() - last_success
                time_str = f"({time_since:.0f}s ago)" if not status else "(Active)"
            else:
                time_str = "(Never)" if not status else "(Initialized)"
            
            print(f"  {icon} {sensor_name.upper()}: {'ONLINE' if status else 'OFFLINE'} {time_str}")
        
        # GPS Anti-Spoofing Status with Pressure Fusion
        print(f"\n🛡️ GPS ANTI-SPOOFING WITH PRESSURE FUSION:")
        if self.gps_data:
            confidence = self.gps_data.get('confidence_level', 0)
            threat_level = self._get_gps_threat_level()
            fusion_active = self.gps_data.get('pressure_fusion_active', False)
            
            print(f"  Status: {threat_level} ({confidence}% confidence)")
            print(f"  Pressure Fusion: {'ACTIVE' if fusion_active else 'INACTIVE'}")
            
            if hasattr(self.gps, 'altitude_comparison') and self.gps.altitude_comparison:
                alt_comp = self.gps.altitude_comparison
                if alt_comp['fusion_active']:
                    gps_alt = alt_comp['gps_altitude']
                    pressure_alt = alt_comp['pressure_altitude']
                    diff = alt_comp['difference']
                    
                    print(f"  GPS Altitude: {gps_alt:.1f}m")
                    print(f"  Pressure Altitude: {pressure_alt:.1f}m")
                    print(f"  Difference: {diff:.1f}m")
                    
                    if diff > 1000:
                        print(f"  ⚠️ MAJOR ALTITUDE SPOOFING DETECTED!")
                    elif diff > 500:
                        print(f"  ⚠️ MODERATE altitude spoofing detected")
                    elif diff > 200:
                        print(f"  ⚠️ Minor altitude spoofing detected")
                    elif diff > 100:
                        print(f"  ⚠️ Suspicious altitude difference")
                    else:
                        print(f"  ✅ Altitude correlation good")
        else:
            print(f"  Status: GPS hardware not available")
        
        print("\n✅ FIXED GPS Anti-Spoofing diagnostics complete!")

# Test function
def main():
    print("🛡️ FIXED GPS Anti-Spoofing AI Field Analyzer Test")
    
    sensors = AIFieldSensorManager()
    if not sensors.initialize_all_sensors():
        print("Failed to initialize sensor system")
        return
    
    print("Starting FIXED GPS Anti-Spoofing monitoring...")
    
    while True:
        try:
            sensors.update_all_sensors()
            data = sensors.get_all_sensor_data()
            
            if data['gps_available']:
                print(f"\n🛡️ GPS Status: {data['gps_anti_spoofing_status']}")
                print(f"   Confidence: {data['gps_confidence_level']}%")
                print(f"   Pressure Fusion: {'ACTIVE' if data['gps_pressure_fusion_active'] else 'INACTIVE'}")
                
                alt_comp = data.get('gps_altitude_comparison')
                if alt_comp and alt_comp['fusion_active']:
                    diff = alt_comp['difference']
                    gps_alt = alt_comp['gps_altitude']
                    pressure_alt = alt_comp['pressure_altitude']
                    
                    # Handle None values safely
                    if gps_alt is not None and pressure_alt is not None and diff is not None:
                        print(f"   Altitude: GPS {gps_alt:.0f}m vs Pressure {pressure_alt:.0f}m ({diff:.0f}m diff)")
                    else:
                        print(f"   Altitude: GPS data incomplete")
                
                print(f"   Time: {data['gps_time']} Sats: {data['gps_satellites']}")
            else:
                print(f"\n📡 GPS: Hardware not available")
            
            print(f"   Location: {data['current_location']}")
            print(f"   CO2: {data['co2']} ppm")
            print("-" * 50)
            
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
