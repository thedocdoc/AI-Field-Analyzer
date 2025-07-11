"""
AI Field Analyzer v2.0 - Main Application (Simplified)
------------------------------------------------------
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

            # Create file with CSV header
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
            battery_status = "LOW" if sensor_data.get('battery_low', False) else "OK"
            radiation_status = "YES" if sensor_data.get('radiation_ready', False) else "NO"
            
            # Write data row
            data_row = (
                timestamp_str + "," +
                str(sensor_data.get('co2', 'ERR')) + "," +
                str(sensor_data.get('voc', 'ERR')) + "," +
                f"{sensor_data.get('temperature', 0):.1f}," +
                f"{sensor_data.get('humidity', 0):.1f}," +
                f"{sensor_data.get('lux', 0):.0f}," +
                f"{sensor_data.get('pressure_hpa', 0):.1f}," +
                f"{sensor_data.get('altitude_m', 0):.1f}," +
                str(sensor_data.get('cpm', 0)) + "," +
                f"{sensor_data.get('usv_h', 0):.3f}," +
                radiation_status + "," +
                f"{sensor_data.get('cpu_usage', 0):.1f}," +
                f"{sensor_data.get('memory_usage', 0):.1f}," +
                f"{sensor_data.get('avg_loop_time', 0)*1000:.1f}," +
                f"{sensor_data.get('cpu_temp', 0):.1f}," +
                battery_status + "," +
                sensor_data.get('current_location', 'UNKNOWN') + "," +
                str(sensor_data.get('gps_satellites', 0)) + "," +
                sensor_data.get('gps_quality', 'NO_FIX') + "\n"
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
        try:
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
        except AttributeError:
            # Handle case where button/flashlight hardware isn't available
            pass
    
    def turn_off(self):
        """Force flashlight off (cleanup)"""
        try:
            if self.flashlight_on:
                self.flashlight_on = False
                self.sensors.flashlight.value = False
                print("🔦 Flashlight turned off")
        except AttributeError:
            pass


def coordinated_startup(display_manager, sensors):
    """
    Simplified startup sequence using existing display methods.
    Removes dependencies on missing display methods.
    """
    print("🚀 AI Field Analyzer v2.0 startup initiated...")
    
    # Use your existing startup screen method
    display_manager.display_startup_screen()
    
    # Simple countdown with console output only
    print("⏱️  Starting system initialization...")
    for i in range(STARTUP_COUNTDOWN, 0, -1):
        if i == 6:
            print("🔧 Beginning sensor initialization...")
        elif i == 3:
            print("📡 Preparing weather forecasting...")
        elif i == 1:
            print("✅ System ready!")
        
        print(f"⏱️  Startup: {i}s")
        time.sleep(1)
    
    # Initialize sensors
    print("🔧 Initializing all sensors...")
    sensors_initialized = sensors.initialize_all_sensors()
    
    if sensors_initialized:
        print("✅ Sensor initialization completed")
    else:
        print("⚠️ Some sensors failed - continuing with available sensors")
    
    print("🎯 Startup sequence complete - transitioning to main operation")
    return sensors_initialized


def print_console_status(sensor_data, data_logger, display_manager):
    """Generate comprehensive console status output"""
    timestamp = time.localtime()
    timestamp_str = f"{timestamp.tm_year}-{timestamp.tm_mon:02d}-{timestamp.tm_mday:02d} {timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
    
    # Status indicators
    rad_status = "READY" if sensor_data.get('radiation_ready', False) else "WARMUP"
    sd_status = "OK" if data_logger.sd_available else "OFF"
    battery_status = "LOW" if sensor_data.get('battery_low', False) else "OK"
    
    # Status line
    status_line = (
        f"[{timestamp_str}] " +
        f"CO₂:{sensor_data.get('co2', 'ERR')} | " +
        f"VOC:{sensor_data.get('voc', 'ERR')} | " +
        f"T:{sensor_data.get('temperature', 0):.1f}C | " +
        f"RH:{sensor_data.get('humidity', 0):.1f}% | " +
        f"P:{sensor_data.get('pressure_hpa', 0):.1f}hPa | " +
        f"ALT:{sensor_data.get('altitude_m', 0):.0f}m | " +
        f"LOC:{sensor_data.get('current_location', 'UNK')} | " +
        f"GPS:{sensor_data.get('gps_satellites', 0)}({sensor_data.get('gps_quality', 'NO_FIX')}) | " +
        f"LUX:{sensor_data.get('lux', 0):.0f} | " +
        f"CPM:{sensor_data.get('cpm', 0)} | " +
        f"µSv/h:{sensor_data.get('usv_h', 0):.3f}({rad_status}) | " +
        f"CPU:{sensor_data.get('cpu_usage', 0):.0f}% | " +
        f"TEMP:{sensor_data.get('cpu_temp', 0):.1f}C | " +
        f"BAT:{battery_status} | " +
        f"SD:{sd_status} | " +
        f"Screen:{display_manager.current_screen+1}/{display_manager.screens_total}"
    )
    
    print(f"\r{status_line}", end="")


def main():
    """
    Main application entry point with full error handling and cleanup.
    Coordinates all subsystems for optimal environmental monitoring.
    """
    print("\n" + "="*70)
    print("AI FIELD ANALYZER v2.0 - ADVANCED ENVIRONMENTAL MONITORING")
    print("Location Detection • Radiation Detection • Air Quality • Weather Prediction")
    print("© 2025 Apollo Timbers - MIT License")
    print("="*70)
    
    # Initialize all core subsystems
    print("🔧 Initializing core subsystems...")
    display_manager = None
    sensors = None
    data_logger = None
    flashlight = None
    
    try:
        # Initialize display first
        display_manager = DisplayManager()
        if not display_manager.initialize_display():
            print("❌ CRITICAL: Display initialization failed!")
            print("🔧 Check SPI connections: GP14(CLK), GP15(MOSI), GP10(CS), GP11(DC), GP16(RST)")
            return False
        
        # Initialize sensors
        sensors = AIFieldSensorManager()
        
        # Run coordinated startup sequence
        sensors_operational = coordinated_startup(display_manager, sensors)
        if not sensors_operational:
            print("⚠️ WARNING: Limited sensor functionality - some readings may be unavailable")
        
        # Initialize remaining subsystems
        data_logger = DataLogger()
        data_logger.setup_sd_logging()  # This will handle its own errors
        
        flashlight = FlashlightController(sensors)
        
        # Initialize timing systems
        display_manager.screen_change_time = time.monotonic()
        
        # Performance monitoring setup
        loop_performance_tracker = []
        console_output_timer = 0
        loop_start_time = time.monotonic()
        
        print("🎯 MAIN LOOP ACTIVE - Maximum radiation sensitivity + Weather forecasting")
        print("📊 Monitoring environmental conditions with location detection and storm prediction")
        
        # **MAIN OPERATIONAL LOOP**
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
            
            # **PRIORITY 2: USER INTERFACE**
            flashlight.update()
            
            # **PRIORITY 3: DISPLAY SYSTEM**
            sensor_data = sensors.get_all_sensor_data()
            display_manager.update_display(sensor_data)
            
            # **PRIORITY 4: DATA PERSISTENCE**
            if data_logger.sd_available:
                data_logger.log_sensor_data(sensor_data)
            
            # **PRIORITY 5: STATUS REPORTING (REDUCED FREQUENCY)**
            if loop_current_time - console_output_timer >= CONSOLE_UPDATE_RATE:
                print_console_status(sensor_data, data_logger, display_manager)
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
            if sensors and data_logger and data_logger.sd_available:
                sensor_data = sensors.get_all_sensor_data()
                data_logger.log_sensor_data(sensor_data)
                print("✅ Emergency sensor data saved")
        except:
            print("❌ Emergency data save failed")
        
        # Display error screen if possible
        try:
            if display_manager and display_manager.display:
                # Create simple error screen using existing methods
                error_splash = display_manager.create_text_line("SYSTEM ERROR", 20, 0x666666)
                if display_manager.display:
                    display_manager.display.root_group = error_splash
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
            if sensors and data_logger and data_logger.sd_available:
                try:
                    sensor_data = sensors.get_all_sensor_data()
                    data_logger.log_sensor_data(sensor_data)
                    print("💾 Final sensor data logged")
                except:
                    pass
            
            # Clear display
            if display_manager and display_manager.display:
                try:
                    error_splash = display_manager.create_text_line("SHUTDOWN", 20, 0x888888)
                    display_manager.display.root_group = error_splash
                    time.sleep(1)
                except:
                    pass
            
            # Memory cleanup
            gc.collect()
            
            print("✅ Cleanup completed successfully")
            
        except Exception as cleanup_error:
            print(f"⚠️ Cleanup warning: {cleanup_error}")
    
    print("👋 AI Field Analyzer v2.0 shutdown complete")
    return True


def run_simple_diagnostics():
    """
    Simplified system diagnostics that work with existing methods.
    """
    print("\n" + "="*60)
    print("AI FIELD ANALYZER v2.0 - SYSTEM DIAGNOSTICS")
    print("="*60)
    
    # Initialize components for testing
    print("🔧 Initializing components for diagnostic testing...")
    
    # Test display
    print("\n📺 DISPLAY SYSTEM TEST")
    print("-" * 30)
    try:
        display_manager = DisplayManager()
        if display_manager.initialize_display():
            print("✅ Display initialization: PASS")
            display_manager.display_startup_screen()
            time.sleep(2)
            print("✅ Display functionality: PASS")
        else:
            print("❌ Display initialization: FAIL")
    except Exception as e:
        print(f"❌ Display test error: {e}")
    
    # Test sensors
    print("\n🔬 SENSOR SYSTEM TEST")
    print("-" * 30)
    try:
        sensors = AIFieldSensorManager()
        if sensors.initialize_all_sensors():
            print("✅ Sensor initialization: PASS")
            
            # Take test readings
            print("\n📊 Test readings (3-second stabilization)...")
            time.sleep(3)
            sensors.update_all_sensors([])
            
            # Get and display sensor data
            sensor_data = sensors.get_all_sensor_data()
            print(f"  CO2: {sensor_data.get('co2', 'ERR')} ppm")
            print(f"  Temperature: {sensor_data.get('temperature', 0):.1f}°C")
            print(f"  Humidity: {sensor_data.get('humidity', 0):.1f}%")
            print(f"  Light: {sensor_data.get('lux', 0)} lux")
            print(f"  Pressure: {sensor_data.get('pressure_hpa', 0):.1f} hPa")
            print(f"  Location: {sensor_data.get('current_location', 'UNKNOWN')}")
            print(f"  Radiation: {sensor_data.get('cpm', 0)} CPM")
            
            print("✅ Sensor functionality: PASS")
        else:
            print("❌ Sensor initialization: FAIL")
    except Exception as e:
        print(f"❌ Sensor test error: {e}")
    
    # Test SD card
    print("\n💾 SD CARD SYSTEM TEST")
    print("-" * 30)
    try:
        data_logger = DataLogger()
        if data_logger.setup_sd_logging():
            print("✅ SD card functionality: PASS")
        else:
            print("❌ SD card functionality: FAIL")
    except Exception as e:
        print(f"❌ SD card test error: {e}")
    
    print("\n🎯 Diagnostics complete!")
    print("="*60)


if __name__ == "__main__":
    import sys
    
    # Command line argument handling
    if len(sys.argv) > 1:
        if sys.argv[1] == "--diagnostics" or sys.argv[1] == "-d":
            run_simple_diagnostics()
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
