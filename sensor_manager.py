"""
AI Field Analyzer v1.9 - Enhanced Sensor Management System (Weather Removed)
---------------------------------------------------------------------------
Clean version with weather functionality removed - using separate weather class.
Updated with BMP390 sensor support.

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
# MAIN ENHANCED SENSOR MANAGER
# =============================================================================

class AIFieldSensorManager:
    """Enhanced AI Field Analyzer sensor management system"""
    
    def __init__(self):
        # Hardware sensor instances
        self.i2c = None
        self.scd41 = None
        self.tsl = None
        self.bmp390 = None
        
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
        self.gps_last_update = 0
        self.GPS_UPDATE_INTERVAL = 5
        
        # Location-aware polling configuration
        self.location_polling_config = {
            "OUTDOOR": {"gps": 5, "air": 5, "light": 3, "pressure": 10, "radiation": 1},
            "INDOOR":  {"gps": 30, "air": 3, "light": 10, "pressure": 15, "radiation": 1},
            "VEHICLE": {"gps": 3, "air": 8, "light": 15, "pressure": 0, "radiation": 1},
            "CAVE":    {"gps": 0, "air": 2, "light": 30, "pressure": 15, "radiation": 1}
        }
        
        # Polling timing
        self.last_poll_times = {
            "gps": 0, "air": 0, "light": 0, "pressure": 0, "radiation": 0
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
        self.radiation_warmup_start = 0    # Separate warmup timer
        self.radiation_count_start = 0     # Renamed from radiation_start_time
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
        
        # Update timers
        self.air_quality_last_update = 0
        self.light_last_update = 0
        self.pressure_last_update = 0
        self.performance_update_time = 0
        self.battery_check_time = 0
        
        # Configuration
        self.RADIATION_WARMUP = 120
        self.BATTERY_CHECK_INTERVAL = 60
        
        print("🔧 Enhanced AI Field Sensor Manager v1.9 initialized (Weather Removed, BMP390)")
    
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
       
           # Set both timers once at startup
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
            
            # BMP390
            try:
                self.bmp390 = adafruit_bmp3xx.BMP3XX_I2C(self.i2c)
                # Configure BMP390 settings for better accuracy
                self.bmp390.pressure_oversampling = 4
                self.bmp390.temperature_oversampling = 1
                self.bmp390.filter_coefficient = 8
                self.bmp390.standby_time = 5
                
                # Set sea level pressure for altitude calculations
                self.bmp390.sea_level_pressure = 1013.25
                
                # Read initial values
                self.pressure_hpa = self.bmp390.pressure
                self.altitude_m = self.bmp390.altitude
                
                sensors_initialized += 1
                print(f"✅ BMP390 sensor ready - Initial: {self.pressure_hpa:.1f} hPa, {self.altitude_m:.1f}m")
                
            except Exception as e:
                print(f"❌ BMP390 initialization failed: {e}")
                self.bmp390 = None
                
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
       """Update radiation detection"""
       current_time = time.monotonic()
       current_geiger_state = self.geiger_pin.value
   
       # Pulse detection
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
       """Check if radiation sensor is ready"""
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
        if self.bmp390:
            try:
                self.pressure_hpa = self.bmp390.pressure
                self.altitude_m = self.bmp390.altitude
                return True
            except Exception as e:
                print(f"⚠️ BMP390 read error: {e}")
        return False
    
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
    
    def set_sea_level_pressure(self, pressure_hpa):
        """Set sea level pressure for altitude calculations"""
        if self.bmp390:
            self.bmp390.sea_level_pressure = pressure_hpa
            print(f"📊 Sea level pressure set to {pressure_hpa:.1f} hPa")
    
    def get_bmp390_temperature(self):
        """Get temperature from BMP390 sensor"""
        if self.bmp390:
            try:
                return self.bmp390.temperature
            except Exception as e:
                print(f"⚠️ BMP390 temperature read error: {e}")
                return None
        return None
    
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
        
        # System monitoring
        self.update_system_performance(loop_times)
        self.check_battery_status()
        
        return True
    
    def get_all_sensor_data(self):
        """Get all sensor data"""
        location_info = self.gps_location_detector.get_location_info()
        
        # Get BMP390 temperature if available
        bmp390_temp = self.get_bmp390_temperature()
        
        return {
            # Basic sensor data
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
            
            # BMP390 specific data
            'bmp390_temperature': bmp390_temp,
            'sea_level_pressure': self.bmp390.sea_level_pressure if self.bmp390 else 1013.25,
            
            # Location data
            'current_location': location_info['location'],
            'location_confidence': location_info['confidence'],
            'location_description': f"{location_info['location']} ({location_info['confidence']}%)",
            
            # GPS data
            'gps_satellites': location_info['gps_satellites'],
            'gps_speed_kmh': location_info['gps_speed_kmh'],
            'gps_fix': location_info['gps_fix'],
            'gps_quality': self.gps_location_detector.get_gps_quality_description(),
            
            # Power data
            'battery_usage_estimate': self.battery_usage_estimate,
        }
    
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
            'bmp390': self.bmp390 is not None,
            'geiger_counter': self.geiger_pin is not None,
            'battery_monitor': self.battery_low_pin is not None
        }
        
        for sensor, active in sensors.items():
            icon = "✅" if active else "❌"
            print(f"  {icon} {sensor.upper()}")
        
        # BMP390 specific diagnostics
        if self.bmp390:
            print(f"\n📊 BMP390 STATUS:")
            print(f"  Pressure Oversampling: {self.bmp390.pressure_oversampling}")
            print(f"  Temperature Oversampling: {self.bmp390.temperature_oversampling}")
            print(f"  Filter Coefficient: {self.bmp390.filter_coefficient}")
            print(f"  Sea Level Pressure: {self.bmp390.sea_level_pressure:.1f} hPa")
        
        # Location status
        location_info = self.gps_location_detector.get_location_info()
        print(f"\n📍 LOCATION STATUS:")
        print(f"  Current: {location_info['location']} ({location_info['confidence']}% confidence)")
        print(f"  GPS: {location_info['gps_satellites']} satellites")
        
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
    print("\n🧪 Testing Enhanced AI Field Analyzer v1.9 (BMP390 Version)")
    print("=" * 60)
    
    # Initialize
    print("🔧 Initializing enhanced sensor manager...")
    sensors = AIFieldSensorManager()
    
    # Test initialization
    print("\n--- Hardware Initialization Test ---")
    init_success = sensors.initialize_all_sensors()
    print(f"Initialization: {'✅ SUCCESS' if init_success else '❌ FAILED'}")
    
    # Test BMP390 specific features
    print("\n--- BMP390 Specific Tests ---")
    if sensors.bmp390:
        print("  Testing sea level pressure adjustment...")
        sensors.set_sea_level_pressure(1010.0)
        time.sleep(0.1)
        
        sensor_data = sensors.get_all_sensor_data()
        print(f"  BMP390 Temperature: {sensor_data['bmp390_temperature']:.1f}°C")
        print(f"  Pressure: {sensor_data['pressure_hpa']:.1f} hPa")
        print(f"  Altitude: {sensor_data['altitude_m']:.1f} m")
        print(f"  Sea Level Pressure: {sensor_data['sea_level_pressure']:.1f} hPa")
    else:
        print("  ❌ BMP390 not available for testing")
    
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
        print(f"    Battery: {sensor_data['battery_usage_estimate']}%")
        print(f"    GPS Quality: {sensor_data['gps_quality']}")
        
        time.sleep(1)
    
    # Test basic sensor readings
    print("\n--- Basic Sensor Test ---")
    sensors.current_location = "OUTDOOR"
    sensors.update_all_sensors()
    
    sensor_data = sensors.get_all_sensor_data()
    print(f"  CO2: {sensor_data['co2']} ppm")
    print(f"  Temperature: {sensor_data['temperature']:.1f}°C")
    print(f"  Humidity: {sensor_data['humidity']:.1f}%")
    print(f"  Light: {sensor_data['lux']} lux")
    print(f"  Pressure: {sensor_data['pressure_hpa']:.1f} hPa")
    print(f"  Altitude: {sensor_data['altitude_m']:.1f} m")
    print(f"  Radiation: {sensor_data['cpm']} CPM ({'Ready' if sensor_data['radiation_ready'] else 'Warming up'})")
    
    # Run diagnostics
    print("\n--- System Diagnostics ---")
    sensors.run_diagnostics()
    
    print(f"\n✅ Enhanced sensor manager test complete!")
    print("🎯 Ready for integration with separate weather class!")
    print("🌟 BMP390 features: Higher accuracy, configurable oversampling, and built-in filtering!")
    
    return sensors

if __name__ == "__main__":
    test_enhanced_sensor_manager()
