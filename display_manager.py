"""
AI Field Analyzer v2.5 - FIXED Triangle Spinner (No Screen Flicker)
------------------------------------------------------------------------
Triangle spinner now updates independently without rebuilding entire screen.
Position moved up 2 pixels, speed increased slightly.

© 2025 Apollo Timbers. MIT License.
"""

import time
import board
import busio
import displayio
import terminalio
import math
from fourwire import FourWire
from adafruit_display_text import label
import adafruit_ssd1325

# Import shapes for triangle spinner
try:
    from adafruit_display_shapes.line import Line
    SHAPES_AVAILABLE = True
except ImportError:
    SHAPES_AVAILABLE = False

# Display configuration constants
SCREEN_DURATION = 12        # Seconds per screen
SCROLL_SPEED = 2           # Pixels per scroll frame
SCROLL_FPS = 15            # Scroll animation FPS
DATA_UPDATE_RATE = 3       # Screen data update interval
SCROLL_REFRESH = 1.0 / SCROLL_FPS

class TriangleSpinner:
    """Triangle activity spinner for display corner - Independent updates"""
    
    def __init__(self, x=5, y=5):  # Moved up 2 pixels (was y=8, now y=6)
        self.x = x
        self.y = y
        self.size = 5
        self.color = 0x888888
        self.frame = 0
        self.speed = 0.4  # Increased speed (was 0.6, now 0.4 - lower = faster)
        self.last_update = 0
        self.shapes_available = SHAPES_AVAILABLE
        self.text_chars = ['|', '/', '-', '\\']
        self.current_group = None
        
    def create_element(self):
        """Create spinner element (graphics or text fallback)"""
        if self.shapes_available:
            self.current_group = self.create_triangle_graphics()
        else:
            self.current_group = self.create_triangle_text()
        return self.current_group
    
    def create_triangle_graphics(self):
        """Create rotating triangle using graphics shapes"""
        group = displayio.Group()
        
        # Smooth rotation (30 degrees per frame)
        angle = (self.frame * 30) % 360
        rad = math.radians(angle)
        
        # Triangle points
        points = [
            (0, -self.size),
            (self.size * 0.866, self.size * 0.5),
            (-self.size * 0.866, self.size * 0.5)
        ]
        
        # Rotate points
        rotated_points = []
        for px, py in points:
            rx = px * math.cos(rad) - py * math.sin(rad)
            ry = px * math.sin(rad) + py * math.cos(rad)
            rotated_points.append((self.x + int(rx), self.y + int(ry)))
        
        # Draw triangle lines
        for i in range(3):
            x1, y1 = rotated_points[i]
            x2, y2 = rotated_points[(i + 1) % 3]
            line = Line(x1, y1, x2, y2, color=self.color)
            group.append(line)
        
        return group
    
    def create_triangle_text(self):
        """Create text-based spinner fallback"""
        current_char = self.text_chars[self.frame % len(self.text_chars)]
        
        text = label.Label(terminalio.FONT, text=current_char, 
                          color=self.color, scale=1)
        text.x = self.x - 3
        text.y = self.y
        
        group = displayio.Group()
        group.append(text)
        return group
    
    def update_in_place(self, parent_group):
        """Update spinner animation in-place without rebuilding screen"""
        current_time = time.monotonic()
        
        if current_time - self.last_update >= self.speed:
            self.frame += 1
            self.last_update = current_time
            
            # Remove old spinner from parent group
            if self.current_group and self.current_group in parent_group:
                parent_group.remove(self.current_group)
            
            # Create and add new spinner
            self.current_group = self.create_element()
            if self.current_group:
                parent_group.append(self.current_group)
            
            return True
        
        return False
    
    def update(self):
        """Legacy update method - returns True if frame changed"""
        current_time = time.monotonic()
        
        if current_time - self.last_update >= self.speed:
            self.frame += 1
            self.last_update = current_time
            return True
        
        return False

class DisplayManager:
    """Enhanced display manager with improved triangle spinner (no flicker)"""
    
    def __init__(self):
        # Display hardware
        self.display = None
        
        # Enhanced screen management (now 9 screens)
        self.current_screen = 0
        self.screens_total = 9
        self.screen_names = [
            "CO2 & VOC", "TEMP & HUMIDITY", "LIGHT & UV", "WEATHER", 
            "RADIATION", "SYSTEM", "SUMMARY", "GPS DATA", "NAVIGATION"
        ]
        
        # Display state
        self.current_splash = None
        self.current_scroll_group = None
        self.current_scroll_area = None
        self.scroll_offsets = [0] * self.screens_total
        self.scroll_text_width = 0
        
        # Timing
        self.screen_change_time = 0
        self.display_last_update = 0
        self.data_update_time = 0
        
        # IMPROVED TRIANGLE SPINNER - No screen rebuilds
        self.triangle_spinner = TriangleSpinner(x=5, y=6)  # Moved up 2 pixels
        self.spinner_enabled = True
        
        print("🖥️ Enhanced Display Manager with FIXED Triangle Spinner initialized")
    
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
            oled_rst = board.GP16
            
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
            print("✅ Display with FIXED triangle spinner ready!")
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
        """Create scrolling text"""
        text_area = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
        text_group = displayio.Group(x=width, y=y_pos)
        text_group.append(text_area)
    
        try:
            if text_area.bounding_box and text_area.bounding_box[2] and text_area.bounding_box[2] > 0:
                self.scroll_text_width = text_area.bounding_box[2]
            else:
                self.scroll_text_width = len(str(text)) * 6 * scale
        except:
            self.scroll_text_width = len(str(text)) * 6 * scale
    
        return text_group, text_area
    
    def update_scrolling_text(self, text_group, text_area, scroll_offset):
        """Update scrolling text position"""
        try:
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
        
            new_x = 128 - scroll_offset
        
            if new_x < -text_width - 10:
                scroll_offset = 0
                new_x = 128
        
            text_group.x = new_x
            return scroll_offset + SCROLL_SPEED
        
        except Exception as e:
            print(f"Scroll error: {e}")
            return 0

    def get_gps_time_or_fallback(self, sensor_data):
        """Get GPS time if available, convert to Central Time, otherwise use system time"""
        gps_time = sensor_data.get('gps_time', None)
        gps_date = sensor_data.get('gps_date', None)
        
        if gps_time and gps_time != 'None' and gps_time is not None:
            try:
                if isinstance(gps_time, str) and ':' in gps_time:
                    parts = gps_time.split(':')
                    if len(parts) >= 2:
                        utc_hour = int(parts[0])
                        minute = int(parts[1])
                        second = int(parts[2]) if len(parts) > 2 else 0
                        
                        central_hour = (utc_hour - 5) % 24
                        central_time = f"{central_hour:02d}:{minute:02d}:{second:02d}"
                        
                        if gps_date and gps_date != 'None' and gps_date is not None:
                            return f"{central_time} GPS", True
                        else:
                            return f"{central_time} GPS", True
                    else:
                        raise ValueError("Invalid GPS time format")
                else:
                    raise ValueError("GPS time not in expected format")
            except (ValueError, TypeError, IndexError) as e:
                print(f"⚠️ GPS time conversion error: {e}, falling back to system time")
        
        timestamp = time.localtime()
        sys_time = f"{timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
        return f"{sys_time} SYS", False

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

    def build_screen(self, screen_num, sensor_data, gps_timestamp_str, gps_time_available):
        """Build screen with triangle spinner that updates independently"""
        if self.display and self.display.root_group:
            try:
                self.display.root_group = displayio.Group()
            except Exception as e:
                print(f"Warning: Could not clear display group: {e}")
        
        splash = displayio.Group()
        self.scroll_offsets[screen_num] = 0
        
        try:
            if screen_num == 0:  # CO2 & VOC
                splash.append(self.create_text_line("CO2 & VOC", 6, 0xFFFFFF))
                co2_val = sensor_data.get('co2', 'ERR')
                voc_val = sensor_data.get('voc', 'ERR')
                splash.append(self.create_text_line(f"CO2:{co2_val}ppm", 18, 0xCCCCCC, False))
                splash.append(self.create_text_line(f"VOC:{voc_val}ppb", 28, 0xCCCCCC, False))
                warning_msg, warning_color = self.get_co2_warning(sensor_data.get('co2', 400))
                
            elif screen_num == 1:  # Temperature & Humidity
                splash.append(self.create_text_line("TEMP & HUMIDITY", 6, 0xFFFFFF))
                
                fused_temp = sensor_data.get('temperature_fused', None)
                temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
                active_sensors = sensor_data.get('active_temperature_sensors', 0)
                humidity_val = sensor_data.get('humidity', 'ERR')
                
                if fused_temp is not None:
                    try:
                        splash.append(self.create_text_line(f"TEMP:{fused_temp:.1f}C", 16, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("TEMP:FORMAT_ERR", 16, 0x666666, False))
                else:
                    splash.append(self.create_text_line("TEMP:ERROR", 16, 0x666666, False))
                
                if humidity_val != 'ERR' and humidity_val is not None:
                    try:
                        splash.append(self.create_text_line(f"HUM:{humidity_val:.0f}%", 26, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("HUM:FORMAT_ERR", 26, 0x666666, False))
                else:
                    splash.append(self.create_text_line("HUM:ERROR", 26, 0x666666, False))
                
                source_short = temp_source[:6] if temp_source != "UNKNOWN" else "UNK"
                active_sensors = active_sensors if active_sensors is not None else 0
                splash.append(self.create_text_line(f"SRC:{source_short} ({active_sensors}/2)", 36, 0xAAAAA, False))
                
                warning_msg, warning_color = "Temperature and humidity monitoring active", 0xFFFFFF
                
            elif screen_num == 2:  # Light & UV
                splash.append(self.create_text_line("LIGHT & UV", 6, 0xFFFFFF))
                lux_val = sensor_data.get('lux', 0)
                if lux_val == 'ERR' or lux_val is None:
                    lux_text = "LUX:ERROR"
                else:
                    try:
                        lux_text = f"LUX:{lux_val/1000:.1f}k" if lux_val >= 1000 else f"LUX:{lux_val:.0f}"
                    except (ValueError, TypeError):
                        lux_text = "LUX:FORMAT_ERR"
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
                
            elif screen_num == 3:  # Weather
                splash.append(self.create_text_line("WEATHER", 6, 0xFFFFFF))
                
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                if current_location == "OUTDOOR":
                    pressure_val = sensor_data.get('pressure_hpa', 'ERR')
                    if pressure_val != 'ERR' and pressure_val is not None:
                        try:
                            splash.append(self.create_text_line(f"PRESS:{pressure_val:.1f}hPa", 16, 0xCCCCCC, False))
                        except (ValueError, TypeError):
                            splash.append(self.create_text_line("PRESS:FORMAT_ERR", 16, 0x666666, False))
                    else:
                        splash.append(self.create_text_line("PRESS:ERROR", 16, 0x666666, False))
                    
                    storm_prob = sensor_data.get('weather_storm_probability', 0)
                    weather_type = sensor_data.get('weather_forecast_type', 'UNKNOWN')
                    
                    if storm_prob is None:
                        storm_prob = 0
                    
                    try:
                        if storm_prob > 0:
                            type_short = weather_type.replace('_', '')[:8]
                            splash.append(self.create_text_line(f"{type_short}:{storm_prob}%", 26, 0xCCCCCC, False))
                        else:
                            splash.append(self.create_text_line(f"{weather_type[:12]}", 26, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("WEATHER:FORMAT_ERR", 26, 0x666666, False))
                    
                    warning_msg, warning_color = "Weather monitoring active - outdoor mode", 0xFFFFFF
                    
                else:
                    splash.append(self.create_text_line(f"LOCATION:{current_location}", 18, 0x888888, False))
                    splash.append(self.create_text_line("Weather monitoring", 28, 0x888888, False))
                    splash.append(self.create_text_line("paused indoors", 38, 0x888888, False))
                    warning_msg, warning_color = f"Weather monitoring paused - {current_location.lower()} environment", 0x888888
                
            elif screen_num == 4:  # Radiation
                splash.append(self.create_text_line("RADIATION", 6, 0xFFFFFF))
                cpm_val = sensor_data.get('cpm', 'ERR')
                usv_val = sensor_data.get('usv_h', 'ERR')
                rad_ready = sensor_data.get('radiation_ready', False)
                
                splash.append(self.create_text_line(f"CPM:{cpm_val}", 18, 0xCCCCCC, False))
                if rad_ready and usv_val != 'ERR':
                    try:
                        splash.append(self.create_text_line(f"uSv/h:{usv_val:.3f}", 28, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("uSv/h:FORMAT_ERR", 28, 0x666666, False))
                else:
                    splash.append(self.create_text_line("uSv/h:WARMING", 28, 0x888888, False))
                
                usv_value = usv_val if isinstance(usv_val, (int, float)) else 0
                warning_msg, warning_color = self.get_radiation_warning(usv_value, rad_ready)
                
            elif screen_num == 5:  # System
                splash.append(self.create_text_line("SYSTEM", 6, 0xFFFFFF))
                cpu_usage = sensor_data.get('cpu_usage', 'ERR')
                mem_usage = sensor_data.get('memory_usage', 'ERR')
                
                if cpu_usage != 'ERR' and mem_usage != 'ERR':
                    try:
                        cpu_val = cpu_usage if cpu_usage is not None else 0
                        mem_val = mem_usage if mem_usage is not None else 0
                        splash.append(self.create_text_line(f"CPU:{cpu_val:.0f}% MEM:{mem_val:.0f}%", 18, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("CPU:ERR MEM:ERR", 18, 0x666666, False))
                else:
                    splash.append(self.create_text_line("CPU:ERR MEM:ERR", 18, 0x666666, False))
                
                battery_low = sensor_data.get('battery_low', False)
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                battery_status = "LOW" if battery_low else "OK"
                splash.append(self.create_text_line(f"BATTERY:{battery_status} LOC:{current_location[:3]}", 28, 0xCCCCCC, False))
                warning_msg, warning_color = f"System monitoring - {current_location} mode", 0xFFFFFF
                
            elif screen_num == 6:  # Summary
                splash.append(self.create_text_line("SUMMARY", 6, 0xFFFFFF))
                
                co2_val = sensor_data.get('co2', 'ERR')
                voc_val = sensor_data.get('voc', 'ERR')
                try:
                    voc_display = voc_val // 10 if isinstance(voc_val, (int, float)) else 'ERR'
                    splash.append(self.create_text_line(f"CO2:{co2_val} VOC:{voc_display}", 16, 0xCCCCCC, False))
                except (ValueError, TypeError):
                    splash.append(self.create_text_line("CO2:ERR VOC:ERR", 16, 0x666666, False))
                
                fused_temp = sensor_data.get('temperature_fused', sensor_data.get('temperature', 'ERR'))
                humidity_val = sensor_data.get('humidity', 'ERR')
                if fused_temp != 'ERR' and humidity_val != 'ERR':
                    try:
                        temp_val = fused_temp if fused_temp is not None else 0
                        hum_val = humidity_val if humidity_val is not None else 0
                        splash.append(self.create_text_line(f"T:{temp_val:.1f}C H:{hum_val:.0f}%", 25, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("T:ERR H:ERR", 25, 0x666666, False))
                else:
                    splash.append(self.create_text_line("T:ERR H:ERR", 25, 0x666666, False))
                
                location = sensor_data.get('current_location', 'UNK')[:3]
                battery_low = sensor_data.get('battery_low', False)
                battery_status = "LOW" if battery_low else "OK"
                
                splash.append(self.create_text_line(f"LOC:{location} BAT:{battery_status}", 35, 0xCCCCCC, False))
                warning_msg, warning_color = f"System summary - all sensors active", 0xFFFFFF
                
            elif screen_num == 7:  # GPS Data
                splash.append(self.create_text_line("GPS DATA", 6, 0xFFFFFF))
                
                gps_available = sensor_data.get('gps_available', False)
                if gps_available:
                    gps_lat = sensor_data.get('gps_latitude', None)
                    if gps_lat is not None and isinstance(gps_lat, (int, float)):
                        try:
                            lat_str = f"LAT:{gps_lat:.6f}"
                            splash.append(self.create_text_line(lat_str, 16, 0xCCCCCC, False))
                        except (ValueError, TypeError):
                            splash.append(self.create_text_line("LAT:FORMAT ERR", 16, 0x666666, False))
                    else:
                        splash.append(self.create_text_line("LAT:NO FIX", 16, 0x666666, False))
                    
                    gps_lon = sensor_data.get('gps_longitude', None)
                    if gps_lon is not None and isinstance(gps_lon, (int, float)):
                        try:
                            lon_str = f"LON:{gps_lon:.6f}"
                            splash.append(self.create_text_line(lon_str, 26, 0xCCCCCC, False))
                        except (ValueError, TypeError):
                            splash.append(self.create_text_line("LON:FORMAT ERR", 26, 0x666666, False))
                    else:
                        splash.append(self.create_text_line("LON:NO FIX", 26, 0x666666, False))
                    
                    gps_speed = sensor_data.get('gps_speed_knots', 0)
                    gps_course = sensor_data.get('gps_course', None)
                    
                    if gps_speed is None:
                        gps_speed = 0
                        
                    try:
                        if gps_course is not None and isinstance(gps_course, (int, float)):
                            course_str = f"SPD:{gps_speed:.1f}kt HDG:{gps_course:.0f}°"
                            splash.append(self.create_text_line(course_str, 36, 0xAAAAA, False))
                        else:
                            speed_str = f"SPEED:{gps_speed:.1f} knots"
                            splash.append(self.create_text_line(speed_str, 36, 0xAAAAA, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("SPEED:FORMAT ERR", 36, 0x666666, False))
                    
                    gps_satellites = sensor_data.get('gps_satellites', 0)
                    if gps_satellites is None:
                        gps_satellites = 0
                    
                    warning_msg, warning_color = f"GPS active - {gps_satellites} satellites", 0xFFFFFF
                else:
                    splash.append(self.create_text_line("GPS:OFFLINE", 18, 0x666666, False))
                    splash.append(self.create_text_line("Hardware not", 28, 0x666666, False))
                    splash.append(self.create_text_line("available", 38, 0x666666, False))
                    warning_msg, warning_color = "GPS hardware not available - using sensor fallback", 0x666666
                
            elif screen_num == 8:  # Navigation
                splash.append(self.create_text_line("NAVIGATION", 6, 0xFFFFFF))
                
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                location_confidence = sensor_data.get('location_confidence', 0)
                
                if location_confidence is None:
                    location_confidence = 0
                    
                try:
                    splash.append(self.create_text_line(f"LOC:{current_location} {location_confidence}%", 16, 0xCCCCCC, False))
                except (ValueError, TypeError):
                    splash.append(self.create_text_line(f"LOC:{current_location} ERR%", 16, 0x666666, False))
                
                gps_available = sensor_data.get('gps_available', False)
                if gps_available:
                    gps_confidence = sensor_data.get('gps_confidence_level', 0)
                    gps_anti_spoofing = sensor_data.get('gps_anti_spoofing_status', 'UNK')
                    
                    if gps_confidence is None:
                        gps_confidence = 0
                    if gps_anti_spoofing is None:
                        gps_anti_spoofing = 'UNK'
                    
                    spoofing_short = gps_anti_spoofing[:4]
                    try:
                        splash.append(self.create_text_line(f"GPS:{spoofing_short} {gps_confidence}%", 26, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line("GPS:FORMAT_ERR", 26, 0x666666, False))
                else:
                    splash.append(self.create_text_line("GPS:OFFLINE", 26, 0x666666, False))
                
                warning_msg, warning_color = f"Navigation system - {current_location} mode active", 0xFFFFFF
            
            # ADD TRIANGLE SPINNER TO EVERY SCREEN (Initial placement only)
            if self.spinner_enabled:
                spinner_element = self.triangle_spinner.create_element()
                if spinner_element:
                    splash.append(spinner_element)
            
            # Add scrolling warning message
            self.current_scroll_group, self.current_scroll_area = self.create_scrolling_text(warning_msg, 49, warning_color)
            splash.append(self.current_scroll_group)
            
            # Add enhanced timestamp with location and GPS status
            location_indicator = sensor_data.get('current_location', 'UNK')[:3]
            temp_source_indicator = sensor_data.get('temperature_source', 'UNK')[:1]
            gps_indicator = "G" if gps_time_available else "S"
            enhanced_timestamp = f"{gps_timestamp_str} {location_indicator} T{temp_source_indicator} {gps_indicator}"
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
            
            # Add spinner to error screen too
            if self.spinner_enabled:
                spinner_element = self.triangle_spinner.create_element()
                if spinner_element:
                    error_splash.append(spinner_element)
            
            if self.display:
                self.display.root_group = error_splash
            return error_splash
    
    def update_display(self, sensor_data, force_rebuild=False):
        """Main display update function with FIXED triangle spinner (no screen flicker)"""
        if not self.display:
            return
            
        current_time = time.monotonic()
        display_updated = False
        
        # UPDATE TRIANGLE SPINNER IN-PLACE (No screen rebuild!)
        if self.spinner_enabled and self.current_splash:
            try:
                spinner_updated = self.triangle_spinner.update_in_place(self.current_splash)
                # NOTE: We don't set force_rebuild=True here anymore!
                # This prevents screen flicker
            except Exception as e:
                print(f"⚠️ Spinner update error: {e}")
        
        # Get GPS time or fallback to system time
        gps_timestamp_str, gps_time_available = self.get_gps_time_or_fallback(sensor_data)
        
        # Enhance sensor data with temperature fusion if available
        enhanced_sensor_data = self._enhance_sensor_data_with_fusion(sensor_data)
        
        # Check for screen change
        if current_time - self.screen_change_time >= SCREEN_DURATION:
            self.current_screen = (self.current_screen + 1) % self.screens_total
            self.screen_change_time = current_time
            self.scroll_offsets[self.current_screen] = 0
            force_rebuild = True
            print(f"🔄 Screen: {self.screen_names[self.current_screen]} ({self.current_screen + 1}/{self.screens_total})")
        
        # Rebuild screen if needed (only for screen changes, not spinner updates)
        if force_rebuild or self.current_splash is None:
            try:
                self.build_screen(self.current_screen, enhanced_sensor_data, gps_timestamp_str, gps_time_available)
                display_updated = True
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
                self.scroll_offsets[self.current_screen] = 0
        
        return display_updated
    
    def toggle_spinner(self, enabled=None):
        """Enable/disable triangle spinner"""
        if enabled is None:
            self.spinner_enabled = not self.spinner_enabled
        else:
            self.spinner_enabled = enabled
        
        print(f"🔺 Triangle spinner {'enabled' if self.spinner_enabled else 'disabled'}")
    
    def _enhance_sensor_data_with_fusion(self, sensor_data):
        """Enhanced sensor data with improved temperature fusion detection"""
        enhanced_data = sensor_data.copy()
        
        bmp390_temp = enhanced_data.get('bmp390_temperature', None)
        scd41_temp = enhanced_data.get('temperature', None)
        
        scd41_in_range = (scd41_temp is not None and -10 <= scd41_temp <= 60)
        
        active_sensors = 0
        if bmp390_temp is not None:
            active_sensors += 1
        if scd41_temp is not None and scd41_in_range:
            active_sensors += 1
        
        if bmp390_temp is not None and scd41_temp is not None and scd41_in_range:
            fused_temp = (bmp390_temp * 0.65 + scd41_temp * 0.35)
            temp_source = "FUSED"
            redundancy_active = True
        elif bmp390_temp is not None:
            fused_temp = bmp390_temp
            temp_source = "BMP390"
            redundancy_active = False
        elif scd41_temp is not None and scd41_in_range:
            fused_temp = scd41_temp
            temp_source = "SCD41"
            redundancy_active = False
        elif scd41_temp is not None and not scd41_in_range:
            fused_temp = None
            temp_source = "SCD41_OUT_OF_RANGE"
            redundancy_active = False
        else:
            fused_temp = None
            temp_source = "FAILED"
            redundancy_active = False
        
        enhanced_data['temperature_fused'] = fused_temp
        enhanced_data['temperature_source'] = temp_source
        enhanced_data['active_temperature_sensors'] = active_sensors
        enhanced_data['temperature_redundancy_active'] = redundancy_active
        enhanced_data['scd41_in_range'] = scd41_in_range
        enhanced_data['temperature_failover_available'] = fused_temp is not None
        
        return enhanced_data
    
    def display_startup_screen(self):
        """Enhanced startup screen with triangle spinner"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 8, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER", 20, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("v2.5 FIXED", 32, 0x888888))
        splash.append(self.create_text_line("No Flicker Spinner", 44, 0x666666))
        
        # Add triangle spinner to startup screen
        if self.spinner_enabled:
            spinner_element = self.triangle_spinner.create_element()
            if spinner_element:
                splash.append(spinner_element)
        
        time.sleep(3)
    
    def display_countdown(self, seconds_remaining, status_message):
        """Enhanced countdown screen with triangle spinner"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 6, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER v2.5", 16, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line(f"Ready in {seconds_remaining}s", 28, 0x888888))
        splash.append(self.create_text_line(status_message[:20], 40, 0x666666))
        splash.append(self.create_text_line("Fixed Spinner Active", 52, 0x444444))
        
        # Add triangle spinner to countdown screen
        if self.spinner_enabled:
            spinner_element = self.triangle_spinner.create_element()
            if spinner_element:
                splash.append(spinner_element)
    
    def display_error_screen(self, error_message):
        """Enhanced error screen with triangle spinner"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("ERROR", 8, 0x444444, True, 1))
        splash.append(self.create_text_line("SYSTEM FAULT", 20, 0x666666))
        splash.append(self.create_text_line(error_message[:20], 32, 0x888888))
        splash.append(self.create_text_line("Check connections", 44, 0xAAAAA))
        splash.append(self.create_text_line("Restart device", 56, 0xAAAAA))
        
        # Add triangle spinner to error screen
        if self.spinner_enabled:
            spinner_element = self.triangle_spinner.create_element()
            if spinner_element:
                splash.append(spinner_element)
        
        print(f"❌ Enhanced error screen: {error_message}")

# Helper functions for console output - simplified versions
def get_enhanced_console_status(sensor_data):
    """Get enhanced console status line"""
    timestamp = time.localtime()
    timestamp_str = f"{timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
    
    location = sensor_data.get('current_location', 'UNK')[:3]
    co2_val = sensor_data.get('co2', 'ERR')
    temp_val = sensor_data.get('temperature', 'ERR')
    pressure_val = sensor_data.get('pressure_hpa', 'ERR')
    usv_h_val = sensor_data.get('usv_h', 'ERR')
    battery_low = sensor_data.get('battery_low', False)
    
    try:
        temp_str = f"T:{temp_val:.1f}C" if temp_val != 'ERR' and temp_val is not None else "T:ERR"
    except:
        temp_str = "T:ERR"
        
    try:
        pressure_str = f"P:{pressure_val:.1f}hPa" if pressure_val != 'ERR' and pressure_val is not None else "P:ERR"
    except:
        pressure_str = "P:ERR"
        
    try:
        rad_str = f"RAD:{usv_h_val:.3f}µSv/h" if usv_h_val != 'ERR' and usv_h_val is not None else "RAD:ERR"
    except:
        rad_str = "RAD:ERR"
    
    battery_status = "PWR:LOW" if battery_low else "PWR:OK"
    
    try:
        status_line = (
            f"[{timestamp_str}] " +
            f"LOC:{location} | " +
            f"CO₂:{co2_val} | " +
            f"{temp_str} | " +
            f"{pressure_str} | " +
            f"{rad_str} | " +
            f"{battery_status}"
        )
    except Exception as e:
        print(f"⚠️ Console status error: {e}")
        status_line = f"[{timestamp_str}] STATUS:ERROR - Check sensor data"
    
    return status_line

# For backward compatibility
def get_enhanced_console_status_with_gps_time_safe(sensor_data):
    """Legacy function name for backward compatibility"""
    return get_enhanced_console_status(sensor_data)

def display_gps_navigation_status(sensor_data):
    """Display GPS navigation status"""
    print("\n🧭 GPS NAVIGATION STATUS")
    print("=" * 50)
    
    gps_available = sensor_data.get('gps_available', False)
    current_location = sensor_data.get('current_location', 'UNKNOWN')
    
    if gps_available:
        gps_satellites = sensor_data.get('gps_satellites', 0)
        gps_fix = sensor_data.get('gps_has_fix', False)
        
        print(f"GPS Hardware: AVAILABLE")
        print(f"GPS Fix: {'YES' if gps_fix else 'NO'}")
        print(f"Satellites: {gps_satellites}")
        print(f"Location: {current_location}")
    else:
        print(f"GPS Hardware: NOT AVAILABLE")
        print(f"Using fallback location detection")
        print(f"Location: {current_location}")
    
    print("✅ GPS status complete!")

def display_temperature_fusion_status(sensor_data):
    """Display temperature fusion status"""
    print("\n🌡️ TEMPERATURE FUSION STATUS")
    print("=" * 50)
    
    fused_temp = sensor_data.get('temperature_fused', None)
    temp_source = sensor_data.get('temperature_source', 'UNKNOWN')
    active_sensors = sensor_data.get('active_temperature_sensors', 0)
    
    print(f"Fused Temperature: {fused_temp:.1f}°C" if fused_temp is not None else "Fused Temperature: ERROR")
    print(f"Temperature Source: {temp_source}")
    print(f"Active Sensors: {active_sensors}/2")
    
    print("✅ Temperature fusion status complete!")

# Simple test function
def test_display_with_fixed_spinner():
    """Test the display manager with FIXED triangle spinner (no flicker)"""
    print("🔺 Testing DisplayManager with FIXED Triangle Spinner")
    
    display_manager = DisplayManager()
    
    if not display_manager.initialize_display():
        print("❌ Display initialization failed")
        return
    
    # Test data
    test_sensor_data = {
        'co2': 420,
        'voc': 15,
        'temperature': 22.5,
        'humidity': 45.0,
        'lux': 1500,
        'pressure_hpa': 1013.2,
        'cpm': 25,
        'usv_h': 0.125,
        'radiation_ready': True,
        'battery_low': False,
        'cpu_usage': 35.0,
        'memory_usage': 60.0,
        'current_location': 'OUTDOOR',
        'location_confidence': 85,
        'gps_available': True,
        'gps_satellites': 8,
        'gps_time': '14:30:25',
        'temperature_fused': 22.3,
        'temperature_source': 'FUSED',
        'active_temperature_sensors': 2
    }
    
    print("✅ Display manager initialized with FIXED triangle spinner")
    print("🔺 Triangle spinner will appear in top-left corner (no flicker!)")
    print("🔄 Cycling through all screens...")
    print("⚡ Spinner updates independently - screen won't rebuild constantly")
    
    try:
        start_time = time.monotonic()
        while time.monotonic() - start_time < 60:  # Run for 1 minute
            display_manager.update_display(test_sensor_data)
            time.sleep(0.05)  # Faster update rate to test spinner smoothness
            
    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    
    print("✅ FIXED Triangle spinner test complete!")
    print("🔺 Screen should NOT have been flickering/blinking")
    print("⚡ Triangle should have been smoothly rotating without screen rebuilds")

if __name__ == "__main__":
    test_display_with_fixed_spinner()
