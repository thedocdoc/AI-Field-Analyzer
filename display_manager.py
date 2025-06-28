"""
AI Field Analyzer v1.8 - Display Manager
----------------------------------------
Manages the SSD1325 OLED display and all screen rendering.
Designed for easy extension with menus and navigation.

Features:
- 7-screen rotation with sensor data
- Scrolling warning messages with color coding
- Smart warning generation based on sensor thresholds
- Extensible architecture for future menu system
- Optimized for SSD1325 128x64 4-bit grayscale display

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
    """
    Manages the SSD1325 OLED display and all screen rendering.
    Handles sensor data display, warning messages, and future menu system.
    """
    
    def __init__(self):
        # Display hardware
        self.display = None
        
        # Screen management
        self.current_screen = 0
        self.screens_total = 7  # CO2/VOC, Temp/Humid, Light, Weather, Radiation, System, Summary
        self.screen_names = [
            "CO2 & VOC", "TEMP & HUMID", "LIGHT & UV", "WEATHER", 
            "RADIATION", "SYSTEM", "SUMMARY"
        ]
        
        # Display state
        self.current_splash = None
        self.current_scroll_group = None
        self.current_scroll_area = None
        self.scroll_offsets = [0] * self.screens_total
        
        # Timing
        self.screen_change_time = 0
        self.display_last_update = 0
        self.data_update_time = 0
        
        # Future menu system variables
        self.menu_mode = False
        self.menu_selection = 0
        self.menu_items = []
        
        print("🖥️ Display Manager initialized")
    
    def initialize_display(self):
        """Initialize the SSD1325 OLED display"""
        print("🖥️ Initializing SSD1325 display...")
        
        try:
            displayio.release_displays()
            
            # Display SPI setup
            spi = busio.SPI(clock=board.GP14, MOSI=board.GP15)
            
            # Display pins
            oled_cs = board.GP10   # Chip Select
            oled_dc = board.GP11   # Data/Command
            oled_rst = board.GP12  # Reset
            
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
            print("✅ Display ready!")
            return True
            
        except Exception as e:
            print(f"❌ Display initialization failed: {e}")
            return False
    
    def create_text_line(self, text, y_pos, color=0xFFFFFF, x_center=True, scale=1):
        """Helper function to create text lines with positioning and scaling"""
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
        """Create scrolling text for long warning messages"""
        text_area = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
        # Start text off-screen to the right
        text_group = displayio.Group(x=width, y=y_pos)
        text_group.append(text_area)
        return text_group, text_area
    
    def update_scrolling_text(self, text_group, text_area, scroll_offset):
        """Update scrolling text position with wraparound"""
        text_width = text_area.bounding_box[2]
        new_x = 128 - scroll_offset
        
        # Reset when text completely scrolls off left side
        if new_x < -text_width:
            new_x = 128
            scroll_offset = 0
        
        text_group.x = new_x
        return scroll_offset + SCROLL_SPEED
    
    # =================================================================
    # WARNING MESSAGE GENERATION
    # =================================================================
    
    def get_co2_voc_warning(self, co2, voc):
        """Generate CO2 and VOC specific warning messages"""
        warnings = []
        max_level = 0
        
        # Check CO2 levels (highest priority for cognitive effects)
        if co2 >= 5000:
            warnings.append("CO2-CRITICAL")
            max_level = max(max_level, 4)
        elif co2 >= 2000:
            warnings.append("CO2-DANGER")
            max_level = max(max_level, 3)
        elif co2 >= 1500:
            warnings.append("CO2-WARNING")
            max_level = max(max_level, 2)
        elif co2 >= 1000:
            warnings.append("CO2-CAUTION")
            max_level = max(max_level, 1)
        
        # Check VOC levels
        if voc >= 5500:
            warnings.append("VOC-CRITICAL")
            max_level = max(max_level, 4)
        elif voc >= 2200:
            warnings.append("VOC-DANGER")
            max_level = max(max_level, 3)
        elif voc >= 1430:
            warnings.append("VOC-WARNING")
            max_level = max(max_level, 2)
        elif voc >= 660:
            warnings.append("VOC-CAUTION")
            max_level = max(max_level, 1)
        
        # Generate appropriate message and color
        if max_level >= 4:
            message = "CRITICAL: " + " | ".join(warnings) + " - EVACUATE IMMEDIATELY!"
            color = 0x444444
        elif max_level >= 3:
            message = "DANGER: " + " | ".join(warnings) + " - Leave area in 5 minutes"
            color = 0x666666
        elif max_level >= 2:
            message = "WARNING: " + " | ".join(warnings) + " - Address within 15 minutes"
            color = 0x888888
        elif max_level >= 1:
            message = "CAUTION: " + " | ".join(warnings) + " - Monitor and improve ventilation"
            color = 0xAAAAA
        else:
            message = "EXCELLENT: CO2 and VOC levels within optimal ranges"
            color = 0xFFFFFF
        
        return message, color
    
    def get_temp_humidity_warning(self, temp, humidity):
        """Generate temperature and humidity warning messages"""
        warnings = []
        max_level = 0
        
        # Check temperature
        if temp >= 35 or temp < 16:
            warnings.append("TEMP-CRITICAL")
            max_level = max(max_level, 4)
        elif temp >= 30 or temp < 18:
            warnings.append("TEMP-DANGER")
            max_level = max(max_level, 3)
        elif temp >= 28 or temp < 20:
            warnings.append("TEMP-WARNING")
            max_level = max(max_level, 2)
        elif temp > 26 or temp < 20:
            warnings.append("TEMP-NOTICE")
            max_level = max(max_level, 1)
        
        # Check humidity
        if humidity >= 90 or humidity < 20:
            warnings.append("HUMID-CRITICAL")
            max_level = max(max_level, 4)
        elif humidity >= 80 or humidity < 30:
            warnings.append("HUMID-DANGER")
            max_level = max(max_level, 3)
        elif humidity >= 70 or humidity < 40:
            warnings.append("HUMID-WARNING")
            max_level = max(max_level, 2)
        elif humidity > 60 or humidity < 40:
            warnings.append("HUMID-NOTICE")
            max_level = max(max_level, 1)
        
        # Generate message
        if max_level >= 4:
            message = "CRITICAL: " + " | ".join(warnings) + " - Immediate action required!"
            color = 0x444444
        elif max_level >= 3:
            message = "DANGER: " + " | ".join(warnings) + " - Address within 30 minutes"
            color = 0x666666
        elif max_level >= 2:
            message = "WARNING: " + " | ".join(warnings) + " - Consider climate adjustment"
            color = 0x888888
        elif max_level >= 1:
            message = "NOTICE: " + " | ".join(warnings) + " - Monitor comfort conditions"
            color = 0xAAAAA
        else:
            message = "COMFORTABLE: Temperature and humidity in ideal ranges"
            color = 0xFFFFFF
        
        return message, color
    
    def get_light_warning(self, lux):
        """Generate light/UV warning messages with UV index estimation"""
        if lux < 200:
            return "DIM: Eye strain possible - increase lighting for tasks", 0xAAAAA
        elif lux < 500:
            return "NORMAL: Typical indoor lighting - no UV concerns", 0xFFFFFF
        elif lux < 2000:
            return "BRIGHT: Comfortable outdoor light - minimal UV protection needed", 0xCCCCCC
        elif lux < 10000:
            return "BRIGHT SUN: Apply SPF 30+ sunscreen - UV Index likely 3-5", 0xAAAAA
        elif lux < 25000:
            return "STRONG SUN: UV Index 6-7 - Apply SPF 30+, seek shade 11am-3pm", 0x888888
        elif lux < 50000:
            return "VERY BRIGHT: UV Index 8-10 - Reapply SPF 30+ every 2hrs, wear hat/sunglasses", 0x666666
        else:
            return "INTENSE SUN: UV Index 11+ EXTREME - Minimize exposure 10am-4pm, full protection!", 0x444444
    
    def get_weather_warning(self, pressure, trend, storm_risk, forecast):
        """Generate weather/storm warning messages"""
        if storm_risk == "SEVERE":
            return f"SEVERE WEATHER: {forecast}", 0x333333
        elif storm_risk == "HIGH":
            return f"STORM WARNING: {forecast}", 0x555555
        elif storm_risk == "MODERATE":
            return f"WEATHER WATCH: {forecast}", 0x777777
        elif storm_risk in ["CLEARING", "IMPROVING"]:
            return f"IMPROVING: {forecast}", 0xAAAAA
        elif storm_risk == "LOW":
            return f"STABLE: {forecast}", 0xFFFFFF
        else:
            return f"MONITORING: {forecast}", 0x888888
    
    def get_radiation_warning(self, usv_h, radiation_ready):
        """Generate radiation warning messages"""
        if not radiation_ready:
            return "WARMING UP: Dose rate ready soon - CPM only", 0x888888
        elif usv_h < 0.5:
            return "SAFE: Normal background radiation", 0xFFFFFF
        elif usv_h < 5.0:
            return "ELEVATED: Limit exposure to 30 min - elevated radiation", 0xAAAAA
        else:
            return "DANGER: Evacuate in 5 min - dangerous radiation level!", 0x666666
    
    def get_system_warning(self, sensor_data):
        """Generate system performance warning messages"""
        warnings = []
        warning_level = 0
        
        # Check battery status FIRST (highest priority)
        if sensor_data['battery_low']:
            warnings.append("BATTERY-CRITICAL")
            warning_level = max(warning_level, 3)
        
        # Check CPU usage
        if sensor_data['cpu_usage'] >= 85:
            warnings.append("CPU-CRITICAL")
            warning_level = max(warning_level, 2)
        elif sensor_data['cpu_usage'] >= 70:
            warnings.append("CPU-HIGH")
            warning_level = max(warning_level, 1)
        
        # Check memory usage
        if sensor_data['memory_usage'] >= 90:
            warnings.append("MEMORY-CRITICAL")
            warning_level = max(warning_level, 2)
        elif sensor_data['memory_usage'] >= 80:
            warnings.append("MEMORY-HIGH")
            warning_level = max(warning_level, 1)
        
        # Check loop timing
        if sensor_data['avg_loop_time'] >= 0.25:
            warnings.append("TIMING-CRITICAL")
            warning_level = max(warning_level, 2)
        elif sensor_data['avg_loop_time'] >= 0.15:
            warnings.append("TIMING-SLOW")
            warning_level = max(warning_level, 1)
        
        # Generate warning message
        if warning_level == 3:  # Critical - Battery low
            message = "CRITICAL: BATTERY LOW - Save data and recharge immediately!"
            color = 0x333333
        elif warning_level == 2:
            if sensor_data['cpu_usage'] >= 85 or sensor_data['avg_loop_time'] >= 0.25:
                message = "UPGRADE TO PICO 2 RECOMMENDED - Performance critical!"
            else:
                message = "CRITICAL: " + " | ".join(warnings) + " - Consider optimization"
            color = 0x444444
        elif warning_level == 1:
            message = "CAUTION: " + " | ".join(warnings) + " - Monitor performance"
            color = 0x888888
        else:
            message = "SYSTEM OPTIMAL - All systems nominal, battery OK"
            color = 0xFFFFFF
        
        return message, color
    
    def get_summary_warning(self, sensor_data):
        """Generate comprehensive summary warning messages"""
        alerts = []
        
        # Air quality alerts
        if sensor_data['co2'] >= 2000:
            alerts.append("CO2-DANGER")
        elif sensor_data['co2'] >= 1000:
            alerts.append("CO2-CAUTION")
        
        if sensor_data['voc'] >= 2200:
            alerts.append("VOC-DANGER")
        elif sensor_data['voc'] >= 660:
            alerts.append("VOC-CAUTION")
        
        # Climate alerts
        if sensor_data['temperature'] >= 30 or sensor_data['temperature'] < 18:
            alerts.append("TEMP-WARNING")
        elif sensor_data['temperature'] >= 28 or sensor_data['temperature'] < 20:
            alerts.append("TEMP-NOTICE")
        
        if sensor_data['humidity'] >= 80 or sensor_data['humidity'] < 30:
            alerts.append("HUMID-WARNING")
        elif sensor_data['humidity'] >= 70 or sensor_data['humidity'] < 40:
            alerts.append("HUMID-NOTICE")
        
        # Radiation alerts
        if sensor_data['usv_h'] >= 5.0:
            alerts.append("RAD-DANGER")
        elif sensor_data['usv_h'] >= 0.5:
            alerts.append("RAD-ELEVATED")
        
        # Light alerts
        if sensor_data['lux'] >= 50000:
            alerts.append("LIGHT-EXTREME")
        elif sensor_data['lux'] >= 25000:
            alerts.append("LIGHT-INTENSE")
        
        # Weather alerts
        if sensor_data['storm_risk'] == "SEVERE":
            alerts.append("STORM-SEVERE")
        elif sensor_data['storm_risk'] == "HIGH":
            alerts.append("STORM-HIGH")
        elif sensor_data['storm_risk'] == "MODERATE":
            alerts.append("WEATHER-WATCH")
        
        # System alerts
        if sensor_data['battery_low']:
            alerts.append("BATTERY-LOW")
        
        if sensor_data['cpu_usage'] >= 85:
            alerts.append("SYSTEM-CRITICAL")
        
        # Generate message
        if alerts:
            status_msg = "ALERTS: " + " | ".join(alerts[:3])  # Limit to 3 alerts for space
            status_color = 0x888888
        else:
            status_msg = "ALL SYSTEMS NORMAL - Environment within safe parameters"
            status_color = 0xFFFFFF
        
        return status_msg, status_color
    
    def get_warning_message(self, screen_type, sensor_data):
        """Get appropriate warning message for each screen type"""
        if screen_type == "co2_voc":
            return self.get_co2_voc_warning(sensor_data['co2'], sensor_data['voc'])
        elif screen_type == "temp_humid":
            return self.get_temp_humidity_warning(sensor_data['temperature'], sensor_data['humidity'])
        elif screen_type == "light":
            return self.get_light_warning(sensor_data['lux'])
        elif screen_type == "weather":
            return self.get_weather_warning(sensor_data['pressure_hpa'], sensor_data['pressure_trend'], 
                                          sensor_data['storm_risk'], sensor_data['weather_forecast'])
        elif screen_type == "radiation":
            return self.get_radiation_warning(sensor_data['usv_h'], sensor_data['radiation_ready'])
        elif screen_type == "system":
            return self.get_system_warning(sensor_data)
        elif screen_type == "summary":
            return self.get_summary_warning(sensor_data)
        else:
            return "MONITORING: All systems operational", 0xFFFFFF
    
    # =================================================================
    # STARTUP AND SPECIAL SCREENS
    # =================================================================
    
    def display_startup_screen(self):
        """Show startup screen with version info"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 8, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER", 20, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("v1.8", 32, 0x888888))
        splash.append(self.create_text_line("Weather + Storm", 44, 0x666666))
        
        time.sleep(3)
    
    def display_countdown(self, seconds_remaining, status_message):
        """Show countdown with status during sensor initialization"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 6, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER", 16, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line(f"Ready in {seconds_remaining}s", 28, 0x888888))
        splash.append(self.create_text_line(status_message, 40, 0x666666))
    
    # =================================================================
    # MAIN SENSOR SCREENS
    # =================================================================
    
    def build_screen(self, screen_num, sensor_data, timestamp_str):
        """Build the specified screen with current sensor data"""
        splash = displayio.Group()
        self.display.root_group = splash
        
        if screen_num == 0:  # CO2 & VOC Screen
            splash.append(self.create_text_line("CO2 & VOC", 6, 0xFFFFFF))
            splash.append(self.create_text_line(f"CO2:{sensor_data['co2']}ppm", 18, 0xCCCCCC, False))
            splash.append(self.create_text_line(f"VOC:{sensor_data['voc']}ppb", 28, 0xCCCCCC, False))
            warning_msg, warning_color = self.get_warning_message("co2_voc", sensor_data)
            
        elif screen_num == 1:  # Temperature & Humidity Screen
            splash.append(self.create_text_line("TEMP & HUMID", 6, 0xFFFFFF))
            splash.append(self.create_text_line(f"TEMP:{sensor_data['temperature']:.1f}C", 18, 0xCCCCCC, False))
            splash.append(self.create_text_line(f"HUMID:{sensor_data['humidity']:.1f}%", 28, 0xCCCCCC, False))
            warning_msg, warning_color = self.get_warning_message("temp_humid", sensor_data)
            
        elif screen_num == 2:  # Light/UV Screen
            splash.append(self.create_text_line("LIGHT & UV", 6, 0xFFFFFF))
            lux_text = f"LUX:{sensor_data['lux']/1000:.1f}k" if sensor_data['lux'] >= 1000 else f"LUX:{sensor_data['lux']:.0f}"
            splash.append(self.create_text_line(lux_text, 18, 0xCCCCCC, False))
            
            # Light condition indicator
            if sensor_data['lux'] < 200: condition = "LOW"
            elif sensor_data['lux'] < 1000: condition = "MOD"
            elif sensor_data['lux'] < 10000: condition = "BRIGHT"
            elif sensor_data['lux'] < 50000: condition = "V.BRIGHT"
            else: condition = "INTENSE"
            
            splash.append(self.create_text_line(f"LEVEL:{condition}", 28, 0xAAAAA, False))
            warning_msg, warning_color = self.get_warning_message("light", sensor_data)
            
        elif screen_num == 3:  # Weather/Storm Screen
            splash.append(self.create_text_line("WEATHER", 6, 0xFFFFFF))
            splash.append(self.create_text_line(f"PRESS:{sensor_data['pressure_hpa']:.1f}hPa", 18, 0xCCCCCC, False))
            splash.append(self.create_text_line(f"ALT:{sensor_data['altitude_m']:.0f}m {sensor_data['pressure_trend']}", 28, 0xCCCCCC, False))
            warning_msg, warning_color = self.get_warning_message("weather", sensor_data)
            
        elif screen_num == 4:  # Radiation Screen
            splash.append(self.create_text_line("RADIATION", 6, 0xFFFFFF))
            splash.append(self.create_text_line(f"CPM:{sensor_data['cpm']}", 18, 0xCCCCCC, False))
            if sensor_data['radiation_ready']:
                splash.append(self.create_text_line(f"uSv/h:{sensor_data['usv_h']:.3f}", 28, 0xCCCCCC, False))
            else:
                splash.append(self.create_text_line("uSv/h:WARMING", 28, 0x888888, False))
            warning_msg, warning_color = self.get_warning_message("radiation", sensor_data)
            
        elif screen_num == 5:  # System Performance Screen
            splash.append(self.create_text_line("SYSTEM", 6, 0xFFFFFF))
            splash.append(self.create_text_line(f"CPU:{sensor_data['cpu_usage']:.0f}% MEM:{sensor_data['memory_usage']:.0f}%", 18, 0xCCCCCC, False))
            splash.append(self.create_text_line(f"TEMP:{sensor_data['cpu_temp']:.1f}C LOOP:{sensor_data['avg_loop_time']*1000:.0f}ms", 28, 0xCCCCCC, False))
            warning_msg, warning_color = self.get_warning_message("system", sensor_data)
            
        elif screen_num == 6:  # Summary Screen
            splash.append(self.create_text_line("SUMMARY", 6, 0xFFFFFF))
            splash.append(self.create_text_line(f"CO2:{sensor_data['co2']} VOC:{sensor_data['voc']//10}", 16, 0xCCCCCC, False))
            splash.append(self.create_text_line(f"T:{sensor_data['temperature']:.1f}C H:{sensor_data['humidity']:.0f}%", 25, 0xCCCCCC, False))
            
            lux_display = f"{sensor_data['lux']/1000:.1f}k" if sensor_data['lux'] >= 1000 else f"{sensor_data['lux']:.0f}"
            splash.append(self.create_text_line(f"P:{sensor_data['pressure_hpa']:.0f} L:{lux_display} R:{sensor_data['usv_h']:.2f}", 35, 0xCCCCCC, False))
            warning_msg, warning_color = self.get_warning_message("summary", sensor_data)
        
        # Add scrolling warning message
        self.current_scroll_group, self.current_scroll_area = self.create_scrolling_text(warning_msg, 39, warning_color)
        splash.append(self.current_scroll_group)
        
        # Add timestamp
        splash.append(self.create_text_line(f"Time: {timestamp_str}", 60, 0x666666, False))
        
        self.current_splash = splash
        return splash
    
    def update_screen_data(self, sensor_data, timestamp_str):
        """Update dynamic data on current screen without rebuilding"""
        if not self.current_splash or len(self.current_splash) < 4:
            return
        
        try:
            # Update based on current screen
            if self.current_screen == 0:  # CO2 & VOC
                self.current_splash[1][0].text = f"CO2:{sensor_data['co2']}ppm"
                self.current_splash[2][0].text = f"VOC:{sensor_data['voc']}ppb"
                warning_msg, warning_color = self.get_warning_message("co2_voc", sensor_data)
                
            elif self.current_screen == 1:  # Temperature & Humidity
                self.current_splash[1][0].text = f"TEMP:{sensor_data['temperature']:.1f}C"
                self.current_splash[2][0].text = f"HUMID:{sensor_data['humidity']:.1f}%"
                warning_msg, warning_color = self.get_warning_message("temp_humid", sensor_data)
                
            elif self.current_screen == 2:  # Light
                lux_text = f"LUX:{sensor_data['lux']/1000:.1f}k" if sensor_data['lux'] >= 1000 else f"LUX:{sensor_data['lux']:.0f}"
                self.current_splash[1][0].text = lux_text
                
                # Update light condition
                if sensor_data['lux'] < 200: condition = "LOW"
                elif sensor_data['lux'] < 1000: condition = "MOD"
                elif sensor_data['lux'] < 10000: condition = "BRIGHT"
                elif sensor_data['lux'] < 50000: condition = "V.BRIGHT"
                else: condition = "INTENSE"
                self.current_splash[2][0].text = f"LEVEL:{condition}"
                warning_msg, warning_color = self.get_warning_message("light", sensor_data)
                
            elif self.current_screen == 3:  # Weather
                self.current_splash[1][0].text = f"PRESS:{sensor_data['pressure_hpa']:.1f}hPa"
                self.current_splash[2][0].text = f"ALT:{sensor_data['altitude_m']:.0f}m {sensor_data['pressure_trend']}"
                warning_msg, warning_color = self.get_warning_message("weather", sensor_data)
                
            elif self.current_screen == 4:  # Radiation
                self.current_splash[1][0].text = f"CPM:{sensor_data['cpm']}"
                if sensor_data['radiation_ready']:
                    self.current_splash[2][0].text = f"uSv/h:{sensor_data['usv_h']:.3f}"
                else:
                    self.current_splash[2][0].text = "uSv/h:WARMING"
                warning_msg, warning_color = self.get_warning_message("radiation", sensor_data)
                
            elif self.current_screen == 5:  # System
                self.current_splash[1][0].text = f"CPU:{sensor_data['cpu_usage']:.0f}% MEM:{sensor_data['memory_usage']:.0f}%"
                self.current_splash[2][0].text = f"TEMP:{sensor_data['cpu_temp']:.1f}C LOOP:{sensor_data['avg_loop_time']*1000:.0f}ms"
                warning_msg, warning_color = self.get_warning_message("system", sensor_data)
                
            elif self.current_screen == 6:  # Summary
                self.current_splash[1][0].text = f"CO2:{sensor_data['co2']} VOC:{sensor_data['voc']//10}"
                self.current_splash[2][0].text = f"T:{sensor_data['temperature']:.1f}C H:{sensor_data['humidity']:.0f}%"
                lux_display = f"{sensor_data['lux']/1000:.1f}k" if sensor_data['lux'] >= 1000 else f"{sensor_data['lux']:.0f}"
                self.current_splash[3][0].text = f"P:{sensor_data['pressure_hpa']:.0f} L:{lux_display} R:{sensor_data['usv_h']:.2f}"
                warning_msg, warning_color = self.get_warning_message("summary", sensor_data)
            
            # Update timestamp (always last element)
            if len(self.current_splash) > 4:
                self.current_splash[-1][0].text = f"Time: {timestamp_str}"
            
            # Update warning message
            if self.current_scroll_area:
                self.current_scroll_area.text = warning_msg
                self.current_scroll_area.color = warning_color
                
        except Exception as e:
            print(f"⚠️ Display update error: {e}")
    
    # =================================================================
    # MAIN DISPLAY UPDATE LOGIC
    # =================================================================
    
    def update_display(self, sensor_data, force_rebuild=False):
        """Main display update function - handles screen rotation and updates"""
        current_time = time.monotonic()
        timestamp = time.localtime()
        timestamp_str = f"{timestamp.tm_hour:02}:{timestamp.tm_min:02}:{timestamp.tm_sec:02}"
        
        # Check for screen change (automatic rotation)
        if current_time - self.screen_change_time >= SCREEN_DURATION:
            self.current_screen = (self.current_screen + 1) % self.screens_total
            self.screen_change_time = current_time
            self.scroll_offsets[self.current_screen] = 0  # Reset scroll for new screen
            force_rebuild = True
            print(f"🔄 Screen change: {self.screen_names[self.current_screen]} ({self.current_screen + 1}/{self.screens_total})")
        
        # Rebuild screen if needed (screen change or forced)
        if force_rebuild:
            self.build_screen(self.current_screen, sensor_data, timestamp_str)
        
        # Update screen data periodically without rebuilding
        elif current_time - self.data_update_time >= DATA_UPDATE_RATE:
            self.update_screen_data(sensor_data, timestamp_str)
            self.data_update_time = current_time
        
        # Update scrolling text animation
        if (current_time - self.display_last_update >= SCROLL_REFRESH and 
            self.current_scroll_group and self.current_scroll_area):
            self.scroll_offsets[self.current_screen] = self.update_scrolling_text(
                self.current_scroll_group, self.current_scroll_area, 
                self.scroll_offsets[self.current_screen]
            )
            self.display_last_update = current_time
    
    # =================================================================
    # FUTURE MENU SYSTEM (PLACEHOLDER)
    # =================================================================
    
    def enter_menu_mode(self):
        """Enter menu mode (future implementation)"""
        self.menu_mode = True
        self.menu_selection = 0
        self.menu_items = [
            "Settings",
            "Calibration", 
            "Data Export",
            "Diagnostics",
            "About",
            "Exit Menu"
        ]
        print("📋 Menu mode activated")
        # TODO: Implement menu display
    
    def exit_menu_mode(self):
        """Exit menu mode and return to sensor display"""
        self.menu_mode = False
        self.menu_selection = 0
        self.menu_items = []
        print("📊 Returning to sensor display")
        # Force screen rebuild when exiting menu
        return True  # Signal to force rebuild
    
    def navigate_menu(self, direction):
        """Navigate menu selection (future implementation)"""
        if not self.menu_mode:
            return
            
        if direction == "up":
            self.menu_selection = (self.menu_selection - 1) % len(self.menu_items)
        elif direction == "down":
            self.menu_selection = (self.menu_selection + 1) % len(self.menu_items)
        
        print(f"📋 Menu: {self.menu_items[self.menu_selection]}")
        # TODO: Update menu display
    
    def select_menu_item(self):
        """Select current menu item (future implementation)"""
        if not self.menu_mode:
            return
            
        selected_item = self.menu_items[self.menu_selection]
        print(f"📋 Selected: {selected_item}")
        
        # TODO: Implement menu actions
        if selected_item == "Exit Menu":
            return self.exit_menu_mode()
        
        return False
    
    # =================================================================
    # DISPLAY UTILITIES AND STATUS
    # =================================================================
    
    def force_screen_change(self, screen_number):
        """Manually change to a specific screen"""
        if 0 <= screen_number < self.screens_total:
            self.current_screen = screen_number
            self.screen_change_time = time.monotonic()
            self.scroll_offsets[self.current_screen] = 0
            print(f"🔄 Manual screen change: {self.screen_names[self.current_screen]}")
            return True
        return False
    
    def get_current_screen_info(self):
        """Get information about current screen"""
        return {
            'screen_number': self.current_screen,
            'screen_name': self.screen_names[self.current_screen],
            'total_screens': self.screens_total,
            'menu_mode': self.menu_mode,
            'scroll_offset': self.scroll_offsets[self.current_screen]
        }
    
    def display_error_screen(self, error_message):
        """Show error screen for critical failures"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("ERROR", 8, 0x444444, True, 1))
        splash.append(self.create_text_line("SYSTEM FAULT", 20, 0x666666))
        splash.append(self.create_text_line(error_message[:20], 32, 0x888888))  # Truncate long messages
        splash.append(self.create_text_line("Check connections", 44, 0xAAAAA))
        splash.append(self.create_text_line("Restart device", 56, 0xAAAAA))
        
        print(f"❌ Error screen displayed: {error_message}")
    
    def display_diagnostic_screen(self, diagnostic_info):
        """Show diagnostic information screen"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("DIAGNOSTICS", 6, 0xFFFFFF))
        splash.append(self.create_text_line(f"Sensors: {diagnostic_info.get('sensor_count', 0)}/3", 18, 0xCCCCCC, False))
        splash.append(self.create_text_line(f"Memory: {diagnostic_info.get('memory_free', 0)}KB", 28, 0xCCCCCC, False))
        splash.append(self.create_text_line(f"Uptime: {diagnostic_info.get('uptime', 0)}min", 38, 0xCCCCCC, False))
        
        status = "PASS" if diagnostic_info.get('all_ok', False) else "FAIL"
        color = 0xFFFFFF if diagnostic_info.get('all_ok', False) else 0x888888
        splash.append(self.create_text_line(f"Status: {status}", 50, color, False))
        
        print("🔧 Diagnostic screen displayed")
    
    def set_display_brightness(self, brightness):
        """Set display brightness (if supported by hardware)"""
        # Note: SSD1325 brightness control would be implemented here
        # This is a placeholder for future enhancement
        print(f"🔆 Display brightness set to {brightness}%")
    
    def get_display_status(self):
        """Get comprehensive display status"""
        return {
            'initialized': self.display is not None,
            'current_screen': self.current_screen,
            'screen_name': self.screen_names[self.current_screen],
            'menu_mode': self.menu_mode,
            'scroll_position': self.scroll_offsets[self.current_screen],
            'last_update': self.display_last_update,
            'screen_change_time': self.screen_change_time,
            'screens_total': self.screens_total
        }
    
    def __del__(self):
        """Cleanup display resources when object is destroyed"""
        try:
            if self.display:
                # Clear display
                splash = displayio.Group()
                self.display.root_group = splash
                print("🖥️ Display cleared")
        except:
            pass
