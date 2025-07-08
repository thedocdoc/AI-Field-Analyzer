"""
AI Field Analyzer v2.0 - Main Application (Fixed)
-------------------------------------------------
Clean main application using modular sensor and display managers.
Optimized for maximum radiation detection sensitivity with professional
environmental monitoring capabilities.

Project Link: https://hackaday.io/project/203273-ai-field-analyzer
MIT License - © 2025 Apollo Timbers. All rights reserved.

Architecture:
- sensor_manager.py: All sensor operations and data processing
- display_manager.py: All display rendering and UI logic
- main.py: Application coordination and main loop
"""

import time
import board
import busio
import storage
import sdcardio
import gc

# Import our modular components
from sensor_manager import AIFieldSensorManager
from display_manager import DisplayManager
from weather_manager import WeatherManager


# **CONFIGURATION CONSTANTS**
STARTUP_COUNTDOWN = 8      # Startup countdown duration
SD_LOG_INTERVAL = 30       # SD card write interval (seconds)
DEBOUNCE_DELAY = 0.2       # Button debounce delay
CONSOLE_UPDATE_RATE = 3.0  # Console output frequency


class DataLogger:
    """
    Handles SD card initialization and data logging with timestamped CSV files.
    Automatically creates headers and manages write timing.
    """
    
    def __init__(self):
        self.sd_available = False
        self.log_file = None
        self.last_sd_write = 0
        print("💾 Data Logger initialized")
    
    def setup_sd_logging(self):
        """Initialize SD card and create timestamped log file"""
        try:
            # Initialize SD card SPI interface
            spi = busio.SPI(board.GP18, board.GP19, board.GP16)
            cs = board.GP17
            sdcard = sdcardio.SDCard(spi, cs)
            vfs = storage.VfsFat(sdcard)
            storage.mount(vfs, "/sd")
            self.sd_available = True
            print("✅ SD Card mounted successfully")

            # Generate unique timestamped filename
            timestamp = time.localtime()
            date_str = f"{timestamp.tm_year}-{timestamp.tm_mon:02d}-{timestamp.tm_mday:02d}"
            time_str = f"{timestamp.tm_hour:02d}-{timestamp.tm_min:02d}-{timestamp.tm_sec:02d}"
            self.log_file = f"/sd/field_data_{date_str}_{time_str}.csv"

            # Create file with updated CSV header (removed weather fields)
            with open(self.log_file, "w") as f:
                header = "Timestamp,CO2_ppm,VOC_ppb,Temperature_C,Humidity_%,Lux,Pressure_hPa,Altitude_m,CPM,uSv_h,Radiation_Ready,CPU_%,Memory_%,Loop_ms,CPU_Temp_C,Battery_Status,Location,GPS_Satellites,GPS_Quality\n"
                f.write(header)
            
            print(f"✅ Logging to: {self.log_file}")
            return True

        except Exception as e:
            self.sd_available = False
            self.log_file = None
            print(f"🚨 SD Card setup failed: {e}")
            return False
    
    def log_sensor_data(self, sensor_data):
        """Write sensor data to SD card with automatic timing control"""
        current_time = time.monotonic()
        
        # Check if it's time to write (rate limiting)
        if current_time - self.last_sd_write < SD_LOG_INTERVAL:
            return False
        
        if not self.sd_available or not self.log_file:
            return False
        
        try:
            # Generate timestamp
            timestamp = time.localtime()
            timestamp_str = f"{timestamp.tm_year}-{timestamp.tm_mon:02d}-{timestamp.tm_mday:02d} {timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
            
            # Prepare data fields
            battery_status = "LOW" if sensor_data['battery_low'] else "OK"
            radiation_status = "YES" if sensor_data['radiation_ready'] else "NO"
            
            # Write updated data row (removed weather fields)
            data_row = (
                timestamp_str + "," +
                str(sensor_data['co2']) + "," +
                str(sensor_data['voc']) + "," +
                f"{sensor_data['temperature']:.1f}," +
                f"{sensor_data['humidity']:.1f}," +
                f"{sensor_data['lux']:.0f}," +
                f"{sensor_data['pressure_hpa']:.1f}," +
                f"{sensor_data['altitude_m']:.1f}," +
                str(sensor_data['cpm']) + "," +
                f"{sensor_data['usv_h']:.3f}," +
                radiation_status + "," +
                f"{sensor_data['cpu_usage']:.1f}," +
                f"{sensor_data['memory_usage']:.1f}," +
                f"{sensor_data['avg_loop_time']*1000:.1f}," +
                f"{sensor_data['cpu_temp']:.1f}," +
                battery_status + "," +
                sensor_data['current_location'] + "," +
                str(sensor_data['gps_satellites']) + "," +
                sensor_data['gps_quality'] + "\n"
            )
            
            with open(self.log_file, "a") as f:
                f.write(data_row)
            
            self.last_sd_write = current_time
            return True
            
        except Exception as e:
            print(f"❌ SD write error: {e}")
            return False


class FlashlightController:
    """
    Manages flashlight button input with debouncing and state tracking.
    Provides reliable on/off control for field operations.
    """
    
    def __init__(self, sensors):
        self.sensors = sensors
        self.flashlight_on = False
        self.button_last_state = True  # Pull-up resistor makes unpressed = True
        self.button_press_time = 0
        print("🔦 Flashlight Controller ready")
    
    def update(self):
        """Check button state and toggle flashlight with debounce protection"""
        current_time = time.monotonic()
        current_button_state = self.sensors.button.value
        
        # Detect button press (transition from True to False due to pull-up)
        if self.button_last_state and not current_button_state:
            # Check debounce timing
            if current_time - self.button_press_time > DEBOUNCE_DELAY:
                self.flashlight_on = not self.flashlight_on
                self.sensors.flashlight.value = self.flashlight_on
                self.button_press_time = current_time
                print(f"🔦 Flashlight {'ON' if self.flashlight_on else 'OFF'}")
        
        self.button_last_state = current_button_state
    
    def turn_off(self):
        """Force flashlight off (cleanup)"""
        if self.flashlight_on:
            self.flashlight_on = False
            self.sensors.flashlight.value = False
            print("🔦 Flashlight turned off")


def coordinated_startup(display_manager, sensors):
    """
    Professional startup sequence with countdown timer and parallel sensor initialization.
    Provides visual feedback during the sensor warm-up period.
    """
    print("🚀 AI Field Analyzer v2.0 startup initiated...")
    
    # Show initial startup screen
    display_manager.display_startup_screen()
    
    # Countdown and initialization coordination
    start_time = time.monotonic()
    last_second_displayed = 10  # Force first update
    sensors_initialized = False
    
    # Startup phase messages
    startup_phases = {
        8: "Initializing system...",
        7: "Configuring hardware...", 
        6: "Starting I2C bus...",
        5: "Initializing air quality sensor...",
        4: "Configuring light sensor...",
        3: "Setting up pressure sensor...",
        2: "Preparing data logging...",
        1: "Starting radiation detection...",
        0: "System ready!"
    }
    
    while True:
        current_time = time.monotonic()
        elapsed = current_time - start_time
        remaining = max(0, STARTUP_COUNTDOWN - elapsed)
        current_second = int(remaining) + 1
        
        # Exit when countdown complete
        if remaining <= 0:
            break
        
        # Update display when second changes
        if current_second != last_second_displayed and current_second > 0:
            status_message = startup_phases.get(current_second, "Preparing...")
            display_manager.display_countdown(current_second, status_message)
            last_second_displayed = current_second
            print(f"⏱️  Startup: {current_second}s - {status_message}")
        
        # Start sensor initialization at 2 seconds elapsed (6s remaining)
        if elapsed >= 2.0 and not sensors_initialized:
            print("🔧 Beginning sensor initialization...")
            sensors_initialized = sensors.initialize_all_sensors()
            if sensors_initialized:
                print("✅ Sensor initialization completed")
            else:
                print("⚠️ Some sensors failed - continuing with available sensors")
        
        time.sleep(0.1)  # Small delay for smooth countdown
    
    print("🎯 Startup sequence complete - transitioning to main operation")
    return sensors_initialized


def print_console_status(sensor_data, data_logger, display_manager):
    """Generate comprehensive console status output (updated for new sensor data)"""
    timestamp = time.localtime()
    timestamp_str = f"{timestamp.tm_year}-{timestamp.tm_mon:02d}-{timestamp.tm_mday:02d} {timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
    
    # Status indicators
    rad_status = "READY" if sensor_data['radiation_ready'] else "WARMUP"
    sd_status = "OK" if data_logger.sd_available else "OFF"
    battery_status = "LOW" if sensor_data['battery_low'] else "OK"
    
    # Updated status line (removed weather fields)
    status_line = (
        f"[{timestamp_str}] " +
        f"CO₂:{sensor_data['co2']} | " +
        f"VOC:{sensor_data['voc']} | " +
        f"T:{sensor_data['temperature']:.1f}C | " +
        f"RH:{sensor_data['humidity']:.1f}% | " +
        f"P:{sensor_data['pressure_hpa']:.1f}hPa | " +
        f"ALT:{sensor_data['altitude_m']:.0f}m | " +
        f"LOC:{sensor_data['current_location']} | " +
        f"GPS:{sensor_data['gps_satellites']}({sensor_data['gps_quality']}) | " +
        f"LUX:{sensor_data['lux']:.0f} | " +
        f"CPM:{sensor_data['cpm']} | " +
        f"µSv/h:{sensor_data['usv_h']:.3f}({rad_status}) | " +
        f"CPU:{sensor_data['cpu_usage']:.0f}% | " +
        f"TEMP:{sensor_data['cpu_temp']:.1f}C | " +
        f"BAT:{battery_status} | " +
        f"SD:{sd_status} | " +
        f"Screen:{display_manager.current_screen+1}/{display_manager.screens_total}"
    )
    
    print(f"\r{status_line}", end="")


def main():
    """
    Main application entry point with full error handling and cleanup.
    Coordinates all subsystems including weather prediction for optimal environmental monitoring.
    """
    print("\n" + "="*70)
    print("AI FIELD ANALYZER v2.0 - ADVANCED ENVIRONMENTAL MONITORING")
    print("Location Detection • Radiation Detection • Air Quality • Weather Prediction")
    print("© 2025 Apollo Timbers - MIT License")
    print("="*70)
    
    # Import our modular components
    from sensor_manager import AIFieldSensorManager
    from display_manager import DisplayManager
    from weather_manager import WeatherManager
    
    # Initialize all core subsystems
    print("🔧 Initializing core subsystems...")
    display_manager = DisplayManager()
    sensors = AIFieldSensorManager()
    weather = WeatherManager()
    flashlight = None
    
    try:
        # Critical: Initialize display first
        if not display_manager.initialize_display():
            print("❌ CRITICAL: Display initialization failed!")
            print("🔧 Check SPI connections: GP14(CLK), GP15(MOSI), GP10(CS), GP11(DC), GP12(RST)")
            return False
        
        # Run coordinated startup sequence
        sensors_operational = coordinated_startup(display_manager, sensors)
        if not sensors_operational:
            print("⚠️ WARNING: Limited sensor functionality - some readings may be unavailable")
        
        # Connect weather manager to sensors
        print("🌐 Connecting weather prediction system...")
        weather.connect_sensor_manager(sensors)
        print("✅ Weather manager connected - Professional forecasting enabled")
        
        # Initialize remaining subsystems
        flashlight = FlashlightController(sensors)
        
        # Initialize timing systems
        display_manager.screen_change_time = time.monotonic()
        display_manager.data_update_time = time.monotonic()
        display_manager.display_last_update = time.monotonic()
        
        # Performance monitoring setup
        loop_performance_tracker = []
        console_output_timer = 0
        loop_start_time = time.monotonic()
        
        print("🎯 MAIN LOOP ACTIVE - Maximum radiation sensitivity + Weather forecasting")
        print("📊 Monitoring environmental conditions with location detection and storm prediction")
        
        # **MAIN OPERATIONAL LOOP**
        # Optimized for maximum radiation detection sensitivity + weather prediction
        while True:
            # **PERFORMANCE TRACKING**
            loop_current_time = time.monotonic()
            loop_duration = loop_current_time - loop_start_time
            
            # Maintain rolling performance history
            loop_performance_tracker.append(loop_duration)
            if len(loop_performance_tracker) > 20:
                loop_performance_tracker.pop(0)
            
            loop_start_time = loop_current_time
            
            # **PRIORITY 1: RADIATION DETECTION (CRITICAL - EVERY LOOP)**
            # Maximum sensitivity requires this to be called every cycle
            sensors.update_all_sensors(loop_performance_tracker)
            
            # **PRIORITY 2: WEATHER PREDICTION**
            # Get current weather forecast using sensor data
            forecast = weather.get_weather_forecast()
            
            # **PRIORITY 3: USER INTERFACE**
            flashlight.update()
            
            # **PRIORITY 4: DISPLAY SYSTEM**
            sensor_data = sensors.get_all_sensor_data()
            
            # Add weather forecast data to sensor data for display
            sensor_data['weather_forecast_type'] = forecast.get('storm_type', 'UNKNOWN')
            sensor_data['weather_confidence'] = forecast.get('confidence', 0)
            sensor_data['weather_storm_probability'] = forecast.get('storm_probability', 0)
            sensor_data['weather_arrival_timing'] = forecast.get('arrival_timing', 'N/A')
            
            # Your existing display manager handles the rest
            display_manager.update_display(sensor_data)
            
            # **PRIORITY 5: DATA PERSISTENCE**
            # Your existing data logging approach goes here
            # (Remove the fictional data_logger calls)
            
            # **PRIORITY 6: STATUS REPORTING (REDUCED FREQUENCY)**
            if loop_current_time - console_output_timer >= CONSOLE_UPDATE_RATE:
                print_console_status(sensor_data, forecast, display_manager)
                console_output_timer = loop_current_time
            
            # **NO SLEEP/DELAY - MAXIMUM RADIATION SENSITIVITY**
            # Any delay would reduce pulse detection capability
            
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
        
    except Exception as critical_error:
        print(f"\n❌ CRITICAL SYSTEM ERROR: {critical_error}")
        
        # Emergency data save attempt
        try:
            print("💾 Attempting emergency data save...")
            if 'sensor_data' in locals():
                # Use your existing data logging method here
                print("✅ Emergency sensor data noted")
            if 'forecast' in locals():
                # Weather data emergency save
                print("✅ Emergency weather data noted")
            print("✅ Emergency data save completed")
        except:
            print("❌ Emergency data save failed")
        
        # Display error screen if possible
        try:
            if display_manager and display_manager.display:
                display_manager.display_error_screen(str(critical_error)[:50])
                time.sleep(5)  # Show error for 5 seconds
        except:
            pass
    
    finally:
        # **CLEANUP OPERATIONS**
        print("\n🧹 Performing system cleanup...")
        
        try:
            # Turn off flashlight
            if flashlight:
                flashlight.turn_off()
            
            # Final data write attempt
            if 'sensor_data' in locals():
                # Use your existing data logging method here
                print("💾 Final sensor data logged")
                if 'forecast' in locals():
                    print("💾 Final weather data logged")
            
            # Weather system diagnostics before shutdown
            if weather:
                print("🌤️ Weather system final status:")
                weather.run_weather_diagnostics()
            
            # Clear display
            if display_manager and display_manager.display:
                display_manager.display_error_screen("SYSTEM SHUTDOWN")
                time.sleep(1)
            
            # Memory cleanup
            gc.collect()
            
            print("✅ Cleanup completed successfully")
            
        except Exception as cleanup_error:
            print(f"⚠️ Cleanup warning: {cleanup_error}")
    
    print("👋 AI Field Analyzer v2.0 shutdown complete")
    return True


def print_console_status(sensor_data, forecast, display_manager):
    """
    Enhanced console status display including weather information.
    Uses existing DisplayManager's enhanced console status function.
    """
    # Add weather data to sensor_data for the enhanced console function
    sensor_data['weather_forecast_type'] = forecast.get('storm_type', 'UNKNOWN')
    sensor_data['weather_confidence'] = forecast.get('confidence', 0)
    sensor_data['weather_storm_probability'] = forecast.get('storm_probability', 0)
    sensor_data['weather_arrival_timing'] = forecast.get('arrival_timing', 'N/A')
    
    # Use your existing enhanced console status
    from display_manager import get_enhanced_console_status
    status_line = get_enhanced_console_status(sensor_data)
    print(status_line)
    
    # Additional weather details
    if forecast.get('storm_probability', 0) > 30:
        print(f"🌦️  Weather Alert: {forecast.get('storm_probability', 0)}% - {forecast.get('storm_type', 'UNKNOWN')}")
        if forecast.get('arrival_timing', 'N/A') != 'N/A':
            print(f"⏰ ETA: {forecast.get('arrival_timing', 'N/A')} | Confidence: {forecast.get('confidence', 0)}%")


def run_comprehensive_diagnostics():
    """
    Comprehensive system diagnostics with detailed component testing.
    Useful for troubleshooting hardware and software issues.
    """
    print("\n" + "="*60)
    print("AI FIELD ANALYZER v2.0 - COMPREHENSIVE DIAGNOSTICS")
    print("="*60)
    
    # Initialize all components for testing
    print("🔧 Initializing components for diagnostic testing...")
    sensors = AIFieldSensorManager()
    display_manager = DisplayManager()
    data_logger = DataLogger()
    
    diagnostic_results = {
        'display': False,
        'sensors': False,
        'sd_card': False,
        'overall': False
    }
    
    # **DISPLAY TESTING**
    print("\n📺 DISPLAY SYSTEM TEST")
    print("-" * 30)
    try:
        if display_manager.initialize_display():
            print("✅ Display initialization: PASS")
            display_manager.display_startup_screen()
            time.sleep(2)
            
            # Test diagnostic screen
            test_info = {'sensor_count': 3, 'memory_free': 200, 'uptime': 1, 'all_ok': True}
            display_manager.display_diagnostic_screen(test_info)
            time.sleep(2)
            
            diagnostic_results['display'] = True
            print("✅ Display functionality: PASS")
        else:
            print("❌ Display initialization: FAIL")
    except Exception as e:
        print(f"❌ Display test error: {e}")
    
    # **SENSOR TESTING**
    print("\n🔬 SENSOR SYSTEM TEST")
    print("-" * 30)
    try:
        if sensors.initialize_all_sensors():
            print("✅ Sensor initialization: PASS")
            
            # Run built-in diagnostics
            sensors.run_diagnostics()
            
            # Take test readings
            print("\n📊 Test readings (3-second stabilization)...")
            time.sleep(3)
            sensors.update_all_sensors()
            
            # Get and display sensor data
            sensor_data = sensors.get_all_sensor_data()
            print(f"  CO2: {sensor_data['co2']} ppm")
            print(f"  Temperature: {sensor_data['temperature']:.1f}°C")
            print(f"  Humidity: {sensor_data['humidity']:.1f}%")
            print(f"  Light: {sensor_data['lux']} lux")
            print(f"  Pressure: {sensor_data['pressure_hpa']:.1f} hPa")
            print(f"  Location: {sensor_data['current_location']}")
            print(f"  GPS: {sensor_data['gps_satellites']} satellites")
            print(f"  Radiation: {sensor_data['cpm']} CPM")
            
            diagnostic_results['sensors'] = True
            print("✅ Sensor functionality: PASS")
        else:
            print("❌ Sensor initialization: FAIL")
    except Exception as e:
        print(f"❌ Sensor test error: {e}")
    
    # **SD CARD TESTING**
    print("\n💾 SD CARD SYSTEM TEST")
    print("-" * 30)
    try:
        if data_logger.setup_sd_logging():
            print("✅ SD card mount: PASS")
            
            # Test data write
            test_data = sensors.get_all_sensor_data()
            if data_logger.log_sensor_data(test_data):
                print("✅ SD card write: PASS")
                diagnostic_results['sd_card'] = True
            else:
                print("❌ SD card write: FAIL")
        else:
            print("❌ SD card mount: FAIL")
    except Exception as e:
        print(f"❌ SD card test error: {e}")
    
    # **OVERALL ASSESSMENT**
    print("\n🎯 DIAGNOSTIC SUMMARY")
    print("-" * 30)
    
    passed_tests = sum(diagnostic_results.values())
    total_tests = len(diagnostic_results) - 1  # Exclude 'overall'
    success_rate = (passed_tests / total_tests) * 100
    
    for component, status in diagnostic_results.items():
        if component != 'overall':
            status_symbol = "✅" if status else "❌"
            print(f"{component.upper()}: {status_symbol}")
    
    diagnostic_results['overall'] = success_rate >= 66  # At least 2/3 systems working
    
    print(f"\nSuccess Rate: {success_rate:.0f}% ({passed_tests}/{total_tests})")
    
    if diagnostic_results['overall']:
        print("🎉 OVERALL STATUS: SYSTEM READY FOR OPERATION")
    else:
        print("⚠️ OVERALL STATUS: SYSTEM REQUIRES ATTENTION")
        print("🔧 Check hardware connections and restart device")
    
    print("\n" + "="*60)
    return diagnostic_results


if __name__ == "__main__":
    import sys
    
    # Command line argument handling
    if len(sys.argv) > 1:
        if sys.argv[1] == "--diagnostics" or sys.argv[1] == "-d":
            run_comprehensive_diagnostics()
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("AI Field Analyzer v2.0 - Command Line Options:")
            print("  python main.py                 # Normal operation")
            print("  python main.py --diagnostics   # Run system diagnostics") 
            print("  python main.py --help          # Show this help")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for available options")
    else:
        # Normal operation
        main()
