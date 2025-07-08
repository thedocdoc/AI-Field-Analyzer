"""
AI Field Analyzer v2.0 - Enhanced Display Manager with Temperature Fusion
-------------------------------------------------------------------------
Fixed scrolling and screen hanging issues.
Enhanced with location awareness, weather intelligence, and temperature fusion.
Now integrates with sensor manager's smart temperature failover and averaging.

© 2025 Apollo Timbers. MIT License.
"""

import time
import board
import busio
import displayio
import terminalio
from fourwire import FourWire
from adafruit_display_text import label
import adafruit_ssd1325

# Display configuration constants
SCREEN_DURATION = 12        # Seconds per screen
SCROLL_SPEED = 2           # Pixels per scroll frame
SCROLL_FPS = 15            # Scroll animation FPS
DATA_UPDATE_RATE = 3       # Screen data update interval
SCROLL_REFRESH = 1.0 / SCROLL_FPS

class DisplayManager:
    """Enhanced display manager with location-aware layouts, weather intelligence, and temperature fusion"""
    
    def __init__(self):
        # Display hardware
        self.display = None
        
        # Enhanced screen management (now 8 screens)
        self.current_screen = 0
        self.screens_total = 8
        self.screen_names = [
            "CO2 & VOC", "TEMP FUSION", "LIGHT & UV", "WEATHER", 
            "RADIATION", "SYSTEM", "SUMMARY", "LOCATION"
        ]
        
        # Display state
        self.current_splash = None
        self.current_scroll_group = None
        self.current_scroll_area = None
        self.scroll_offsets = [0] * self.screens_total
        self.scroll_text_width = 0  # Track text width for proper scrolling
        
        # Timing
        self.screen_change_time = 0
        self.display_last_update = 0
        self.data_update_time = 0
        
        print("🖥️ Enhanced Display Manager with Temperature Fusion initialized")
    
    def initialize_display(self):
        """Initialize the SSD1325 OLED display"""
        print("🖥️ Initializing SSD1325 display...")
        
        try:
            displayio.release_displays()
            
            # Display SPI setup
            spi = busio.SPI(clock=board.GP14, MOSI=board.GP15)
            
            # Display pins
            oled_cs = board.GP10
            oled_dc = board.GP11
            oled_rst = board.GP12
            
            # Create display bus
            display_bus = FourWire(
                spi, 
                command=oled_dc, 
                chip_select=oled_cs, 
                reset=oled_rst,
                baudrate=1000000
            )
            
            # Initialize display
            self.display = adafruit_ssd1325.SSD1325(display_bus, width=128, height=64)
            print("✅ Enhanced display with temperature fusion ready!")
            return True
            
        except Exception as e:
            print(f"❌ Display initialization failed: {e}")
            return False
    
    def create_text_line(self, text, y_pos, color=0xFFFFFF, x_center=True, scale=1):
        """Helper function to create text lines"""
        text_area = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
        if x_center:
            text_width = text_area.bounding_box[2]
            x_pos = (128 - text_width) // 2
        else:
            x_pos = 2
        
        text_group = displayio.Group(x=x_pos, y=y_pos)
        text_group.append(text_area)
        return text_group
    
    def create_scrolling_text(self, text, y_pos, color=0xFFFFFF, width=128, scale=1):
        """Create scrolling text - MINIMAL FIX for text width"""
        text_area = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
        text_group = displayio.Group(x=width, y=y_pos)
        text_group.append(text_area)
    
        # FIXED: More robust text width calculation
        try:
            if text_area.bounding_box and text_area.bounding_box[2] and text_area.bounding_box[2] > 0:
                self.scroll_text_width = text_area.bounding_box[2]
            else:
                self.scroll_text_width = len(str(text)) * 6 * scale
        except:
            self.scroll_text_width = len(str(text)) * 6 * scale
    
        return text_group, text_area
    
    def update_scrolling_text(self, text_group, text_area, scroll_offset):
        """Update scrolling text position - MINIMAL FIX"""
        try:
            # Use stored width first, then fallback calculations
            if hasattr(self, 'scroll_text_width') and self.scroll_text_width > 0:
                text_width = self.scroll_text_width
            else:
                try:
                    if text_area.bounding_box and text_area.bounding_box[2] and text_area.bounding_box[2] > 0:
                        text_width = text_area.bounding_box[2]
                    else:
                        raise ValueError("Invalid bounding box")
                except:
                    text_width = len(str(text_area.text)) * 6
        
            # Calculate new position
            new_x = 128 - scroll_offset
        
            # Reset scroll when text completely moves off screen
            if new_x < -text_width - 10:
                scroll_offset = 0
                new_x = 128
        
            text_group.x = new_x
            return scroll_offset + SCROLL_SPEED
        
        except Exception as e:
            print(f"Scroll error: {e}")
            return 0

    def get_temperature_fusion_warning(self, sensor_data):
        """NEW: Temperature fusion status and warnings"""
        # Get temperature fusion data from sensor manager
        fused_temp = sensor_data.get('temperature_fused', None)
        temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
        bmp390_temp = sensor_data.get('bmp390_temperature', None)
        scd41_temp = sensor_data.get('temperature', None)
        
        # Temperature sensor status
        active_temp_sensors = sensor_data.get('active_temperature_sensors', 0)
        temp_redundancy = sensor_data.get('temperature_redundancy_active', False)
        scd41_in_range = sensor_data.get('scd41_in_range', True)
        
        if fused_temp is None:
            return "TEMPERATURE: No sensors available - Check connections", 0x666666
        
        # Warning based on source and status
        if temp_source == "FUSED":
            if temp_redundancy:
                return f"TEMP FUSION: {fused_temp:.1f}°C from 2 sensors - Optimal accuracy", 0xFFFFFF
            else:
                return f"TEMP FUSION: {fused_temp:.1f}°C weighted average - Good", 0xCCCCCC
        elif temp_source == "BMP390":
            if scd41_temp is not None and not scd41_in_range:
                return f"TEMP: {fused_temp:.1f}°C (BMP390) - SCD41 out of range", 0xAAAAA
            else:
                return f"TEMP: {fused_temp:.1f}°C (BMP390 only) - SCD41 offline", 0x888888
        elif temp_source == "SCD41":
            return f"TEMP: {fused_temp:.1f}°C (SCD41 only) - BMP390 offline", 0x888888
        elif temp_source == "SCD41_OUT_OF_RANGE":
            return f"TEMP WARNING: SCD41 {scd41_temp:.1f}°C outside range (-10 to 60°C)", 0x666666
        elif temp_source == "FAILED":
            return "TEMP CRITICAL: Both temperature sensors failed", 0x444444
        else:
            return f"TEMP: {fused_temp:.1f}°C ({temp_source}) - Status unknown", 0x888888

    def get_enhanced_weather_warning_with_countdown(self, sensor_data):
        """Enhanced weather warnings with countdown and storm details"""
        current_location = sensor_data.get('current_location', 'UNKNOWN')
        storm_prob = sensor_data.get('weather_storm_probability', 0)
        weather_type = sensor_data.get('weather_forecast_type', 'UNKNOWN')
        weather_confidence = sensor_data.get('weather_confidence', 0)
        arrival_timing = sensor_data.get('weather_arrival_timing', 'N/A')
        
        if current_location != "OUTDOOR":
            return f"Weather monitoring paused - {current_location.lower()} environment", 0x888888
        
        # Storm warnings with countdown
        if storm_prob >= 80:
            if arrival_timing != 'N/A':
                return f"SEVERE STORM INCOMING: {storm_prob}% in {arrival_timing}", 0x666666
            else:
                return f"SEVERE STORM WARNING: {storm_prob}% probability detected", 0x666666
        
        elif storm_prob >= 60:
            if arrival_timing != 'N/A':
                return f"STORM LIKELY: {storm_prob}% chance, arriving {arrival_timing}", 0x888888
            else:
                return f"STORM LIKELY: {storm_prob}% probability - Monitor conditions", 0x888888
        
        elif storm_prob >= 30:
            if arrival_timing != 'N/A':
                return f"WEATHER CHANGE: {storm_prob}% chance in {arrival_timing}", 0xAAAAA
            else:
                return f"WEATHER CHANGE: {storm_prob}% - Conditions developing", 0xAAAAA
        
        elif storm_prob >= 10:
            return f"MONITORING: {storm_prob}% storm chance - Conditions stable", 0xCCCCCC
        
        else:
            # Clear conditions
            if weather_type == "STABLE":
                return f"CLEAR CONDITIONS: Weather stable ({weather_confidence}% confidence)", 0xFFFFFF
            else:
                return f"CLEAR: {weather_type} conditions ({weather_confidence}% conf)", 0xFFFFFF

    def get_enhanced_weather_warning(self, sensor_data):
        """Enhanced weather warnings using new data"""
        current_location = sensor_data.get('current_location', 'UNKNOWN')
        weather_type = sensor_data.get('weather_forecast_type', 'UNKNOWN')
        weather_confidence = sensor_data.get('weather_confidence', 0)
        fog_risk = sensor_data.get('fog_risk', 'UNKNOWN')
        
        if current_location != "OUTDOOR":
            return f"Weather monitoring paused - {current_location.lower()} environment", 0x888888
        if fog_risk == "CONFIRMED":
            return f"FOG PRESENT: <500m visibility confirmed", 0x333333
        elif fog_risk == "FORMING":
            return f"FOG FORMING: Visibility reducing, conditions developing", 0x444444
        elif weather_type == "DENSE_FOG" or fog_risk == "IMMINENT":
            return f"FOG IMMINENT: Conditions perfect, visibility dropping", 0x444444
        elif fog_risk == "POSSIBLE":
            return f"FOG POSSIBLE: Low light + humidity detected", 0x666666
        elif weather_type == "CLEAR":
            return f"CLEAR CONDITIONS: Weather stable ({weather_confidence}%)", 0xFFFFFF
        else:
            return f"MONITORING: Clean outdoor data ({weather_confidence}%)", 0xCCCCCC
    
    def get_location_warning(self, sensor_data):
        """Location and GPS warnings"""
        current_location = sensor_data.get('current_location', 'UNKNOWN')
        location_confidence = sensor_data.get('location_confidence', 0)
        gps_satellites = sensor_data.get('gps_satellites', 0)
        gps_speed = sensor_data.get('gps_speed_kmh', 0)
        
        if current_location == "VEHICLE" and gps_speed > 50:
            return f"HIGH SPEED: {gps_speed:.0f} km/h - Monitor conditions", 0x666666
        elif current_location == "OUTDOOR" and gps_satellites >= 8:
            return f"GPS EXCELLENT: {gps_satellites} satellites - High precision", 0xFFFFFF
        elif current_location == "INDOOR":
            return f"INDOOR DETECTED: Air quality monitoring active", 0x888888
        elif current_location == "CAVE":
            return f"UNDERGROUND: Safety monitoring prioritized", 0x666666
        else:
            return f"LOCATION: {current_location} ({location_confidence}%)", 0xAAAAA
    
    def get_system_warning(self, sensor_data):
        """System warnings with power management"""
        warnings = []
        warning_level = 0
        
        battery_usage = sensor_data.get('battery_usage_estimate', 100)
        current_location = sensor_data.get('current_location', 'UNKNOWN')
        
        if sensor_data.get('battery_low', False):
            warnings.append("BATTERY-CRITICAL")
            warning_level = 3
        elif sensor_data.get('cpu_usage', 0) >= 85:
            warnings.append("CPU-CRITICAL")
            warning_level = 2
        elif battery_usage <= 70:
            power_savings = 100 - battery_usage
            warnings.append(f"POWER-SAVE-{power_savings}%")
            warning_level = 1
        
        if warning_level == 3:
            return "CRITICAL: BATTERY LOW - Recharge immediately!", 0x333333
        elif warning_level == 2:
            return "PERFORMANCE: High CPU usage - Monitor system", 0x444444
        elif warning_level == 1:
            power_savings = 100 - battery_usage
            return f"POWER SAVE: {current_location} mode - {power_savings}% savings", 0xAAAAA
        else:
            return f"SYSTEM OPTIMAL: {current_location} mode - All systems nominal", 0xFFFFFF

    def get_enhanced_summary_warning_with_weather(self, sensor_data):
        """Enhanced summary warning with weather priority"""
        alerts = []
        current_location = sensor_data.get('current_location', 'UNKNOWN')
        storm_prob = sensor_data.get('weather_storm_probability', 0)
        arrival_timing = sensor_data.get('weather_arrival_timing', 'N/A')
        
        # Weather alerts have priority
        if storm_prob >= 70:
            if arrival_timing != 'N/A':
                alerts.append(f"STORM-{arrival_timing}")
            else:
                alerts.append(f"STORM-{storm_prob}%")
        elif storm_prob >= 40:
            alerts.append(f"WEATHER-{storm_prob}%")
        
        # Temperature alerts
        temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
        if temp_source == "FAILED":
            alerts.append("TEMP-FAIL")
        elif temp_source == "SCD41_OUT_OF_RANGE":
            alerts.append("TEMP-RANGE")
        
        # Other alerts
        if sensor_data.get('co2', 400) >= 1000:
            alerts.append("CO2-HIGH")
        
        if sensor_data.get('battery_low', False):
            alerts.append("BATTERY-LOW")
        
        if sensor_data.get('usv_h', 0) > 0.5:
            alerts.append("RADIATION")
        
        if alerts:
            status_msg = f"{current_location}: " + " | ".join(alerts[:2])
            # Color based on severity
            if storm_prob >= 70 or sensor_data.get('battery_low', False) or temp_source == "FAILED":
                status_color = 0x666666  # High priority
            elif storm_prob >= 40 or sensor_data.get('co2', 400) >= 1000 or temp_source == "SCD41_OUT_OF_RANGE":
                status_color = 0x888888  # Medium priority
            else:
                status_color = 0xAAAAA  # Low priority
        else:
            # All clear
            battery_usage = sensor_data.get('battery_usage_estimate', 100)
            power_savings = 100 - battery_usage
            temp_fusion_status = "FUSED" if sensor_data.get('temperature_source') == "FUSED" else "SINGLE"
            if power_savings > 0:
                status_msg = f"{current_location}: {power_savings}% power save, temp {temp_fusion_status}"
            else:
                status_msg = f"{current_location}: All optimal, temp fusion {temp_fusion_status}"
            status_color = 0xFFFFFF
        
        return status_msg, status_color
    
    def build_screen(self, screen_num, sensor_data, timestamp_str):
        """Build screen with enhanced data including temperature fusion - UPDATED VERSION"""
        # Clear any existing display groups to prevent hanging
        if self.display and self.display.root_group:
            try:
                self.display.root_group = displayio.Group()
            except Exception as e:
                print(f"Warning: Could not clear display group: {e}")
        
        splash = displayio.Group()
        
        # Reset scroll offset for this screen
        self.scroll_offsets[screen_num] = 0
        
        try:
            if screen_num == 0:  # CO2 & VOC
                splash.append(self.create_text_line("CO2 & VOC", 6, 0xFFFFFF))
                co2_val = sensor_data.get('co2', 'ERR')
                voc_val = sensor_data.get('voc', 'ERR')
                splash.append(self.create_text_line(f"CO2:{co2_val}ppm", 18, 0xCCCCCC, False))
                splash.append(self.create_text_line(f"VOC:{voc_val}ppb", 28, 0xCCCCCC, False))
                warning_msg, warning_color = self.get_co2_warning(sensor_data.get('co2', 400))
                
            elif screen_num == 1:  # NEW: Temperature Fusion Display
                splash.append(self.create_text_line("TEMP FUSION", 6, 0xFFFFFF))
                
                # Get fused temperature data
                fused_temp = sensor_data.get('temperature_fused', None)
                temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
                active_sensors = sensor_data.get('active_temperature_sensors', 0)
                
                if fused_temp is not None:
                    splash.append(self.create_text_line(f"TEMP:{fused_temp:.1f}C", 18, 0xCCCCCC, False))
                else:
                    splash.append(self.create_text_line("TEMP:ERROR", 18, 0x666666, False))
                
                # Show source and sensor count
                source_short = temp_source[:8] if temp_source != "UNKNOWN" else "UNK"
                splash.append(self.create_text_line(f"SRC:{source_short}", 28, 0xAAAAA, False))
                splash.append(self.create_text_line(f"SENSORS:{active_sensors}/2", 38, 0xAAAAA, False))
                
                warning_msg, warning_color = self.get_temperature_fusion_warning(sensor_data)
                
            elif screen_num == 2:  # Light & UV (adjusted index)
                splash.append(self.create_text_line("LIGHT & UV", 6, 0xFFFFFF))
                lux_val = sensor_data.get('lux', 0)
                if lux_val == 'ERR' or lux_val is None:
                    lux_text = "LUX:ERROR"
                else:
                    lux_text = f"LUX:{lux_val/1000:.1f}k" if lux_val >= 1000 else f"LUX:{lux_val:.0f}"
                splash.append(self.create_text_line(lux_text, 18, 0xCCCCCC, False))
                
                if lux_val not in ['ERR', None] and isinstance(lux_val, (int, float)):
                    if lux_val < 200: condition = "LOW"
                    elif lux_val < 1000: condition = "MOD"
                    elif lux_val < 10000: condition = "BRIGHT"
                    else: condition = "INTENSE"
                else:
                    condition = "ERROR"
                
                splash.append(self.create_text_line(f"LEVEL:{condition}", 28, 0xAAAAA, False))
                warning_msg, warning_color = self.get_light_warning(lux_val if isinstance(lux_val, (int, float)) else 0)
                
            elif screen_num == 3:  # Enhanced Weather Screen (adjusted index)
                splash.append(self.create_text_line("WEATHER", 6, 0xFFFFFF))
                
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                if current_location == "OUTDOOR":
                    # Line 1: Pressure
                    pressure_val = sensor_data.get('pressure_hpa', 'ERR')
                    if pressure_val != 'ERR' and pressure_val is not None:
                        splash.append(self.create_text_line(f"PRESS:{pressure_val:.1f}hPa", 16, 0xCCCCCC, False))
                    else:
                        splash.append(self.create_text_line("PRESS:ERROR", 16, 0x666666, False))
                    
                    # Line 2: Storm probability and type
                    storm_prob = sensor_data.get('weather_storm_probability', 0)
                    weather_type = sensor_data.get('weather_forecast_type', 'UNKNOWN')
                    
                    if storm_prob > 0:
                        # Show probability percentage
                        type_short = weather_type.replace('_', '')[:8]  # Shorten long names
                        splash.append(self.create_text_line(f"{type_short}:{storm_prob}%", 26, 0xCCCCCC, False))
                    else:
                        splash.append(self.create_text_line(f"{weather_type[:12]}", 26, 0xCCCCCC, False))
                    
                    # Line 3: Storm timing or confidence
                    arrival_timing = sensor_data.get('weather_arrival_timing', 'N/A')
                    weather_conf = sensor_data.get('weather_confidence', 0)
                    
                    if arrival_timing != 'N/A' and storm_prob > 30:
                        # Show countdown when storm is coming
                        timing_short = arrival_timing.replace(' hours', 'h').replace(' minutes', 'm')
                        splash.append(self.create_text_line(f"ETA:{timing_short}", 36, 0xAAAAA, False))
                    else:
                        # Show confidence when no storm
                        splash.append(self.create_text_line(f"CONF:{weather_conf}%", 36, 0xAAAAA, False))
                    
                    # Enhanced weather warning with countdown
                    warning_msg, warning_color = self.get_enhanced_weather_warning_with_countdown(sensor_data)
                    
                else:
                    # Indoor mode - show location and status
                    splash.append(self.create_text_line(f"LOCATION:{current_location}", 18, 0x888888, False))
                    splash.append(self.create_text_line("Weather monitoring", 28, 0x888888, False))
                    splash.append(self.create_text_line("paused indoors", 38, 0x888888, False))
                    warning_msg, warning_color = self.get_enhanced_weather_warning(sensor_data)
                
            elif screen_num == 4:  # Radiation (adjusted index)
                splash.append(self.create_text_line("RADIATION", 6, 0xFFFFFF))
                cpm_val = sensor_data.get('cpm', 'ERR')
                usv_val = sensor_data.get('usv_h', 'ERR')
                rad_ready = sensor_data.get('radiation_ready', False)
                
                splash.append(self.create_text_line(f"CPM:{cpm_val}", 18, 0xCCCCCC, False))
                if rad_ready and usv_val != 'ERR':
                    splash.append(self.create_text_line(f"uSv/h:{usv_val:.3f}", 28, 0xCCCCCC, False))
                else:
                    splash.append(self.create_text_line("uSv/h:WARMING", 28, 0x888888, False))
                
                usv_value = usv_val if isinstance(usv_val, (int, float)) else 0
                warning_msg, warning_color = self.get_radiation_warning(usv_value, rad_ready)
                
            elif screen_num == 5:  # Enhanced System (adjusted index)
                splash.append(self.create_text_line("SYSTEM", 6, 0xFFFFFF))
                cpu_usage = sensor_data.get('cpu_usage', 'ERR')
                mem_usage = sensor_data.get('memory_usage', 'ERR')
                
                if cpu_usage != 'ERR' and mem_usage != 'ERR':
                    splash.append(self.create_text_line(f"CPU:{cpu_usage:.0f}% MEM:{mem_usage:.0f}%", 18, 0xCCCCCC, False))
                else:
                    splash.append(self.create_text_line("CPU:ERR MEM:ERR", 18, 0x666666, False))
                
                battery_usage = sensor_data.get('battery_usage_estimate', 100)
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                splash.append(self.create_text_line(f"PWR:{battery_usage}% {current_location[:3]}", 28, 0xCCCCCC, False))
                warning_msg, warning_color = self.get_system_warning(sensor_data)
                
            elif screen_num == 6:  # Enhanced Summary with Weather and Temperature (adjusted index)
                splash.append(self.create_text_line("SUMMARY", 6, 0xFFFFFF))
                
                # Line 1: Air quality
                co2_val = sensor_data.get('co2', 'ERR')
                voc_val = sensor_data.get('voc', 'ERR')
                voc_display = voc_val // 10 if isinstance(voc_val, (int, float)) else 'ERR'
                splash.append(self.create_text_line(f"CO2:{co2_val} VOC:{voc_display}", 16, 0xCCCCCC, False))
                
                # Line 2: Environment with fused temperature
                fused_temp = sensor_data.get('temperature_fused', sensor_data.get('temperature', 'ERR'))
                humidity_val = sensor_data.get('humidity', 'ERR')
                if fused_temp != 'ERR' and humidity_val != 'ERR':
                    splash.append(self.create_text_line(f"T:{fused_temp:.1f}C H:{humidity_val:.0f}%", 25, 0xCCCCCC, False))
                else:
                    splash.append(self.create_text_line("T:ERR H:ERR", 25, 0x666666, False))
                
                # Line 3: Location, Weather, Battery, and Temperature source
                location = sensor_data.get('current_location', 'UNK')[:3]
                storm_prob = sensor_data.get('weather_storm_probability', 0)
                battery = sensor_data.get('battery_usage_estimate', 100)
                temp_source = sensor_data.get('temperature_source', 'UNK')[:3]
                
                if storm_prob > 30:
                    # Show storm probability when storm is possible
                    splash.append(self.create_text_line(f"LOC:{location} STORM:{storm_prob}% T:{temp_source}", 35, 0xCCCCCC, False))
                else:
                    weather = sensor_data.get('weather_forecast_type', 'UNK')[:4]
                    splash.append(self.create_text_line(f"LOC:{location} WX:{weather} T:{temp_source}", 35, 0xCCCCCC, False))
                
                warning_msg, warning_color = self.get_enhanced_summary_warning_with_weather(sensor_data)
                
            elif screen_num == 7:  # Location & GPS (adjusted index)
                splash.append(self.create_text_line("LOCATION & GPS", 6, 0xFFFFFF))
                
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                location_confidence = sensor_data.get('location_confidence', 0)
                splash.append(self.create_text_line(f"LOC:{current_location}", 18, 0xCCCCCC, False))
                splash.append(self.create_text_line(f"CONF:{location_confidence}%", 28, 0xCCCCCC, False))
                
                gps_satellites = sensor_data.get('gps_satellites', 0)
                gps_speed = sensor_data.get('gps_speed_kmh', 0)
                
                if current_location == "VEHICLE":
                    splash.append(self.create_text_line(f"SPEED:{gps_speed:.0f}km/h", 38, 0xAAAAA, False))
                else:
                    gps_quality = sensor_data.get('gps_quality', 'UNKNOWN')
                    splash.append(self.create_text_line(f"GPS:{gps_satellites}sat {gps_quality[:3]}", 38, 0xAAAAA, False))
                
                warning_msg, warning_color = self.get_location_warning(sensor_data)
            
            # Add scrolling warning message
            self.current_scroll_group, self.current_scroll_area = self.create_scrolling_text(warning_msg, 49, warning_color)
            splash.append(self.current_scroll_group)
            
            # Add enhanced timestamp with location and temperature source
            location_indicator = sensor_data.get('current_location', 'UNK')[:3]
            temp_source_indicator = sensor_data.get('temperature_source', 'UNK')[:1]  # First letter only for space
            enhanced_timestamp = f"{timestamp_str} {location_indicator} T{temp_source_indicator}"
            splash.append(self.create_text_line(enhanced_timestamp, 60, 0x666666, False))
            
            # Set the display root group
            if self.display:
                self.display.root_group = splash
            
            self.current_splash = splash
            return splash
            
        except Exception as e:
            print(f"❌ Error building screen {screen_num}: {e}")
            # Create a simple error screen
            error_splash = displayio.Group()
            error_splash.append(self.create_text_line(f"SCREEN {screen_num} ERROR", 20, 0x666666))
            error_splash.append(self.create_text_line("Check sensor data", 32, 0x888888))
            if self.display:
                self.display.root_group = error_splash
            return error_splash
    
    def get_co2_warning(self, co2):
        """Basic CO2 warning"""
        if co2 == 'ERR' or co2 is None:
            return "CO2 SENSOR: Error reading sensor data", 0x666666
        elif co2 >= 2000:
            return f"CO2 DANGER: {co2}ppm - Ventilate immediately", 0x666666
        elif co2 >= 1000:
            return f"CO2 CAUTION: {co2}ppm - Improve ventilation", 0xAAAAA
        else:
            return f"CO2 NORMAL: {co2}ppm - Air quality good", 0xFFFFFF
    
    def get_temp_warning(self, temp):
        """Basic temperature warning with fusion awareness"""
        if temp == 'ERR' or temp is None:
            return "TEMP SENSOR: Error reading temperature data", 0x666666
        elif temp >= 30 or temp < 18:
            return f"TEMP WARNING: {temp:.1f}C - Uncomfortable", 0x888888
        else:
            return f"TEMP COMFORTABLE: {temp:.1f}C - Good", 0xFFFFFF
    
    def get_light_warning(self, lux):
        """Basic light warning"""
        if lux == 'ERR' or lux is None:
            return "LIGHT SENSOR: Error reading light sensor", 0x666666
        elif lux < 200:
            return f"LIGHT LOW: {lux:.0f} lux - Eye strain possible", 0xAAAAA
        elif lux > 50000:
            return f"LIGHT INTENSE: {lux/1000:.1f}k lux - UV protection", 0x666666
        else:
            return f"LIGHT GOOD: {lux:.0f} lux - Comfortable", 0xFFFFFF
    
    def get_radiation_warning(self, usv_h, radiation_ready):
        """Basic radiation warning"""
        if not radiation_ready:
            return "RADIATION: Warming up - ready soon", 0x888888
        elif usv_h < 0.5:
            return f"RADIATION SAFE: {usv_h:.3f} µSv/h - Normal", 0xFFFFFF
        else:
            return f"RADIATION ELEVATED: {usv_h:.3f} µSv/h - Limit exposure", 0xAAAAA
    
    def get_summary_warning(self, sensor_data):
        """Enhanced summary warning with temperature fusion awareness"""
        alerts = []
        current_location = sensor_data.get('current_location', 'UNKNOWN')
        
        # Check CO2
        co2_val = sensor_data.get('co2', 400)
        if co2_val != 'ERR' and co2_val is not None and co2_val >= 1000:
            alerts.append("CO2-HIGH")
        
        # Check temperature fusion status
        temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
        if temp_source == "FAILED":
            alerts.append("TEMP-FAIL")
        elif temp_source == "SCD41_OUT_OF_RANGE":
            alerts.append("TEMP-RANGE")
        
        # Check fog risk
        fog_risk = sensor_data.get('fog_risk', 'UNKNOWN')
        if fog_risk in ["IMMINENT", "HIGH"]:
            alerts.append(f"FOG-{fog_risk}")
        
        # Check battery
        if sensor_data.get('battery_low', False):
            alerts.append("BATTERY-LOW")
        
        if alerts:
            status_msg = f"{current_location}: " + " | ".join(alerts[:2])
            status_color = 0x888888
        else:
            battery_usage = sensor_data.get('battery_usage_estimate', 100)
            power_savings = 100 - battery_usage
            temp_fusion_active = temp_source == "FUSED"
            temp_status = "FUSED" if temp_fusion_active else "SINGLE"
            
            if power_savings > 0:
                status_msg = f"{current_location}: {power_savings}% power save, temp {temp_status}"
            else:
                status_msg = f"{current_location}: All optimal, temp fusion {temp_status}"
            status_color = 0xFFFFFF
        
        return status_msg, status_color
    
    def update_display(self, sensor_data, force_rebuild=False):
        """Main display update function with temperature fusion support - ENHANCED VERSION"""
        if not self.display:
            return
            
        current_time = time.monotonic()
        timestamp = time.localtime()
        timestamp_str = f"{timestamp.tm_hour:02}:{timestamp.tm_min:02}:{timestamp.tm_sec:02}"
        
        # Enhance sensor data with temperature fusion if available
        enhanced_sensor_data = self._enhance_sensor_data_with_fusion(sensor_data)
        
        # Check for screen change
        if current_time - self.screen_change_time >= SCREEN_DURATION:
            self.current_screen = (self.current_screen + 1) % self.screens_total
            self.screen_change_time = current_time
            self.scroll_offsets[self.current_screen] = 0
            force_rebuild = True
            print(f"🔄 Screen: {self.screen_names[self.current_screen]} ({self.current_screen + 1}/{self.screens_total})")
        
        # Rebuild screen if needed
        if force_rebuild or self.current_splash is None:
            try:
                self.build_screen(self.current_screen, enhanced_sensor_data, timestamp_str)
            except Exception as e:
                print(f"❌ Error updating display: {e}")
                return
        
        # Update scrolling text with proper error handling
        if (current_time - self.display_last_update >= SCROLL_REFRESH and 
            self.current_scroll_group and self.current_scroll_area):
            try:
                self.scroll_offsets[self.current_screen] = self.update_scrolling_text(
                    self.current_scroll_group, self.current_scroll_area, 
                    self.scroll_offsets[self.current_screen]
                )
                self.display_last_update = current_time
            except Exception as e:
                print(f"Warning: Scrolling text update failed: {e}")
                # Reset scrolling on error
                self.scroll_offsets[self.current_screen] = 0
    
    def _enhance_sensor_data_with_fusion(self, sensor_data):
        """Enhanced sensor data with improved temperature fusion detection"""
        # Create a copy of sensor data to avoid modifying original
        enhanced_data = sensor_data.copy()
        
        # Get basic temperature readings
        bmp390_temp = enhanced_data.get('bmp390_temperature', None)
        scd41_temp = enhanced_data.get('temperature', None)
        
        # Determine SCD41 range status
        scd41_in_range = (scd41_temp is not None and -10 <= scd41_temp <= 60)
        
        # Count active sensors
        active_sensors = 0
        if bmp390_temp is not None:
            active_sensors += 1
        if scd41_temp is not None and scd41_in_range:
            active_sensors += 1
        
        # Determine temperature fusion logic
        if bmp390_temp is not None and scd41_temp is not None and scd41_in_range:
            # Both sensors working and in range - use fusion
            fused_temp = (bmp390_temp * 0.65 + scd41_temp * 0.35)
            temp_source = "FUSED"
            redundancy_active = True
        elif bmp390_temp is not None:
            # BMP390 primary sensor working
            fused_temp = bmp390_temp
            temp_source = "BMP390"
            redundancy_active = False
        elif scd41_temp is not None and scd41_in_range:
            # SCD41 backup sensor working and in range
            fused_temp = scd41_temp
            temp_source = "SCD41"
            redundancy_active = False
        elif scd41_temp is not None and not scd41_in_range:
            # SCD41 out of range
            fused_temp = None
            temp_source = "SCD41_OUT_OF_RANGE"
            redundancy_active = False
        else:
            # Both sensors failed
            fused_temp = None
            temp_source = "FAILED"
            redundancy_active = False
        
        # Enhanced sensor data with fusion information
        enhanced_data['temperature_fused'] = fused_temp
        enhanced_data['temperature_source'] = temp_source
        enhanced_data['active_temperature_sensors'] = active_sensors
        enhanced_data['temperature_redundancy_active'] = redundancy_active
        enhanced_data['scd41_in_range'] = scd41_in_range
        enhanced_data['temperature_failover_available'] = fused_temp is not None
        
        return enhanced_data
    
    def display_startup_screen(self):
        """Enhanced startup screen with temperature fusion info"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 8, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER", 20, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("v2.0", 32, 0x888888))
        splash.append(self.create_text_line("Temperature Fusion Enhanced", 44, 0x666666))
        
        time.sleep(3)
    
    def display_countdown(self, seconds_remaining, status_message):
        """Enhanced countdown screen"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 6, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER v2.0", 16, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line(f"Ready in {seconds_remaining}s", 28, 0x888888))
        splash.append(self.create_text_line(status_message[:20], 40, 0x666666))
        splash.append(self.create_text_line("Temp Fusion Ready", 52, 0x444444))
    
    def display_error_screen(self, error_message):
        """Enhanced error screen"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("ERROR", 8, 0x444444, True, 1))
        splash.append(self.create_text_line("SYSTEM FAULT", 20, 0x666666))
        splash.append(self.create_text_line(error_message[:20], 32, 0x888888))
        splash.append(self.create_text_line("Check connections", 44, 0xAAAAA))
        splash.append(self.create_text_line("Restart device", 56, 0xAAAAA))
        
        print(f"❌ Enhanced error screen: {error_message}")

# Helper functions for console output with temperature fusion
def get_enhanced_console_status(sensor_data):
    """Legacy function name for backward compatibility"""
    return get_enhanced_console_status_with_fusion(sensor_data)

def get_enhanced_console_status_with_fusion(sensor_data):
    """Get enhanced console status line with temperature fusion information"""
    timestamp = time.localtime()
    timestamp_str = f"{timestamp.tm_hour:02}:{timestamp.tm_min:02}:{timestamp.tm_sec:02}"
    
    location = sensor_data.get('current_location', 'UNK')[:3]
    storm_prob = sensor_data.get('weather_storm_probability', 0)
    weather_type = sensor_data.get('weather_forecast_type', 'UNK')[:6]
    weather_conf = sensor_data.get('weather_confidence', 0)
    arrival_timing = sensor_data.get('weather_arrival_timing', 'N/A')
    battery_usage = sensor_data.get('battery_usage_estimate', 100)
    
    # Enhanced temperature display with fusion info
    fused_temp = sensor_data.get('temperature_fused', sensor_data.get('temperature', 'ERR'))
    temp_source = sensor_data.get('temperature_source', 'UNK')[:3]
    active_temp_sensors = sensor_data.get('active_temperature_sensors', 0)
    
    # Build weather status with storm priority
    if storm_prob >= 30 and arrival_timing != 'N/A':
        weather_status = f"STORM:{storm_prob}%/{arrival_timing}"
    elif storm_prob >= 10:
        weather_status = f"WX:{weather_type}({storm_prob}%)"
    else:
        weather_status = f"WX:{weather_type}({weather_conf}%)"
    
    # Enhanced temperature status
    if fused_temp != 'ERR' and fused_temp is not None:
        temp_status = f"T:{fused_temp:.1f}C({temp_source}:{active_temp_sensors})"
    else:
        temp_status = f"T:ERR({temp_source})"
    
    status_line = (
        f"[{timestamp_str}] " +
        f"LOC:{location} | " +
        f"{weather_status} | " +
        f"CO₂:{sensor_data.get('co2', 'ERR')} | " +
        f"{temp_status} | " +
        f"P:{sensor_data.get('pressure_hpa', 'ERR'):.1f}hPa | " +
        f"RAD:{sensor_data.get('usv_h', 'ERR'):.3f}µSv/h | " +
        f"PWR:{battery_usage}% | " +
        f"GPS:{sensor_data.get('gps_satellites', 0)}sat"
    )
    
    return status_line

def display_temperature_fusion_status(sensor_data):
    """Display detailed temperature fusion status for debugging"""
    print("\n🌡️ TEMPERATURE FUSION STATUS")
    print("=" * 50)
    
    fused_temp = sensor_data.get('temperature_fused', None)
    temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
    bmp390_temp = sensor_data.get('bmp390_temperature', None)
    scd41_temp = sensor_data.get('temperature', None)
    active_sensors = sensor_data.get('active_temperature_sensors', 0)
    redundancy_active = sensor_data.get('temperature_redundancy_active', False)
    scd41_in_range = sensor_data.get('scd41_in_range', True)
    
    # Display individual sensor readings
    print(f"BMP390 Temperature: {bmp390_temp:.1f}°C" if bmp390_temp is not None else "BMP390 Temperature: OFFLINE")
    print(f"SCD41 Temperature:  {scd41_temp:.1f}°C" if scd41_temp is not None else "SCD41 Temperature:  OFFLINE")
    
    if scd41_temp is not None:
        range_status = "IN RANGE" if scd41_in_range else "OUT OF RANGE (-10 to 60°C)"
        print(f"SCD41 Range Status: {range_status}")
    
    # Display fusion results
    print(f"\nFused Temperature:  {fused_temp:.1f}°C" if fused_temp is not None else "Fused Temperature:  ERROR")
    print(f"Temperature Source: {temp_source}")
    print(f"Active Sensors:     {active_sensors}/2")
    print(f"Fusion Active:      {'YES' if redundancy_active else 'NO'}")
    
    # Display fusion details
    if temp_source == "FUSED":
        print(f"Fusion Method:      Weighted average (BMP390: 65%, SCD41: 35%)")
    elif temp_source in ["BMP390", "SCD41"]:
        print(f"Fusion Method:      Single sensor fallback")
    elif temp_source == "SCD41_OUT_OF_RANGE":
        print(f"Fusion Method:      SCD41 out of operating range")
    elif temp_source == "FAILED":
        print(f"Fusion Method:      Both sensors failed")
    
    # Display accuracy information
    print(f"\nAccuracy Information:")
    if bmp390_temp is not None:
        print(f"  BMP390: ±0.5°C accuracy (Primary sensor)")
    if scd41_temp is not None and scd41_in_range:
        print(f"  SCD41:  ±0.8°C accuracy (Backup sensor)")
    
    if temp_source == "FUSED":
        print(f"  Fused:  Enhanced accuracy from dual sensors")
    
    print("✅ Temperature fusion status complete!")
