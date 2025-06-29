"""
AI Field Analyzer v1.9 - Fixed Enhanced Sensor Management System
-----------------------------------------------------------------
Clean version with all syntax errors resolved for CircuitPython compatibility.

© 2025 Apollo Timbers. MIT License.
"""

# Remove the deque import since we're not using it
import time
import board
import busio
import digitalio
import microcontroller
import adafruit_scd4x
import adafruit_tsl2591
import gc
import struct
import math

# =============================================================================
# SIMPLE BMP180 DRIVER (Your existing working code)
# =============================================================================

class SimpleBMP180:
    """Custom BMP180 driver for pressure and temperature"""
    
    def __init__(self, i2c_bus):
        self.i2c = i2c_bus
        self.address = 0x77
        
        # BMP180 calibration coefficients
        self.cal_AC1 = 0
        self.cal_AC2 = 0
        self.cal_AC3 = 0
        self.cal_AC4 = 0
        self.cal_AC5 = 0
        self.cal_AC6 = 0
        self.cal_B1 = 0
        self.cal_B2 = 0
        self.cal_MB = 0
        self.cal_MC = 0
        self.cal_MD = 0
        
        if self._check_device():
            self._read_calibration()
            print("✅ BMP180 initialized successfully")
        else:
            raise RuntimeError("BMP180 not found at 0x77")
    
    def _check_device(self):
        try:
            while not self.i2c.try_lock():
                pass
            self.i2c.writeto(self.address, bytes([0xD0]))
            result = bytearray(1)
            self.i2c.readfrom_into(self.address, result)
            chip_id = result[0]
            return chip_id == 0x55
        except Exception:
            return False
        finally:
            self.i2c.unlock()
    
    def _read_calibration(self):
        try:
            while not self.i2c.try_lock():
                pass
            self.i2c.writeto(self.address, bytes([0xAA]))
            cal_data = bytearray(22)
            self.i2c.readfrom_into(self.address, cal_data)
            
            self.cal_AC1 = struct.unpack('>h', cal_data[0:2])[0]
            self.cal_AC2 = struct.unpack('>h', cal_data[2:4])[0]
            self.cal_AC3 = struct.unpack('>h', cal_data[4:6])[0]
            self.cal_AC4 = struct.unpack('>H', cal_data[6:8])[0]
            self.cal_AC5 = struct.unpack('>H', cal_data[8:10])[0]
            self.cal_AC6 = struct.unpack('>H', cal_data[10:12])[0]
            self.cal_B1 = struct.unpack('>h', cal_data[12:14])[0]
            self.cal_B2 = struct.unpack('>h', cal_data[14:16])[0]
            self.cal_MB = struct.unpack('>h', cal_data[16:18])[0]
            self.cal_MC = struct.unpack('>h', cal_data[18:20])[0]
            self.cal_MD = struct.unpack('>h', cal_data[20:22])[0]
        except Exception as e:
            print(f"❌ Error reading calibration: {e}")
            raise
        finally:
            self.i2c.unlock()
    
    def _read_raw_temperature(self):
        try:
            while not self.i2c.try_lock():
                pass
            self.i2c.writeto(self.address, bytes([0xF4, 0x2E]))
            time.sleep(0.005)
            self.i2c.writeto(self.address, bytes([0xF6]))
            temp_data = bytearray(2)
            self.i2c.readfrom_into(self.address, temp_data)
            raw_temp = (temp_data[0] << 8) + temp_data[1]
            return raw_temp
        finally:
            self.i2c.unlock()
    
    def _read_raw_pressure(self, oss=0):
        try:
            while not self.i2c.try_lock():
                pass
            cmd = 0x34 + (oss << 6)
            self.i2c.writeto(self.address, bytes([0xF4, cmd]))
            wait_times = [0.005, 0.008, 0.014, 0.026]
            time.sleep(wait_times[oss])
            self.i2c.writeto(self.address, bytes([0xF6]))
            press_data = bytearray(3)
            self.i2c.readfrom_into(self.address, press_data)
            raw_pressure = ((press_data[0] << 16) + (press_data[1] << 8) + press_data[2]) >> (8 - oss)
            return raw_pressure
        finally:
            self.i2c.unlock()
    
    @property
    def temperature(self):
        raw_temp = self._read_raw_temperature()
        X1 = ((raw_temp - self.cal_AC6) * self.cal_AC5) >> 15
        X2 = (self.cal_MC << 11) // (X1 + self.cal_MD)
        B5 = X1 + X2
        temp_c = ((B5 + 8) >> 4) / 10.0
        return temp_c
    
    @property
    def pressure(self):
        raw_temp = self._read_raw_temperature()
        raw_pressure = self._read_raw_pressure(oss=0)
        
        X1 = ((raw_temp - self.cal_AC6) * self.cal_AC5) >> 15
        X2 = (self.cal_MC << 11) // (X1 + self.cal_MD)
        B5 = X1 + X2
        
        B6 = B5 - 4000
        X1 = (self.cal_B2 * ((B6 * B6) >> 12)) >> 11
        X2 = (self.cal_AC2 * B6) >> 11
        X3 = X1 + X2
        B3 = (((self.cal_AC1 * 4 + X3) << 0) + 2) >> 2
        
        X1 = (self.cal_AC3 * B6) >> 13
        X2 = (self.cal_B1 * ((B6 * B6) >> 12)) >> 16
        X3 = ((X1 + X2) + 2) >> 2
        B4 = (self.cal_AC4 * (X3 + 32768)) >> 15
        B7 = (raw_pressure - B3) * (50000 >> 0)
        
        if B7 < 0x80000000:
            pressure_pa = (B7 * 2) // B4
        else:
            pressure_pa = (B7 // B4) * 2
        
        X1 = (pressure_pa >> 8) * (pressure_pa >> 8)
        X1 = (X1 * 3038) >> 16
        X2 = (-7357 * pressure_pa) >> 16
        pressure_pa = pressure_pa + ((X1 + X2 + 3791) >> 4)
        
        pressure_hpa = pressure_pa / 100.0
        return pressure_hpa
    
    @property 
    def altitude(self):
        pressure_hpa = self.pressure
        altitude_m = 44330 * (1 - (pressure_hpa / 1013.25) ** 0.1903)
        return altitude_m

# =============================================================================
# SIMPLE GPS LOCATION DETECTOR
# =============================================================================

class GPSLocationDetector:
    """Simple GPS-based location detection"""
    
    def __init__(self):
        self.gps_history = []  # Use simple list instead of deque
        self.current_satellites = 0
        self.current_speed_kmh = 0.0
        self.current_location = "OUTDOOR"
        self.location_confidence = 50
        self.movement_confidence = 0
        self.last_update = 0
        self.MAX_HISTORY = 20  # Manually manage list size
        print("📍 GPS Location Detector initialized")
    
    def update_gps_data(self, satellites, speed_kmh):
        """Update GPS data and determine location"""
        current_time = time.monotonic()
        
        self.current_satellites = satellites
        self.current_speed_kmh = speed_kmh
        
        # Add to history and manage size manually
        self.gps_history.append((current_time, satellites, speed_kmh))
        
        # Keep only recent entries
        while len(self.gps_history) > self.MAX_HISTORY:
            self.gps_history.pop(0)
        
        # Simple location logic
        if speed_kmh > 15:
            self.current_location = "VEHICLE"
            self.location_confidence = 90
        elif satellites == 0:
            self.current_location = "CAVE"
            self.location_confidence = 85
        elif satellites < 3:
            self.current_location = "INDOOR"
            self.location_confidence = 80
        else:
            self.current_location = "OUTDOOR"
            self.location_confidence = 85
        
        self.last_update = current_time
    
    def get_location_info(self):
        """Get current location information"""
        return {
            'location': self.current_location,
            'confidence': self.location_confidence,
            'gps_satellites': self.current_satellites,
            'gps_speed_kmh': self.current_speed_kmh,
            'gps_fix': self.current_satellites >= 3,
            'movement_confidence': self.movement_confidence,
            'stationary_time': 0,
            'time_since_change': 0,
            'location_stable': True
        }
    
    def get_gps_quality_description(self):
        """Get GPS quality description"""
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
# SIMPLE WEATHER SYSTEM
# =============================================================================

class SimpleWeatherSystem:
    """Simple outdoor-only weather system"""
    
    def __init__(self):
        self.current_location = "OUTDOOR"
        self.weather_active = False
        self.current_pressure = 1013.25
        self.current_temp = 20.0
        self.current_humidity = 50.0
        self.pressure_history = []
        
        # Weather results
        self.weather_forecast_type = "INITIALIZING"
        self.weather_confidence = 50
        self.weather_description = "Starting weather analysis..."
        self.dew_point = 0.0
        self.pressure_tendency = 0.0
        
        print("🌪️ Simple Weather System initialized")
    
    def update_location_and_readings(self, pressure_hpa, temperature_c, humidity_percent, current_location):
        """Update weather system"""
        self.current_location = current_location
        
        if current_location == "OUTDOOR":
            self.weather_active = True
            self.current_pressure = pressure_hpa
            self.current_temp = temperature_c
            self.current_humidity = humidity_percent
            
            # Simple weather logic
            self.dew_point = self._calculate_dew_point(temperature_c, humidity_percent)
            temp_dewpoint_diff = temperature_c - self.dew_point
            
            # Basic fog detection
            if temp_dewpoint_diff <= 1.0 and humidity_percent >= 95:
                self.weather_forecast_type = "DENSE_FOG"
                self.weather_confidence = 95
                self.weather_description = "Dense fog forming - visibility will be severely limited"
            elif temp_dewpoint_diff <= 3.0 and humidity_percent >= 85:
                self.weather_forecast_type = "FOG_RISK"
                self.weather_confidence = 75
                self.weather_description = "Fog possible in next few hours"
            else:
                self.weather_forecast_type = "CLEAR"
                self.weather_confidence = 80
                self.weather_description = "Clear conditions expected"
        else:
            self.weather_active = False
            self.weather_forecast_type = "PAUSED"
            self.weather_confidence = 0
            self.weather_description = f"Weather monitoring paused - {current_location.lower()} environment"
    
    def _calculate_dew_point(self, temp_c, humidity_percent):
        """Calculate dew point"""
        if humidity_percent <= 0:
            return temp_c - 50
        a, b = 17.27, 237.7
        alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity_percent / 100.0)
        return (b * alpha) / (a - alpha)
    
    def get_forecast(self):
        """Get current forecast"""
        return {
            'type': self.weather_forecast_type,
            'confidence': self.weather_confidence,
            'timing': '1-3 hours',
            'description': self.weather_description
        }
    
    def get_current_conditions(self):
        """Get current conditions"""
        return {
            'pressure': self.current_pressure,
            'temperature': self.current_temp,
            'humidity': self.current_humidity,
            'dew_point': self.dew_point,
            'pressure_tendency': self.pressure_tendency,
            'weather_active': self.weather_active,
            'data_collection_active': self.weather_active,
            'current_location': self.current_location
        }

# =============================================================================
# MAIN ENHANCED SENSOR MANAGER
# =============================================================================

class AIFieldSensorManager:
    """Enhanced AI Field Analyzer sensor management system"""
    
    def __init__(self):
        # Hardware sensor instances
        self.i2c = None
        self.scd41 = None
        self.tsl = None
        self.bmp = None
        
        # Hardware pins
        self.geiger_pin = None
        self.piezo_pin = None
        self.battery_low_pin = None
        self.button = None
        self.flashlight = None
        
        # Enhanced systems - FIXED initialization
        self.gps_location_detector = GPSLocationDetector()
        self.weather_system = SimpleWeatherSystem()
        
        # Location state
        self.current_location = "OUTDOOR"
        self.location_confidence = 50
        self.gps_available = False
        self.gps_last_update = 0
        self.GPS_UPDATE_INTERVAL = 5
        
        # Location-aware polling configuration
        self.location_polling_config = {
            "OUTDOOR": {"gps": 5, "weather": 10, "air": 5, "light": 3, "pressure": 3, "radiation": 1},
            "INDOOR":  {"gps": 30, "weather": 0, "air": 3, "light": 10, "pressure": 15, "radiation": 1},
            "VEHICLE": {"gps": 3, "weather": 0, "air": 8, "light": 15, "pressure": 0, "radiation": 1},
            "CAVE":    {"gps": 0, "weather": 0, "air": 2, "light": 30, "pressure": 5, "radiation": 1}
        }
        
        # Polling timing
        self.last_poll_times = {
            "gps": 0, "weather": 0, "air": 0, "light": 0, "pressure": 0, "radiation": 0
        }
        
        # Basic sensor data
        self.co2 = 400
        self.voc = 0
        self.temperature = 25.0
        self.humidity = 50.0
        self.lux = 0
        self.pressure_hpa = 1013.25
        self.altitude_m = 0
        
        # Radiation detection 
        self.pulse_count = 0
        self.cpm = 0
        self.usv_h = 0.0
        self.alpha = 53.032
        self.radiation_warmup_start = 0    # NEW: Separate warmup timer
        self.radiation_count_start = 0     # Renamed from radiation_start_time
        self.count_duration = 120
        self.last_pulse_time = 0
        self.previous_geiger_state = True
        
        # Weather data
        self.weather_forecast_type = "INITIALIZING"
        self.weather_confidence = 50
        self.weather_description = "Starting weather analysis..."
        self.fog_risk = "UNKNOWN"
        self.storm_risk = "UNKNOWN"
        self.dew_point = 0.0
        self.pressure_tendency = 0.0
        
        # Legacy compatibility
        self.pressure_trend = "STABLE"
        self.weather_forecast = "Starting up..."
        
        # System monitoring
        self.battery_low = False
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.cpu_temp = 25.0
        self.loop_times = []
        self.avg_loop_time = 0.0
        self.max_loop_time = 0.0
        self.battery_usage_estimate = 100
        
        # Update timers
        self.air_quality_last_update = 0
        self.light_last_update = 0
        self.pressure_last_update = 0
        self.performance_update_time = 0
        self.battery_check_time = 0
        
        # Configuration
        self.RADIATION_WARMUP = 120
        self.BATTERY_CHECK_INTERVAL = 60
        
        print("🔧 Enhanced AI Field Sensor Manager v1.9 initialized")
    
    def initialize_hardware_pins(self):
       """Initialize all hardware pins"""
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
       
           # FIXED: Set both timers once at startup
           current_time = time.monotonic()
           self.radiation_warmup_start = current_time   # Warmup timer - never reset
           self.radiation_count_start = current_time    # Count timer - resets every 2 min
       
           print("✅ Hardware pins initialized")
           return True
       
       except Exception as e:
           print(f"❌ Hardware pin initialization failed: {e}")
           return False
    
    def initialize_i2c_sensors(self):
        """Initialize all I2C sensors"""
        sensors_initialized = 0
        total_sensors = 3
        
        try:
            self.i2c = busio.I2C(board.GP5, board.GP4)
            print("✅ I2C bus initialized")
            
            # SCD41
            try:
                self.scd41 = adafruit_scd4x.SCD4X(self.i2c)
                self.scd41.start_periodic_measurement()
                sensors_initialized += 1
                print("✅ SCD41 air quality sensor ready")
            except Exception as e:
                print(f"❌ SCD41 initialization failed: {e}")
                self.scd41 = None
            
            # TSL2591
            try:
                self.tsl = adafruit_tsl2591.TSL2591(self.i2c)
                self.tsl.gain = adafruit_tsl2591.GAIN_LOW
                self.tsl.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
                sensors_initialized += 1
                print("✅ TSL2591 light sensor ready")
            except Exception as e:
                print(f"❌ TSL2591 initialization failed: {e}")
                self.tsl = None
            
            # BMP180
            try:
                self.bmp = SimpleBMP180(self.i2c)
                self.pressure_hpa = self.bmp.pressure
                self.altitude_m = self.bmp.altitude
                sensors_initialized += 1
                print(f"✅ BMP180 sensor ready - Initial: {self.pressure_hpa:.1f} hPa")
            except Exception as e:
                print(f"❌ BMP180 initialization failed: {e}")
                self.bmp = None
                
        except Exception as e:
            print(f"❌ I2C bus initialization failed: {e}")
            return False
        
        success_rate = (sensors_initialized / total_sensors) * 100
        print(f"📊 Sensor initialization: {sensors_initialized}/{total_sensors} ({success_rate:.0f}%)")
        
        return sensors_initialized > 0
    
    def update_gps_and_location(self):
        """Update GPS and location detection"""
        current_time = time.monotonic()
        
        if current_time - self.gps_last_update < self.GPS_UPDATE_INTERVAL:
            return
        
        try:
            # Simulate GPS based on sensors
            satellites = self._simulate_gps_satellites()
            speed_kmh = 0.0  # Assume stationary for now
            
            self.gps_location_detector.update_gps_data(satellites, speed_kmh)
            
            location_info = self.gps_location_detector.get_location_info()
            self.current_location = location_info['location']
            self.location_confidence = location_info['confidence']
            
            # Calculate battery usage
            config = self.location_polling_config[self.current_location]
            self.battery_usage_estimate = self._calculate_battery_usage(config)
            
            self.gps_last_update = current_time
            
        except Exception as e:
            print(f"⚠️ GPS/Location update error: {e}")
    
    def _simulate_gps_satellites(self):
        """Simulate GPS satellites based on light levels"""
        if self.lux > 1000:
            return 8  # Bright outdoor
        elif self.lux > 300:
            return 2  # Indoor
        else:
            return 0  # Dark/cave
    
    def _calculate_battery_usage(self, config):
        """Calculate battery usage estimate"""
        usage = 50  # Base
        if config["gps"] > 0:
            usage += 20
        if config["weather"] > 0:
            usage += 15
        if config["air"] > 0:
            usage += 10
        return min(100, usage)
    
    def _should_update_sensor(self, sensor_name, interval):
        """Check if sensor should update"""
        if interval <= 0:
            return False
        
        current_time = time.monotonic()
        last_update = self.last_poll_times.get(sensor_name, 0)
        
        if current_time - last_update >= interval:
            self.last_poll_times[sensor_name] = current_time
            return True
        
        return False
    
    def update_radiation_detection(self):
       """Update radiation detection - FIXED TIMER LOGIC"""
       current_time = time.monotonic()
       current_geiger_state = self.geiger_pin.value
   
       # Pulse detection (unchanged)
       if self.previous_geiger_state and not current_geiger_state and current_time - self.last_pulse_time > 0.001:
           self.pulse_count += 1
           self.last_pulse_time = current_time
           self.piezo_pin.value = True
           self.piezo_pin.value = False
   
       self.previous_geiger_state = current_geiger_state
   
       # CPM calculation - only reset COUNT timer, not warmup timer
       if current_time - self.radiation_count_start >= self.count_duration:
           self.cpm = self.pulse_count
           self.usv_h = self.cpm / self.alpha
           self.pulse_count = 0
           self.radiation_count_start = current_time  # ONLY reset count timer
       
           # DEBUG: Print when CPM updates
           print(f"🔄 CPM UPDATE: {self.cpm} CPM, {self.usv_h:.3f} µSv/h")

    def is_radiation_ready(self):
       """Check if radiation sensor is ready - FIXED"""
       elapsed = time.monotonic() - self.radiation_warmup_start
       ready = elapsed >= self.RADIATION_WARMUP
   
       # DEBUG: Print status occasionally
       if int(elapsed) % 30 == 0 and int(elapsed) != getattr(self, '_last_debug', -1):
           print(f"🔍 RADIATION: {elapsed:.1f}s elapsed, ready: {ready}")
           self._last_debug = int(elapsed)
   
       return ready
    
    def update_air_quality(self):
        """Update air quality"""
        if self.scd41:
            try:
                if self.scd41.data_ready:
                    self.co2 = self.scd41.CO2
                    self.temperature = self.scd41.temperature
                    self.humidity = self.scd41.relative_humidity
                    self.voc = max(0, int((self.co2 - 400) * 1.5 + (self.humidity - 40) * 5))
                    return True
            except Exception as e:
                print(f"⚠️ SCD41 read error: {e}")
        return False
    
    def update_light_sensor(self):
        """Update light sensor"""
        if self.tsl:
            try:
                self.lux = self.tsl.lux
                if self.lux is None:
                    self.lux = 120000
                return True
            except Exception as e:
                print(f"⚠️ TSL2591 read error: {e}")
        return False
    
    def update_pressure_sensor(self):
        """Update pressure sensor"""
        if self.bmp:
            try:
                self.pressure_hpa = self.bmp.pressure
                self.altitude_m = self.bmp.altitude
                return True
            except Exception as e:
                print(f"⚠️ BMP180 read error: {e}")
        return False
    
    def update_weather_system(self):
        """Update weather system"""
        try:
            self.weather_system.current_lux = self.lux # pass lux data
            self.weather_system.update_location_and_readings(
                self.pressure_hpa, self.temperature, self.humidity, self.current_location
            )
            
            forecast = self.weather_system.get_forecast()
            conditions = self.weather_system.get_current_conditions()
            
            self.weather_forecast_type = forecast['type']
            self.weather_confidence = forecast['confidence']
            self.weather_description = forecast['description']
            self.dew_point = conditions['dew_point']
            self.pressure_tendency = conditions['pressure_tendency']
            
            # Calculate risk levels
            self.fog_risk = self._calculate_fog_risk()
            self.storm_risk = "LOW"  # Simplified for now
            
            # Legacy compatibility
            self.weather_forecast = self.weather_description
            self.pressure_trend = "STABLE"
            
        except Exception as e:
            print(f"⚠️ Weather system error: {e}")
    
    def _calculate_fog_risk(self):
        """Calculate fog risk using temperature, humidity, AND light levels"""
        if self.current_location != "OUTDOOR":
            return "UNKNOWN"
    
        temp_dewpoint_diff = self.temperature - self.dew_point
    
        # Get current lux level
        current_lux = getattr(self, 'lux', 1000)  # Default if not available
    
        # Fog detection with lux fusion
        if temp_dewpoint_diff <= 1.0 and self.humidity >= 95:
            if current_lux < 500:  # Low visibility confirms fog
                return "CONFIRMED"  # New level - fog actually present
            else:
                return "IMMINENT"   # Conditions right but still visible
        elif temp_dewpoint_diff <= 3.0 and self.humidity >= 85:
            if current_lux < 200:  # Very low light might indicate fog forming
                return "FORMING"    # New level - fog developing
            else:
                return "HIGH"       # Just atmospheric conditions
        elif current_lux < 100 and self.humidity > 70:
            return "POSSIBLE"       # Low light + moisture = potential fog
        else:
            return "LOW"
    
    def update_system_performance(self, loop_times=None):
        """Update system performance"""
        current_time = time.monotonic()
        
        if current_time - self.performance_update_time < 10:
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
            self.loop_times = loop_times[-20:]
            self.avg_loop_time = sum(self.loop_times) / len(self.loop_times)
            self.max_loop_time = max(self.loop_times)
            self.cpu_usage = min(100, (self.avg_loop_time / 0.05) * 100)
        else:
            self.cpu_usage = 25
        
        self.performance_update_time = current_time
        return True
    
    def check_battery_status(self):
        """Check battery status"""
        current_time = time.monotonic()
        
        if current_time - self.battery_check_time < self.BATTERY_CHECK_INTERVAL:
            return self.battery_low
        
        self.battery_low = not self.battery_low_pin.value
        self.battery_check_time = current_time
        return self.battery_low
    
    def is_radiation_ready(self):
        """Check if radiation sensor is ready"""
        return (time.monotonic() - self.radiation_warmup_start) >= self.RADIATION_WARMUP
    
    def update_all_sensors(self, loop_times=None):
        """Update all sensors with adaptive polling"""
        
        # Always update radiation
        self.update_radiation_detection()
        
        # Update GPS and location
        self.update_gps_and_location()
        
        # Get polling configuration
        config = self.location_polling_config[self.current_location]
        
        # Update sensors based on intervals
        if self._should_update_sensor("air", config["air"]):
            self.update_air_quality()
        
        if self._should_update_sensor("light", config["light"]):
            self.update_light_sensor()
        
        if self._should_update_sensor("pressure", config["pressure"]):
            self.update_pressure_sensor()
        
        # Weather only when outdoor
        if config["weather"] > 0 and self.current_location == "OUTDOOR":
            if self._should_update_sensor("weather", config["weather"]):
                self.update_weather_system()
        
        # System monitoring
        self.update_system_performance(loop_times)
        self.check_battery_status()
        
        return True
    
    def get_all_sensor_data(self):
        """Get all sensor data including enhanced features"""
        location_info = self.gps_location_detector.get_location_info()
        
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
            'max_loop_time': self.max_loop_time
        }
        
        # Enhanced data
        enhanced_data = {
            # Location
            'current_location': location_info['location'],
            'location_confidence': location_info['confidence'],
            'location_description': f"{location_info['location']} ({location_info['confidence']}%)",
            
            # GPS
            'gps_satellites': location_info['gps_satellites'],
            'gps_speed_kmh': location_info['gps_speed_kmh'],
            'gps_fix': location_info['gps_fix'],
            'gps_quality': self.gps_location_detector.get_gps_quality_description(),
            
            # Weather
            'weather_forecast_type': self.weather_forecast_type,
            'weather_confidence': self.weather_confidence,
            'weather_description': self.weather_description,
            'fog_risk': self.fog_risk,
            'storm_risk': self.storm_risk,
            'dew_point': self.dew_point,
            'pressure_tendency': self.pressure_tendency,
            
            # Power
            'battery_usage_estimate': self.battery_usage_estimate,
            
            # Legacy compatibility
            'pressure_trend': self.pressure_trend,
            'pressure_change_rate': self.pressure_tendency,
            'weather_forecast': self.weather_forecast
        }
        
        base_data.update(enhanced_data)
        return base_data
    
    def initialize_all_sensors(self):
        """Initialize all sensors"""
        print("🚀 Starting AI Field Analyzer v1.9 sensor initialization...")
        
        success_count = 0
        total_steps = 2
        
        if self.initialize_hardware_pins():
            success_count += 1
            print("✅ Step 1/2: Hardware pins initialized")
        else:
            print("❌ Step 1/2: Hardware pin initialization failed")
        
        if self.initialize_i2c_sensors():
            success_count += 1
            print("✅ Step 2/2: I2C sensors initialized")
        else:
            print("❌ Step 2/2: I2C sensor initialization failed")
        
        success_rate = (success_count / total_steps) * 100
        print(f"📊 Initialization complete: {success_count}/{total_steps} ({success_rate:.0f}%)")
        
        return success_count >= 1
    
    def run_diagnostics(self):
        """Run system diagnostics"""
        print("\n🔧 Running System Diagnostics")
        print("=" * 50)
        
        # Sensor status
        print("\n📡 SENSOR STATUS:")
        sensors = {
            'i2c_bus': self.i2c is not None,
            'scd41': self.scd41 is not None,
            'tsl2591': self.tsl is not None,
            'bmp180': self.bmp is not None,
            'geiger_counter': self.geiger_pin is not None,
            'battery_monitor': self.battery_low_pin is not None
        }
        
        for sensor, active in sensors.items():
            icon = "✅" if active else "❌"
            print(f"  {icon} {sensor.upper()}")
        
        # Location status
        location_info = self.gps_location_detector.get_location_info()
        print(f"\n📍 LOCATION STATUS:")
        print(f"  Current: {location_info['location']} ({location_info['confidence']}% confidence)")
        print(f"  GPS: {location_info['gps_satellites']} satellites")
        
        # Weather status
        print(f"\n🌪️ WEATHER STATUS:")
        print(f"  Active: {self.weather_system.weather_active}")
        print(f"  Location: {self.current_location}")
        print(f"  Forecast: {self.weather_forecast_type}")
        
        # Performance status
        print(f"\n⚡ PERFORMANCE STATUS:")
        print(f"  CPU Usage: {self.cpu_usage:.1f}%")
        print(f"  Memory Usage: {self.memory_usage:.1f}%")
        print(f"  Battery Estimate: {self.battery_usage_estimate}%")
        
        # Polling configuration
        print(f"\n🔄 POLLING CONFIG ({self.current_location}):")
        config = self.location_polling_config[self.current_location]
        for sensor, interval in config.items():
            status_text = f"{interval}s" if interval > 0 else "OFF"
            print(f"  {sensor.upper()}: {status_text}")
        
        print("\n✅ Diagnostics complete!")

# =============================================================================
# TESTING FUNCTIONS
# =============================================================================

def test_enhanced_sensor_manager():
    """Test the enhanced sensor manager"""
    print("\n🧪 Testing Enhanced AI Field Analyzer v1.9")
    print("=" * 60)
    
    # Initialize
    print("🔧 Initializing enhanced sensor manager...")
    sensors = AIFieldSensorManager()
    
    # Test initialization
    print("\n--- Hardware Initialization Test ---")
    init_success = sensors.initialize_all_sensors()
    print(f"Initialization: {'✅ SUCCESS' if init_success else '❌ FAILED'}")
    
    # Test location scenarios
    print("\n--- Location Detection Test ---")
    test_scenarios = [
        ("Outdoor", 8, 1200, "Bright sunny day"),
        ("Indoor", 2, 300, "Inside building"),  
        ("Cave", 0, 20, "Underground"),
    ]
    
    for scenario, sats, lux, description in test_scenarios:
        print(f"\n  Testing {scenario}: {description}")
        
        # Simulate readings
        sensors.lux = lux
        sensors.gps_location_detector.update_gps_data(sats, 0)
        sensors.update_all_sensors()
        
        # Get results
        sensor_data = sensors.get_all_sensor_data()
        
        print(f"    Detected: {sensor_data['current_location']} ({sensor_data['location_confidence']}%)")
        print(f"    Weather: {sensor_data['weather_forecast_type']}")
        print(f"    Battery: {sensor_data['battery_usage_estimate']}%")
        
        time.sleep(1)
    
    # Test weather
    print("\n--- Weather System Test ---")
    sensors.current_location = "OUTDOOR"
    
    weather_tests = [
        (22.0, 45, "Normal conditions"),
        (15.0, 95, "Fog conditions"),
    ]
    
    for temp, humidity, description in weather_tests:
        print(f"\n  Testing: {description}")
        sensors.temperature = temp
        sensors.humidity = humidity
        sensors.update_weather_system()
        
        sensor_data = sensors.get_all_sensor_data()
        print(f"    Forecast: {sensor_data['weather_forecast_type']} ({sensor_data['weather_confidence']}%)")
        print(f"    Fog Risk: {sensor_data['fog_risk']}")
        time.sleep(1)
    
    # Run diagnostics
    print("\n--- System Diagnostics ---")
    sensors.run_diagnostics()
    
    print(f"\n✅ Enhanced sensor manager test complete!")
    print("🎯 Ready for integration!")
    
    return sensors

if __name__ == "__main__":
    test_enhanced_sensor_manager()

