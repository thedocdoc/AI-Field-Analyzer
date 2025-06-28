"""
AI Field Analyzer v1.8 - Unified Sensor Management Class
--------------------------------------------------------
Handles all sensor initialization, calibration, and data acquisition
for the AI Field Analyzer project.

Sensors Managed:
- SCD41: CO2, Temperature, Humidity, VOC estimation
- TSL2591: Light/Lux measurement  
- BMP180: Barometric pressure, altitude, storm prediction
- Geiger Counter: Radiation detection (CPM and µSv/h)
- System sensors: Battery, CPU temperature, performance metrics

© 2025 Apollo Timbers. MIT License.
"""

import time
import board
import busio
import digitalio
import microcontroller
import adafruit_scd4x
import adafruit_tsl2591
import gc
import struct

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
        
        # Check if device is present and read calibration
        if self._check_device():
            self._read_calibration()
            print("✅ BMP180 initialized successfully")
        else:
            raise RuntimeError("BMP180 not found at 0x77")
    
    def _check_device(self):
        """Check if BMP180 is present by reading chip ID"""
        try:
            while not self.i2c.try_lock():
                pass
            
            # Read chip ID register (0xD0) - should return 0x55 for BMP180
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
        """Read calibration coefficients from EEPROM"""
        try:
            while not self.i2c.try_lock():
                pass
            
            # Read 22 bytes of calibration data starting at 0xAA
            self.i2c.writeto(self.address, bytes([0xAA]))
            cal_data = bytearray(22)
            self.i2c.readfrom_into(self.address, cal_data)
            
            # Unpack calibration coefficients (big-endian format)
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
        """Read raw temperature data"""
        try:
            while not self.i2c.try_lock():
                pass
            
            # Start temperature measurement
            self.i2c.writeto(self.address, bytes([0xF4, 0x2E]))
            time.sleep(0.005)  # Wait 4.5ms for measurement
            
            # Read temperature result
            self.i2c.writeto(self.address, bytes([0xF6]))
            temp_data = bytearray(2)
            self.i2c.readfrom_into(self.address, temp_data)
            
            raw_temp = (temp_data[0] << 8) + temp_data[1]
            return raw_temp
            
        finally:
            self.i2c.unlock()
    
    def _read_raw_pressure(self, oss=0):
        """Read raw pressure data (oss = oversampling setting 0-3)"""
        try:
            while not self.i2c.try_lock():
                pass
            
            # Start pressure measurement
            cmd = 0x34 + (oss << 6)
            self.i2c.writeto(self.address, bytes([0xF4, cmd]))
            
            # Wait time depends on oversampling
            wait_times = [0.005, 0.008, 0.014, 0.026]  # 4.5ms, 7.5ms, 13.5ms, 25.5ms
            time.sleep(wait_times[oss])
            
            # Read pressure result (3 bytes)
            self.i2c.writeto(self.address, bytes([0xF6]))
            press_data = bytearray(3)
            self.i2c.readfrom_into(self.address, press_data)
            
            raw_pressure = ((press_data[0] << 16) + (press_data[1] << 8) + press_data[2]) >> (8 - oss)
            return raw_pressure
            
        finally:
            self.i2c.unlock()
    
    @property
    def temperature(self):
        """Get compensated temperature in Celsius"""
        raw_temp = self._read_raw_temperature()
        
        # Calculate true temperature using calibration coefficients
        X1 = ((raw_temp - self.cal_AC6) * self.cal_AC5) >> 15
        X2 = (self.cal_MC << 11) // (X1 + self.cal_MD)
        B5 = X1 + X2
        
        temp_c = ((B5 + 8) >> 4) / 10.0
        return temp_c
    
    @property
    def pressure(self):
        """Get compensated pressure in hPa"""
        # Read raw temperature first (needed for pressure calculation)
        raw_temp = self._read_raw_temperature()
        raw_pressure = self._read_raw_pressure(oss=0)  # Standard precision
        
        # Calculate B5 (needed for pressure compensation)
        X1 = ((raw_temp - self.cal_AC6) * self.cal_AC5) >> 15
        X2 = (self.cal_MC << 11) // (X1 + self.cal_MD)
        B5 = X1 + X2
        
        # Calculate true pressure
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
        
        # Convert Pa to hPa
        pressure_hpa = pressure_pa / 100.0
        return pressure_hpa
    
    @property 
    def altitude(self):
        """Calculate altitude based on pressure"""
        pressure_hpa = self.pressure
        altitude_m = 44330 * (1 - (pressure_hpa / 1013.25) ** 0.1903)
        return altitude_m


class AIFieldSensorManager:
    """
    Unified sensor management class for AI Field Analyzer v1.7
    
    Handles initialization, calibration, and data acquisition for all sensors:
    - Environmental sensors (SCD41, TSL2591, BMP180)
    - Radiation detection (Geiger counter)
    - System monitoring (battery, CPU, performance)
    - Weather prediction algorithms
    """
    
    def __init__(self):
        # Sensor instances
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
        
        # Sensor data
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
        self.alpha = 53.032  # Conversion factor
        self.radiation_start_time = 0
        self.count_duration = 120  # 2 minutes
        self.last_pulse_time = 0
        self.previous_geiger_state = True
        
        # Weather prediction
        self.pressure_history = []
        self.pressure_trend = "STABLE"
        self.pressure_change_rate = 0.0
        self.storm_risk = "LOW"
        self.weather_forecast = "STABLE CONDITIONS"
        
        # System monitoring
        self.battery_low = False
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.cpu_temp = 25.0
        self.loop_times = []
        self.avg_loop_time = 0.0
        self.max_loop_time = 0.0
        
        # Update timers
        self.air_quality_last_update = 0
        self.light_last_update = 0
        self.pressure_last_update = 0
        self.pressure_history_update = 0
        self.performance_update_time = 0
        self.battery_check_time = 0
        
        # Configuration constants
        self.RADIATION_WARMUP = 120  # seconds
        self.PRESSURE_HISTORY_INTERVAL = 300  # 5 minutes
        self.PRESSURE_HISTORY_SIZE = 288  # 24 hours
        self.BATTERY_CHECK_INTERVAL = 60  # 1 minute
        
        # Storm prediction thresholds
        self.PRESSURE_RAPID_FALL = -3.0
        self.PRESSURE_FAST_FALL = -1.5
        self.PRESSURE_SLOW_FALL = -0.5
        self.PRESSURE_RAPID_RISE = 3.0
        self.PRESSURE_FAST_RISE = 1.5
        
        # Performance thresholds
        self.CPU_THRESHOLD_CAUTION = 70
        self.CPU_THRESHOLD_DANGER = 85
        self.MEMORY_THRESHOLD_CAUTION = 80
        self.MEMORY_THRESHOLD_DANGER = 90
        
        print("🔧 AI Field Sensor Manager initialized")
    
    def initialize_hardware_pins(self):
        """Initialize all hardware pins"""
        try:
            # Geiger counter
            self.geiger_pin = digitalio.DigitalInOut(board.GP7)
            self.geiger_pin.switch_to_input(pull=digitalio.Pull.UP)
            
            # Piezo buzzer
            self.piezo_pin = digitalio.DigitalInOut(board.GP20)
            self.piezo_pin.switch_to_output()
            
            # Button and flashlight
            self.button = digitalio.DigitalInOut(board.GP3)
            self.button.switch_to_input(pull=digitalio.Pull.UP)
            
            self.flashlight = digitalio.DigitalInOut(board.GP2)
            self.flashlight.switch_to_output()
            self.flashlight.value = False
            
            # Battery monitor
            self.battery_low_pin = digitalio.DigitalInOut(board.GP0)
            self.battery_low_pin.switch_to_input(pull=digitalio.Pull.UP)
            
            # Initialize radiation timing
            self.radiation_start_time = time.monotonic()
            
            print("✅ Hardware pins initialized")
            return True
            
        except Exception as e:
            print(f"❌ Hardware pin initialization failed: {e}")
            return False
    
    def initialize_i2c_sensors(self):
        """Initialize all I2C sensors with error handling"""
        sensors_initialized = 0
        total_sensors = 3
        
        try:
            # Initialize I2C bus
            self.i2c = busio.I2C(board.GP5, board.GP4)
            print("✅ I2C bus initialized")
            
            # Initialize SCD41 (CO2, Temperature, Humidity)
            try:
                self.scd41 = adafruit_scd4x.SCD4X(self.i2c)
                self.scd41.start_periodic_measurement()
                sensors_initialized += 1
                print("✅ SCD41 air quality sensor ready")
            except Exception as e:
                print(f"❌ SCD41 initialization failed: {e}")
                self.scd41 = None
            
            # Initialize TSL2591 (Light sensor)
            try:
                self.tsl = adafruit_tsl2591.TSL2591(self.i2c)
                self.tsl.gain = adafruit_tsl2591.GAIN_LOW
                self.tsl.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
                sensors_initialized += 1
                print("✅ TSL2591 light sensor ready")
            except Exception as e:
                print(f"❌ TSL2591 initialization failed: {e}")
                self.tsl = None
            
            # Initialize BMP180 (Pressure sensor)
            try:
                self.bmp = SimpleBMP180(self.i2c)
                # Take initial reading
                self.pressure_hpa = self.bmp.pressure
                self.altitude_m = self.bmp.altitude
                self.update_pressure_history(self.pressure_hpa)
                sensors_initialized += 1
                print(f"✅ BMP180 sensor ready - Initial: {self.pressure_hpa:.1f} hPa, {self.altitude_m:.0f}m")
            except Exception as e:
                print(f"❌ BMP180 initialization failed: {e}")
                self.bmp = None
                
        except Exception as e:
            print(f"❌ I2C bus initialization failed: {e}")
            return False
        
        success_rate = (sensors_initialized / total_sensors) * 100
        print(f"📊 Sensor initialization: {sensors_initialized}/{total_sensors} ({success_rate:.0f}%)")
        
        return sensors_initialized > 0
    
    def take_initial_readings(self):
        """Take initial sensor readings during startup"""
        print("📊 Taking initial sensor readings...")
        
        # SCD41 readings
        if self.scd41:
            try:
                if self.scd41.data_ready:
                    self.co2 = self.scd41.CO2
                    self.temperature = self.scd41.temperature
                    self.humidity = self.scd41.relative_humidity
                    self.voc = max(0, (self.co2 - 400) * 2)  # Rough VOC estimate
                    print(f"✅ Initial SCD41: CO2={self.co2}, T={self.temperature:.1f}C, RH={self.humidity:.1f}%, VOC~{self.voc}")
                else:
                    print("⚠️ SCD41 data not ready yet - using defaults")
            except Exception as e:
                print(f"⚠️ Initial SCD41 read failed: {e}")
        
        # Light reading
        if self.tsl:
            try:
                self.lux = self.tsl.lux
                if self.lux is None:
                    self.lux = 0
                print(f"✅ Initial light level: {self.lux:.0f} lux")
            except Exception as e:
                print(f"⚠️ Initial light read failed: {e}")
        
        # Pressure reading
        if self.bmp:
            try:
                self.pressure_hpa = self.bmp.pressure
                self.altitude_m = self.bmp.altitude
                self.update_pressure_history(self.pressure_hpa)
                print(f"✅ Initial pressure: {self.pressure_hpa:.1f} hPa, altitude: {self.altitude_m:.0f}m")
            except Exception as e:
                print(f"⚠️ Initial pressure read failed: {e}")
    
    def update_radiation_detection(self):
        """High-priority radiation pulse detection"""
        current_time = time.monotonic()
        current_geiger_state = self.geiger_pin.value
        
        # Detect pulse on falling edge
        if self.previous_geiger_state and not current_geiger_state and current_time - self.last_pulse_time > 0.001:
            self.pulse_count += 1
            self.last_pulse_time = current_time
            
            # Brief piezo click
            self.piezo_pin.value = True
            self.piezo_pin.value = False
        
        self.previous_geiger_state = current_geiger_state
        
        # Calculate CPM every 2 minutes
        if current_time - self.radiation_start_time >= self.count_duration:
            self.cpm = self.pulse_count
            self.usv_h = self.cpm / self.alpha
            self.pulse_count = 0
            self.radiation_start_time = current_time
    
    def update_air_quality(self, force=False):
        """Update CO2, temperature, humidity, and VOC"""
        current_time = time.monotonic()
        
        if not force and current_time - self.air_quality_last_update < 5:
            return False
            
        if self.scd41:
            try:
                if self.scd41.data_ready:
                    self.co2 = self.scd41.CO2
                    self.temperature = self.scd41.temperature
                    self.humidity = self.scd41.relative_humidity
                    # Enhanced VOC estimate
                    self.voc = max(0, int((self.co2 - 400) * 1.5 + (self.humidity - 40) * 5))
                    self.air_quality_last_update = current_time
                    return True
            except Exception as e:
                print(f"⚠️ SCD41 read error: {e}")
        
        return False
    
    def update_light_sensor(self, force=False):
        """Update light/lux readings"""
        current_time = time.monotonic()
        
        if not force and current_time - self.light_last_update < 4:
            return False
            
        if self.tsl:
            try:
                self.lux = self.tsl.lux
                if self.lux is None:
                    self.lux = 120000  # Overload condition
                self.light_last_update = current_time
                return True
            except Exception as e:
                print(f"⚠️ TSL2591 read error: {e}")
        
        return False
    
    def update_pressure_sensor(self, force=False):
        """Update pressure and altitude readings"""
        current_time = time.monotonic()
        
        if not force and current_time - self.pressure_last_update < 3:
            return False
            
        if self.bmp:
            try:
                self.pressure_hpa = self.bmp.pressure
                self.altitude_m = self.bmp.altitude
                self.pressure_last_update = current_time
                
                # Update pressure history for storm prediction every 5 minutes
                if current_time - self.pressure_history_update >= self.PRESSURE_HISTORY_INTERVAL:
                    self.update_pressure_history(self.pressure_hpa)
                    self.pressure_history_update = current_time
                
                return True
            except Exception as e:
                print(f"⚠️ BMP180 read error: {e}")
        
        return False
    
    def update_pressure_history(self, current_pressure):
        """Maintain 24-hour pressure history for storm prediction"""
        current_time = time.monotonic()
        
        # Add current reading with timestamp
        self.pressure_history.append((current_time, current_pressure))
        
        # Remove readings older than 24 hours
        cutoff_time = current_time - (24 * 3600)
        self.pressure_history = [(t, p) for t, p in self.pressure_history if t > cutoff_time]
        
        # Analyze pressure trends
        self.analyze_pressure_trends()
    
    def analyze_pressure_trends(self):
        """Analyze pressure trends for storm prediction"""
        if len(self.pressure_history) < 2:
            self.pressure_trend = "INSUFFICIENT_DATA"
            self.pressure_change_rate = 0.0
            self.storm_risk = "UNKNOWN"
            self.weather_forecast = "Collecting baseline data..."
            return
        
        current_time = time.monotonic()
        current_pressure = self.pressure_history[-1][1]
        
        # Find pressure readings from 1, 3, and 6 hours ago
        one_hour_ago = current_time - 3600
        three_hours_ago = current_time - (3 * 3600)
        six_hours_ago = current_time - (6 * 3600)
        
        pressure_1h = self.find_closest_pressure(one_hour_ago)
        pressure_3h = self.find_closest_pressure(three_hours_ago)
        pressure_6h = self.find_closest_pressure(six_hours_ago)
        
        # Calculate hourly change rate
        if pressure_1h is not None:
            self.pressure_change_rate = current_pressure - pressure_1h
        else:
            self.pressure_change_rate = 0.0
        
        # Determine trend
        if self.pressure_change_rate > 0.5:
            self.pressure_trend = "RISING"
        elif self.pressure_change_rate < -0.5:
            self.pressure_trend = "FALLING"
        else:
            self.pressure_trend = "STABLE"
        
        # Storm risk assessment
        self.assess_storm_risk(current_pressure, pressure_1h, pressure_3h, pressure_6h)
    
    def find_closest_pressure(self, target_time):
        """Find pressure reading closest to target time"""
        if not self.pressure_history:
            return None
        
        closest_reading = min(self.pressure_history, key=lambda x: abs(x[0] - target_time))
        
        # Only return if within 30 minutes of target time
        if abs(closest_reading[0] - target_time) <= 1800:
            return closest_reading[1]
        return None
    
    def assess_storm_risk(self, current_p, pressure_1h, pressure_3h, pressure_6h):
        """Assess storm risk based on pressure patterns"""
        if pressure_1h is None:
            self.storm_risk = "UNKNOWN"
            self.weather_forecast = "Insufficient data for prediction"
            return
        
        change_1h = current_p - pressure_1h if pressure_1h else 0
        change_3h = (current_p - pressure_3h) / 3 if pressure_3h else 0
        change_6h = (current_p - pressure_6h) / 6 if pressure_6h else 0
        
        # Storm risk assessment
        if change_1h <= self.PRESSURE_RAPID_FALL:
            self.storm_risk = "SEVERE"
            if change_3h <= -2.0:
                self.weather_forecast = "SEVERE STORM IMMINENT - Seek shelter immediately!"
            else:
                self.weather_forecast = "STRONG STORM APPROACHING - Take precautions within 2-4 hours"
        
        elif change_1h <= self.PRESSURE_FAST_FALL:
            self.storm_risk = "HIGH"
            if change_3h <= -1.0:
                self.weather_forecast = "STORM LIKELY - Weather deteriorating in 4-8 hours"
            else:
                self.weather_forecast = "UNSETTLED WEATHER - Monitor conditions closely"
        
        elif change_1h <= self.PRESSURE_SLOW_FALL:
            self.storm_risk = "MODERATE"
            self.weather_forecast = "WEATHER CHANGE POSSIBLE - Conditions may deteriorate slowly"
        
        elif change_1h >= self.PRESSURE_RAPID_RISE:
            self.storm_risk = "CLEARING"
            self.weather_forecast = "RAPID CLEARING - Conditions improving quickly"
        
        elif change_1h >= self.PRESSURE_FAST_RISE:
            self.storm_risk = "IMPROVING"
            self.weather_forecast = "WEATHER IMPROVING - Clearing conditions ahead"
        
        else:
            self.storm_risk = "LOW"
            self.weather_forecast = "STABLE CONDITIONS - No significant weather changes expected"
        
        # Special conditions
        if current_p < 980:
            if self.storm_risk not in ["SEVERE", "HIGH"]:
                self.storm_risk = "HIGH"
            self.weather_forecast = f"LOW PRESSURE SYSTEM - {self.weather_forecast}"
        elif current_p > 1030:
            self.storm_risk = "LOW"
            self.weather_forecast = "HIGH PRESSURE - Stable, clear conditions likely"
    
    def update_system_performance(self, loop_times=None):
        """Update system performance metrics"""
        current_time = time.monotonic()
        
        if current_time - self.performance_update_time < 10:
            return False
        
        # CPU temperature
        try:
            self.cpu_temp = microcontroller.cpu.temperature
        except:
            self.cpu_temp = 25.0
        
        # Memory usage
        try:
            gc.collect()
            total_memory = gc.mem_alloc() + gc.mem_free()
            used_memory = gc.mem_alloc()
            self.memory_usage = (used_memory / total_memory) * 100
        except:
            self.memory_usage = 50
        
        # Loop timing statistics
        if loop_times:
            self.loop_times = loop_times[-20:]  # Keep only recent 20 measurements
            self.avg_loop_time = sum(self.loop_times) / len(self.loop_times)
            self.max_loop_time = max(self.loop_times)
            self.cpu_usage = min(100, (self.avg_loop_time / 0.05) * 100)
        else:
            self.cpu_usage = 25
        
        self.performance_update_time = current_time
        return True
    
    def check_battery_status(self):
        """Check PowerBoost 1000C low battery status"""
        current_time = time.monotonic()
        
        if current_time - self.battery_check_time < self.BATTERY_CHECK_INTERVAL:
            return self.battery_low
        
        # PowerBoost LBO pin goes LOW when battery is low
        self.battery_low = not self.battery_low_pin.value
        self.battery_check_time = current_time
        
        return self.battery_low
    
    def is_radiation_ready(self):
        """Check if radiation sensor warmup period is complete"""
        return (time.monotonic() - self.radiation_start_time) >= self.RADIATION_WARMUP
    
    def get_all_sensor_data(self):
        """Get dictionary of all current sensor readings"""
        return {
            'co2': self.co2,
            'voc': self.voc,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'lux': self.lux,
            'pressure_hpa': self.pressure_hpa,
            'altitude_m': self.altitude_m,
            'pressure_trend': self.pressure_trend,
            'pressure_change_rate': self.pressure_change_rate,
            'storm_risk': self.storm_risk,
            'weather_forecast': self.weather_forecast,
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
    
    def update_all_sensors(self, loop_times=None):
        """Update all sensors - call this from main loop"""
        # High priority: radiation detection (call every loop)
        self.update_radiation_detection()
        
        # Medium priority: environmental sensors (time-based updates)
        self.update_air_quality()
        self.update_light_sensor()
        self.update_pressure_sensor()
        
        # Low priority: system monitoring
        self.update_system_performance(loop_times)
        self.check_battery_status()
        
        return True
    
    def initialize_all_sensors(self):
        """Initialize all sensors in sequence with status reporting"""
        print("🚀 Starting AI Field Analyzer v1.7 sensor initialization...")
        
        success_count = 0
        total_steps = 3
        
        # Step 1: Hardware pins
        if self.initialize_hardware_pins():
            success_count += 1
            print("✅ Step 1/3: Hardware pins initialized")
        else:
            print("❌ Step 1/3: Hardware pin initialization failed")
        
        # Step 2: I2C sensors
        if self.initialize_i2c_sensors():
            success_count += 1
            print("✅ Step 2/3: I2C sensors initialized")
        else:
            print("❌ Step 2/3: I2C sensor initialization failed")
        
        # Step 3: Initial readings
        try:
            self.take_initial_readings()
            success_count += 1
            print("✅ Step 3/3: Initial sensor readings completed")
        except Exception as e:
            print(f"❌ Step 3/3: Initial readings failed: {e}")
        
        success_rate = (success_count / total_steps) * 100
        print(f"📊 Sensor initialization complete: {success_count}/{total_steps} ({success_rate:.0f}%)")
        
        # Return True if at least hardware pins and some sensors work
        return success_count >= 2
    
    def get_sensor_status(self):
        """Get detailed sensor status for diagnostics"""
        status = {
            'i2c_bus': self.i2c is not None,
            'scd41': self.scd41 is not None,
            'tsl2591': self.tsl is not None,
            'bmp180': self.bmp is not None,
            'geiger_counter': self.geiger_pin is not None,
            'battery_monitor': self.battery_low_pin is not None,
            'flashlight': self.flashlight is not None,
            'piezo': self.piezo_pin is not None,
            'radiation_ready': self.is_radiation_ready(),
            'pressure_history_points': len(self.pressure_history),
            'last_updates': {
                'air_quality': self.air_quality_last_update,
                'light': self.light_last_update,
                'pressure': self.pressure_last_update,
                'performance': self.performance_update_time,
                'battery': self.battery_check_time
            }
        }
        return status
    
    def print_sensor_summary(self):
        """Print a summary of all sensor readings"""
        data = self.get_all_sensor_data()
        status = self.get_sensor_status()
        
        print("\n" + "="*60)
        print("AI FIELD ANALYZER v1.7 - SENSOR SUMMARY")
        print("="*60)
        
        print(f"🌬️  AIR QUALITY:")
        print(f"    CO2: {data['co2']} ppm")
        print(f"    VOC: {data['voc']} ppb (estimated)")
        print(f"    Temperature: {data['temperature']:.1f}°C")
        print(f"    Humidity: {data['humidity']:.1f}%")
        
        print(f"💡 LIGHT:")
        print(f"    Lux: {data['lux']:.0f}")
        
        print(f"🌪️  WEATHER:")
        print(f"    Pressure: {data['pressure_hpa']:.1f} hPa")
        print(f"    Altitude: {data['altitude_m']:.0f} m")
        print(f"    Trend: {data['pressure_trend']}")
        print(f"    Storm Risk: {data['storm_risk']}")
        print(f"    Forecast: {data['weather_forecast']}")
        
        print(f"☢️  RADIATION:")
        print(f"    CPM: {data['cpm']}")
        print(f"    µSv/h: {data['usv_h']:.3f}")
        print(f"    Ready: {'Yes' if data['radiation_ready'] else 'Warming up'}")
        
        print(f"🖥️  SYSTEM:")
        print(f"    CPU: {data['cpu_usage']:.0f}%")
        print(f"    Memory: {data['memory_usage']:.0f}%")
        print(f"    CPU Temp: {data['cpu_temp']:.1f}°C")
        print(f"    Loop Time: {data['avg_loop_time']*1000:.1f}ms")
        print(f"    Battery: {'LOW' if data['battery_low'] else 'OK'}")
        
        print(f"📊 SENSOR STATUS:")
        for sensor, active in status.items():
            if sensor != 'last_updates':
                status_symbol = "✅" if active else "❌"
                print(f"    {sensor}: {status_symbol}")
        
        print("="*60)
    
    def run_sensor_diagnostics(self):
        """Run comprehensive sensor diagnostics"""
        print("\n🔧 Running sensor diagnostics...")
        
        # Test each sensor individually
        diagnostics = {}
        
        # Test SCD41
        if self.scd41:
            try:
                if self.scd41.data_ready:
                    co2_test = self.scd41.CO2
                    temp_test = self.scd41.temperature
                    humid_test = self.scd41.relative_humidity
                    diagnostics['scd41'] = f"✅ OK - CO2:{co2_test}, T:{temp_test:.1f}C, RH:{humid_test:.1f}%"
                else:
                    diagnostics['scd41'] = "⚠️ Not ready - data pending"
            except Exception as e:
                diagnostics['scd41'] = f"❌ Error: {e}"
        else:
            diagnostics['scd41'] = "❌ Not initialized"
        
        # Test TSL2591
        if self.tsl:
            try:
                lux_test = self.tsl.lux
                diagnostics['tsl2591'] = f"✅ OK - Lux: {lux_test}"
            except Exception as e:
                diagnostics['tsl2591'] = f"❌ Error: {e}"
        else:
            diagnostics['tsl2591'] = "❌ Not initialized"
        
        # Test BMP180
        if self.bmp:
            try:
                pressure_test = self.bmp.pressure
                altitude_test = self.bmp.altitude
                diagnostics['bmp180'] = f"✅ OK - P:{pressure_test:.1f}hPa, Alt:{altitude_test:.0f}m"
            except Exception as e:
                diagnostics['bmp180'] = f"❌ Error: {e}"
        else:
            diagnostics['bmp180'] = "❌ Not initialized"
        
        # Test hardware pins
        try:
            geiger_state = self.geiger_pin.value
            battery_state = self.battery_low_pin.value
            diagnostics['hardware'] = f"✅ OK - Geiger:{geiger_state}, Battery:{battery_state}"
        except Exception as e:
            diagnostics['hardware'] = f"❌ Error: {e}"
        
        # Print diagnostics
        print("Diagnostics Results:")
        for component, result in diagnostics.items():
            print(f"  {component}: {result}")
        
        return diagnostics
    
    def emergency_sensor_reset(self):
        """Emergency sensor reset procedure"""
        print("🚨 Emergency sensor reset initiated...")
        
        try:
            # Stop SCD41 measurements
            if self.scd41:
                try:
                    self.scd41.stop_periodic_measurement()
                    time.sleep(0.5)
                    self.scd41.start_periodic_measurement()
                    print("✅ SCD41 reset complete")
                except:
                    print("❌ SCD41 reset failed")
            
            # Reset pressure history
            self.pressure_history = []
            print("✅ Pressure history cleared")
            
            # Reset radiation counters
            self.pulse_count = 0
            self.cpm = 0
            self.usv_h = 0.0
            self.radiation_start_time = time.monotonic()
            print("✅ Radiation counters reset")
            
            # Force garbage collection
            gc.collect()
            print("✅ Memory cleanup complete")
            
            print("🔧 Emergency reset complete - monitoring resumed")
            
        except Exception as e:
            print(f"❌ Emergency reset failed: {e}")
    
    def __del__(self):
        """Cleanup when sensor manager is destroyed"""
        try:
            # Stop SCD41 measurements
            if self.scd41:
                self.scd41.stop_periodic_measurement()
            
            # Turn off flashlight
            if self.flashlight:
                self.flashlight.value = False
            
            print("🧹 Sensor manager cleanup complete")
        except:
            pass
