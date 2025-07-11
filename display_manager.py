"""
AI Field Analyzer v2.6 - Optimized Weather Display with Consolidated Forecasting
-------------------------------------------------------------------------------
Enhanced triangle spinner with comprehensive weather monitoring display.
Consolidated weather information into 2 efficient screens.

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
SCREEN_DURATION = 15        # 15 seconds per screen
SCROLL_SPEED = 2           # Pixels per scroll frame
SCROLL_FPS = 15            # Scroll animation FPS
DATA_UPDATE_RATE = 3       # Screen data update interval
SCROLL_REFRESH = 1.0 / SCROLL_FPS

class TriangleSpinner:
    """Triangle activity spinner for display corner - Independent updates"""
    
    def __init__(self, x=5, y=5):
        self.x = x
        self.y = y
        self.size = 5
        self.color = 0x888888
        self.frame = 0
        self.speed = 0.4
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

class DisplayManager:
    """Optimized display manager with consolidated weather monitoring"""
    
    def __init__(self):
        # Display hardware
        self.display = None
        
        # Optimized screen management (10 screens total: 2 weather instead of 4)
        self.current_screen = 0
        self.screens_total = 10
        self.screen_names = [
            "CO2 & VOC", "TEMP & HUMIDITY", "LIGHT & UV", "WEATHER STATUS", 
            "WEATHER FORECAST", "RADIATION", "SYSTEM", "SUMMARY", 
            "GPS DATA", "NAVIGATION"
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
        
        # Triangle spinner
        self.triangle_spinner = TriangleSpinner(x=5, y=6)
        self.spinner_enabled = True
        
        print("🖥️ Optimized Weather Display Manager initialized")
        print("🌦️ Consolidated weather forecasting with 2 efficient screens")
    
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
            print("✅ Optimized weather display ready!")
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

    def get_weather_warnings(self, sensor_data):
        """Generate comprehensive weather warnings with enhanced details"""
        warnings = []
        
        # Get weather forecast data
        weather_forecast = sensor_data.get('weather_forecast', {})
        storm_probability = weather_forecast.get('storm_probability', 0)
        confidence = weather_forecast.get('confidence', 0)
        storm_type = weather_forecast.get('storm_type', 'UNKNOWN')
        arrival_timing = weather_forecast.get('arrival_timing', 'N/A')
        
        # Enhanced storm warnings with timing
        if storm_probability >= 80:
            if arrival_timing != 'N/A':
                warnings.append(f"⚠️ SEVERE STORM ALERT: {storm_probability}% probability - arriving in {arrival_timing}")
            else:
                warnings.append(f"⚠️ SEVERE STORM ALERT: {storm_probability}% probability - imminent threat")
        elif storm_probability >= 60:
            if arrival_timing != 'N/A':
                warnings.append(f"🌩️ STORM WARNING: {storm_probability}% chance - expect weather in {arrival_timing}")
            else:
                warnings.append(f"🌩️ STORM WARNING: {storm_probability}% chance - conditions deteriorating")
        elif storm_probability >= 30:
            warnings.append(f"🌤️ WEATHER CHANGE: {storm_probability}% chance - monitor conditions")
        
        # Atmospheric pressure warnings
        pressure_val = sensor_data.get('pressure_hpa', 1013.25)
        pressure_trend = weather_forecast.get('trends', {}).get('pressure_hpa_per_hour', 0)
        
        if pressure_trend < -2.0:
            warnings.append(f"📉 RAPID PRESSURE DROP: {pressure_trend:.1f} hPa/h - storm system approaching")
        elif pressure_val < 1000:
            warnings.append(f"🔻 LOW PRESSURE: {pressure_val:.1f} hPa - unstable weather likely")
        elif pressure_val < 1005:
            warnings.append(f"📊 FALLING PRESSURE: {pressure_val:.1f} hPa - weather change possible")
        
        # Visibility and fog warnings
        lux_val = sensor_data.get('lux', 1000)
        humidity_val = sensor_data.get('humidity', 50)
        temp_val = sensor_data.get('temperature', 20)
        
        # Enhanced fog detection
        if humidity_val > 90 and lux_val < 1000:
            dew_point_approx = temp_val - ((100 - humidity_val) / 5)
            if abs(temp_val - dew_point_approx) < 2:
                warnings.append(f"🌫️ FOG CONDITIONS: Visibility reduced - dewpoint {dew_point_approx:.1f}°C")
        elif humidity_val > 85 and lux_val < 5000:
            warnings.append(f"☁️ LOW VISIBILITY: {humidity_val:.0f}% humidity - fog risk increasing")
        
        # Temperature trend warnings
        temp_trend = weather_forecast.get('trends', {}).get('temp_c_per_hour', 0)
        if temp_trend < -2.0:
            warnings.append(f"🌡️ RAPID COOLING: {temp_trend:.1f}°C/h - cold front approaching")
        elif temp_trend > 2.0:
            warnings.append(f"🌡️ RAPID WARMING: {temp_trend:.1f}°C/h - thermal instability")
        
        # Radiation + weather interaction
        usv_h = sensor_data.get('usv_h', 0)
        if storm_probability > 50 and usv_h > 0.3:
            warnings.append(f"☢️ RADIATION + STORM: {usv_h:.3f} µSv/h - seek indoor shelter immediately")
        
        # Default message if no warnings
        if not warnings:
            if confidence > 70:
                warnings.append(f"✅ STABLE CONDITIONS: {confidence}% confidence - weather monitoring active")
            else:
                warnings.append(f"📡 WEATHER MONITORING: Building forecast confidence ({confidence}%)")
        
        return warnings
    
    def get_storm_confidence_display(self, confidence):
        """Get storm confidence display with visual indicator"""
        if confidence >= 90:
            return f"CONF:{confidence}% ████", 0xFFFFFF
        elif confidence >= 70:
            return f"CONF:{confidence}% ███░", 0xCCCCCC
        elif confidence >= 50:
            return f"CONF:{confidence}% ██░░", 0xAAAAA
        elif confidence >= 30:
            return f"CONF:{confidence}% █░░░", 0x888888
        else:
            return f"CONF:{confidence}% ░░░░", 0x666666

    def build_screen(self, screen_num, sensor_data, gps_timestamp_str, gps_time_available):
        """Build screen with optimized weather monitoring features"""
        if self.display and self.display.root_group:
            try:
                self.display.root_group = displayio.Group()
            except Exception as e:
                print(f"Warning: Could not clear display group: {e}")
        
        splash = displayio.Group()
        self.scroll_offsets[screen_num] = 0
        
        # Get weather forecast data
        weather_forecast = sensor_data.get('weather_forecast', {})
        
        try:
            if screen_num == 0:  # CO2 & VOC
                splash.append(self.create_text_line("CO2 & VOC", 6, 0xFFFFFF))
                co2_val = sensor_data.get('co2', 'ERR')
                voc_val = sensor_data.get('voc', 'ERR')
                splash.append(self.create_text_line(f"CO2:{co2_val}ppm", 18, 0xCCCCCC, False))
                splash.append(self.create_text_line(f"VOC:{voc_val}ppb", 28, 0xCCCCCC, False))
                
                # Enhanced CO2 warning with weather context
                if co2_val != 'ERR' and isinstance(co2_val, (int, float)):
                    if co2_val >= 2000:
                        warning_msg = f"CO2 DANGER: {co2_val}ppm - Ventilate immediately"
                        warning_color = 0x666666
                    elif co2_val >= 1000:
                        warning_msg = f"CO2 CAUTION: {co2_val}ppm - Check weather before opening windows"
                        warning_color = 0xAAAAA
                    else:
                        storm_prob = weather_forecast.get('storm_probability', 0)
                        if storm_prob > 60:
                            warning_msg = f"CO2 OK: {co2_val}ppm - Storm approaching, monitor ventilation"
                            warning_color = 0xCCCCCC
                        else:
                            warning_msg = f"CO2 NORMAL: {co2_val}ppm - Air quality good"
                            warning_color = 0xFFFFFF
                else:
                    warning_msg = "CO2 sensor error - check connections"
                    warning_color = 0x666666
                
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
                
                # Enhanced temperature trend display
                temp_trend = weather_forecast.get('trends', {}).get('temp_c_per_hour', 0)
                if temp_trend != 0:
                    trend_symbol = "↑" if temp_trend > 0 else "↓"
                    splash.append(self.create_text_line(f"TREND:{trend_symbol}{abs(temp_trend):.1f}C/h", 36, 0xAAAAA, False))
                else:
                    source_short = temp_source[:6] if temp_source != "UNKNOWN" else "UNK"
                    active_sensors = active_sensors if active_sensors is not None else 0
                    splash.append(self.create_text_line(f"SRC:{source_short} ({active_sensors}/2)", 36, 0xAAAAA, False))
                
                # Weather-aware temperature warning
                if humidity_val != 'ERR' and humidity_val > 85 and fused_temp is not None:
                    dew_point = fused_temp - ((100 - humidity_val) / 5)
                    warning_msg = f"FOG RISK: Dewpoint {dew_point:.1f}°C - visibility may reduce"
                    warning_color = 0xAAAAA
                else:
                    warning_msg = "Temperature and humidity monitoring active"
                    warning_color = 0xFFFFFF
                
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
                
                # Enhanced light analysis with weather context
                if lux_val not in ['ERR', None] and isinstance(lux_val, (int, float)):
                    if lux_val < 200: 
                        condition = "LOW"
                        warning_msg = f"LOW LIGHT: {lux_val:.0f} lux - possible storm clouds or fog"
                        warning_color = 0xAAAAA
                    elif lux_val < 1000: 
                        condition = "MOD"
                        storm_prob = weather_forecast.get('storm_probability', 0)
                        if storm_prob > 40:
                            warning_msg = f"CLOUDY: {lux_val:.0f} lux - storm clouds building ({storm_prob}%)"
                            warning_color = 0xAAAAA
                        else:
                            warning_msg = f"MODERATE LIGHT: {lux_val:.0f} lux - normal conditions"
                            warning_color = 0xFFFFFF
                    elif lux_val < 10000: 
                        condition = "BRIGHT"
                        warning_msg = f"BRIGHT CONDITIONS: {lux_val:.0f} lux - good visibility"
                        warning_color = 0xFFFFFF
                    else: 
                        condition = "INTENSE"
                        warning_msg = f"INTENSE LIGHT: {lux_val/1000:.1f}k lux - UV protection recommended"
                        warning_color = 0xCCCCCC
                else:
                    condition = "ERROR"
                    warning_msg = "Light sensor error - check connections"
                    warning_color = 0x666666
                
                splash.append(self.create_text_line(f"LEVEL:{condition}", 28, 0xAAAAA, False))
                
            elif screen_num == 3:  # CONSOLIDATED WEATHER STATUS
                splash.append(self.create_text_line("WEATHER STATUS", 6, 0xFFFFFF))
                
                current_location = sensor_data.get('current_location', 'UNKNOWN')
                if current_location == "OUTDOOR":
                    # Line 1: Pressure and Storm Probability
                    pressure_val = sensor_data.get('pressure_hpa', 'ERR')
                    storm_prob = weather_forecast.get('storm_probability', 0)
                    
                    if pressure_val != 'ERR' and pressure_val is not None:
                        try:
                            storm_color = 0x666666 if storm_prob >= 70 else 0xAAAAA if storm_prob >= 40 else 0xFFFFFF
                            splash.append(self.create_text_line(f"P:{pressure_val:.1f}hPa S:{storm_prob}%", 16, storm_color, False))
                        except (ValueError, TypeError):
                            splash.append(self.create_text_line("P:ERR S:ERR", 16, 0x666666, False))
                    else:
                        splash.append(self.create_text_line("P:ERROR S:ERROR", 16, 0x666666, False))
                    
                    # Line 2: Confidence and Fog Risk
                    confidence = weather_forecast.get('confidence', 0)
                    humidity_val = sensor_data.get('humidity', 50)
                    temp_val = sensor_data.get('temperature', 20)
                    
                    # Calculate fog risk
                    fog_risk = "LOW"
                    if humidity_val > 85 and temp_val is not None:
                        dew_point = temp_val - ((100 - humidity_val) / 5)
                        dew_diff = abs(temp_val - dew_point)
                        if dew_diff < 1.0 and humidity_val > 90:
                            fog_risk = "HIGH"
                        elif dew_diff < 2.0 and humidity_val > 85:
                            fog_risk = "MED"
                    
                    conf_color = 0xFFFFFF if confidence >= 70 else 0xAAAAA
                    fog_color = 0x666666 if fog_risk == "HIGH" else 0xAAAAA if fog_risk == "MED" else 0xCCCCCC
                    splash.append(self.create_text_line(f"CONF:{confidence}% FOG:{fog_risk}", 26, conf_color, False))
                    
                    # Line 3: Atmospheric Trends
                    trends = weather_forecast.get('trends', {})
                    pressure_trend = trends.get('pressure_hpa_per_hour', 0)
                    temp_trend = trends.get('temp_c_per_hour', 0)
                    
                    p_symbol = "↓" if pressure_trend < -0.5 else "↑" if pressure_trend > 0.5 else "→"
                    t_symbol = "↑" if temp_trend > 0.5 else "↓" if temp_trend < -0.5 else "→"
                    trend_color = 0x666666 if abs(pressure_trend) > 1.5 or abs(temp_trend) > 1.5 else 0xAAAAA
                    
                    splash.append(self.create_text_line(f"P{p_symbol}{abs(pressure_trend):.1f} T{t_symbol}{abs(temp_trend):.1f}/h", 36, trend_color, False))
                    
                    # Generate comprehensive warning message
                    warnings = self.get_weather_warnings(sensor_data)
                    warning_msg = warnings[0] if warnings else "Weather monitoring active"
                    warning_color = 0xFFFFFF
                    
                else:
                    splash.append(self.create_text_line(f"LOCATION:{current_location}", 18, 0x888888, False))
                    splash.append(self.create_text_line("Weather monitoring", 28, 0x888888, False))
                    splash.append(self.create_text_line("paused indoors", 38, 0x888888, False))
                    warning_msg = f"Weather monitoring paused - {current_location.lower()} environment"
                    warning_color = 0x888888
                
            elif screen_num == 4:  # CONSOLIDATED WEATHER FORECAST
                splash.append(self.create_text_line("WEATHER FORECAST", 6, 0xFFFFFF))
                
                storm_prob = weather_forecast.get('storm_probability', 0)
                storm_type = weather_forecast.get('storm_type', 'UNKNOWN')
                arrival_timing = weather_forecast.get('arrival_timing', 'N/A')
                confidence = weather_forecast.get('confidence', 0)
                
                # Line 1: Storm Type and Probability
                type_short = storm_type.replace('_', ' ')[:8]
                prob_color = 0x666666 if storm_prob >= 70 else 0xAAAAA if storm_prob >= 40 else 0xFFFFFF
                splash.append(self.create_text_line(f"{type_short} {storm_prob}%", 16, prob_color, False))
                
                # Line 2: Arrival Timing or Method
                if arrival_timing != 'N/A':
                    timing_color = 0x666666 if storm_prob >= 70 else 0xAAAAA
                    splash.append(self.create_text_line(f"ETA: {arrival_timing}", 26, timing_color, False))
                else:
                    method = weather_forecast.get('method', 'UNKNOWN')
                    splash.append(self.create_text_line(f"METHOD: {method[:8]}", 26, 0x888888, False))
                
                # Line 3: Confidence Bar and Visibility
                lux_val = sensor_data.get('lux', 1000)
                humidity_val = sensor_data.get('humidity', 50)
                
                # Confidence bar
                conf_bars = "████" if confidence >= 90 else "███░" if confidence >= 70 else "██░░" if confidence >= 50 else "█░░░" if confidence >= 30 else "░░░░"
                
                # Visibility status
                vis_status = "CLEAR"
                if lux_val < 1000 and humidity_val > 85:
                    vis_status = "POOR"
                elif lux_val < 5000 or humidity_val > 75:
                    vis_status = "FAIR"
                
                vis_color = 0x666666 if vis_status == "POOR" else 0xAAAAA if vis_status == "FAIR" else 0xFFFFFF
                splash.append(self.create_text_line(f"{conf_bars} VIS:{vis_status}", 36, vis_color, False))
                
                # Enhanced forecast warning
                if storm_prob >= 80:
                    if arrival_timing != 'N/A':
                        warning_msg = f"SEVERE STORM ALERT: {storm_prob}% probability - arriving in {arrival_timing}"
                    else:
                        warning_msg = f"SEVERE STORM ALERT: {storm_prob}% - take immediate precautions"
                    warning_color = 0x666666
                elif storm_prob >= 60:
                    if arrival_timing != 'N/A':
                        warning_msg = f"STORM WARNING: {storm_prob}% chance - prepare for weather in {arrival_timing}"
                    else:
                        warning_msg = f"STORM WARNING: {storm_prob}% chance - conditions deteriorating"
                    warning_color = 0xAAAAA
                elif storm_prob >= 30:
                    warning_msg = f"WEATHER CHANGE: {storm_prob}% chance - monitor atmospheric conditions"
                    warning_color = 0xCCCCCC
                else:
                    warning_msg = f"STABLE CONDITIONS: {storm_prob}% storm chance - weather looks good"
                    warning_color = 0xFFFFFF
                
            elif screen_num == 5:  # Radiation
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
                
                # Enhanced radiation warning with weather context
                storm_prob = weather_forecast.get('storm_probability', 0)
                if rad_ready and isinstance(usv_val, (int, float)):
                    if usv_val >= 0.5:
                        if storm_prob > 50:
                            warning_msg = f"RADIATION ALERT: {usv_val:.3f} µSv/h + {storm_prob}% storm risk - seek indoor shelter"
                            warning_color = 0x666666
                        else:
                            warning_msg = f"RADIATION ELEVATED: {usv_val:.3f} µSv/h - limit outdoor exposure"
                            warning_color = 0xAAAAA
                    elif usv_val >= 0.3:
                        warning_msg = f"RADIATION MODERATE: {usv_val:.3f} µSv/h - monitor exposure time"
                        warning_color = 0xCCCCCC
                    else:
                        warning_msg = f"RADIATION NORMAL: {usv_val:.3f} µSv/h - levels safe for outdoor activity"
                        warning_color = 0xFFFFFF
                else:
                    warning_msg = "Radiation sensor warming up - readings will be available shortly"
                    warning_color = 0x888888
                
            elif screen_num == 6:  # System
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
                
                # Weather system status
                weather_method = weather_forecast.get('method', 'UNKNOWN')
                weather_confidence = weather_forecast.get('confidence', 0)
                splash.append(self.create_text_line(f"WX:{weather_method[:6]} {weather_confidence}%", 38, 0xAAAAA, False))
                
                warning_msg = f"System monitoring - {current_location} mode, weather forecasting active"
                warning_color = 0xFFFFFF
                
            elif screen_num == 7:  # Summary
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
                
                # Weather summary
                storm_prob = weather_forecast.get('storm_probability', 0)
                pressure_val = sensor_data.get('pressure_hpa', 'ERR')
                if pressure_val != 'ERR':
                    try:
                        splash.append(self.create_text_line(f"WX:{storm_prob}% P:{pressure_val:.0f}", 35, 0xCCCCCC, False))
                    except (ValueError, TypeError):
                        splash.append(self.create_text_line(f"WX:{storm_prob}% P:ERR", 35, 0x666666, False))
                else:
                    splash.append(self.create_text_line(f"WX:{storm_prob}% P:ERR", 35, 0x666666, False))
                
                # Enhanced summary warning
                if storm_prob >= 70:
                    warning_msg = f"SYSTEM SUMMARY: Storm {storm_prob}% - all sensors monitoring severe weather approach"
                    warning_color = 0x666666
                elif storm_prob >= 40:
                    warning_msg = f"SYSTEM SUMMARY: Weather change {storm_prob}% - monitoring atmospheric conditions"
                    warning_color = 0xAAAAA
                else:
                    warning_msg = f"SYSTEM SUMMARY: All sensors active - stable conditions, routine monitoring"
                    warning_color = 0xFFFFFF
                
            elif screen_num == 8:  # GPS Data
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
                    
                    storm_prob = weather_forecast.get('storm_probability', 0)
                    if storm_prob > 60:
                        warning_msg = f"GPS active - {gps_satellites} satellites, storm {storm_prob}% - plan shelter route"
                        warning_color = 0xAAAAA
                    else:
                        warning_msg = f"GPS active - {gps_satellites} satellites, weather stable"
                        warning_color = 0xFFFFFF
                else:
                    splash.append(self.create_text_line("GPS:OFFLINE", 18, 0x666666, False))
                    splash.append(self.create_text_line("Hardware not", 28, 0x666666, False))
                    splash.append(self.create_text_line("available", 38, 0x666666, False))
                    warning_msg = "GPS hardware not available - using sensor fallback for location detection"
                    warning_color = 0x666666
                
            elif screen_num == 9:  # Navigation
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
                
                # Weather-aware navigation warning
                storm_prob = weather_forecast.get('storm_probability', 0)
                arrival_timing = weather_forecast.get('arrival_timing', 'N/A')
                
                if storm_prob >= 70:
                    if arrival_timing != 'N/A':
                        warning_msg = f"NAVIGATION ALERT: Severe weather in {arrival_timing} - seek immediate shelter"
                        warning_color = 0x666666
                    else:
                        warning_msg = f"NAVIGATION ALERT: {storm_prob}% storm probability - avoid outdoor travel"
                        warning_color = 0x666666
                elif storm_prob >= 40:
                    if arrival_timing != 'N/A':
                        warning_msg = f"TRAVEL ADVISORY: Weather change in {arrival_timing} - plan accordingly"
                        warning_color = 0xAAAAA
                    else:
                        warning_msg = f"NAVIGATION: {storm_prob}% weather change - monitor conditions closely"
                        warning_color = 0xAAAAA
                else:
                    warning_msg = f"Navigation system active - {current_location} mode, stable weather conditions"
                    warning_color = 0xFFFFFF
            
            # ADD TRIANGLE SPINNER TO EVERY SCREEN
            if self.spinner_enabled:
                spinner_element = self.triangle_spinner.create_element()
                if spinner_element:
                    splash.append(spinner_element)
            
            # Add enhanced scrolling warning message
            self.current_scroll_group, self.current_scroll_area = self.create_scrolling_text(warning_msg, 49, warning_color)
            splash.append(self.current_scroll_group)
            
            # Add enhanced timestamp with weather status
            location_indicator = sensor_data.get('current_location', 'UNK')[:3]
            temp_source_indicator = sensor_data.get('temperature_source', 'UNK')[:1]
            gps_indicator = "G" if gps_time_available else "S"
            weather_indicator = f"W{weather_forecast.get('storm_probability', 0)}"
            enhanced_timestamp = f"{gps_timestamp_str} {location_indicator} T{temp_source_indicator} {gps_indicator} {weather_indicator}"
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
        """Main display update function with optimized weather monitoring"""
        if not self.display:
            return
            
        current_time = time.monotonic()
        display_updated = False
        
        # UPDATE TRIANGLE SPINNER IN-PLACE (No screen rebuild!)
        if self.spinner_enabled and self.current_splash:
            try:
                spinner_updated = self.triangle_spinner.update_in_place(self.current_splash)
            except Exception as e:
                print(f"⚠️ Spinner update error: {e}")
        
        # Get GPS time or fallback to system time
        gps_timestamp_str, gps_time_available = self.get_gps_time_or_fallback(sensor_data)
        
        # Enhance sensor data with temperature fusion and weather forecast
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
                self.build_screen(self.current_screen, enhanced_sensor_data, gps_timestamp_str, gps_time_available)
                display_updated = True
            except Exception as e:
                print(f"❌ Error updating display: {e}")
                return
        
        # Update scrolling text
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
    
    def _enhance_sensor_data_with_fusion(self, sensor_data):
        """Enhanced sensor data with temperature fusion and mock weather forecast"""
        enhanced_data = sensor_data.copy()
        
        # Temperature fusion (existing logic)
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
        elif bmp390_temp is not None:
            fused_temp = bmp390_temp
            temp_source = "BMP390"
        elif scd41_temp is not None and scd41_in_range:
            fused_temp = scd41_temp
            temp_source = "SCD41"
        else:
            fused_temp = None
            temp_source = "FAILED"
        
        enhanced_data['temperature_fused'] = fused_temp
        enhanced_data['temperature_source'] = temp_source
        enhanced_data['active_temperature_sensors'] = active_sensors
        
        # Generate mock weather forecast if not present
        if 'weather_forecast' not in enhanced_data:
            enhanced_data['weather_forecast'] = self._generate_mock_weather_forecast(enhanced_data)
        
        return enhanced_data
    
    def _generate_mock_weather_forecast(self, sensor_data):
        """Generate realistic mock weather forecast for demonstration"""
        pressure = sensor_data.get('pressure_hpa', 1013.25)
        humidity = sensor_data.get('humidity', 50)
        temp = sensor_data.get('temperature', 20)
        lux = sensor_data.get('lux', 1000)
        
        # Simple weather prediction algorithm
        storm_probability = 0
        confidence = 85
        
        # Pressure-based prediction
        if pressure < 1005:
            storm_probability += 40
        elif pressure < 1010:
            storm_probability += 20
        
        # Humidity factor
        if humidity > 85:
            storm_probability += 30
        elif humidity > 75:
            storm_probability += 15
        
        # Light factor (daytime only)
        current_hour = time.localtime().tm_hour
        if 6 <= current_hour <= 18:  # Daytime
            if lux < 5000:
                storm_probability += 25
            elif lux < 15000:
                storm_probability += 10
        
        # Cap at 100%
        storm_probability = min(100, storm_probability)
        
        # Determine storm type and timing
        if storm_probability >= 80:
            storm_type = "SEVERE_STORM"
            arrival_timing = "1-3 hours"
        elif storm_probability >= 60:
            storm_type = "STORM_LIKELY"
            arrival_timing = "2-6 hours"
        elif storm_probability >= 30:
            storm_type = "WEATHER_CHANGE"
            arrival_timing = "4-12 hours"
        else:
            storm_type = "STABLE"
            arrival_timing = "N/A"
        
        # Generate trends
        trends = {
            'pressure_hpa_per_hour': (1013.25 - pressure) * 0.5,  # Mock trend
            'temp_c_per_hour': 0.2 if storm_probability > 50 else -0.1,
            'humidity_pct_per_hour': 2.0 if storm_probability > 40 else 0.5,
            'light_change_factor': -0.3 if storm_probability > 60 else 0.1
        }
        
        return {
            'storm_probability': storm_probability,
            'confidence': confidence,
            'storm_type': storm_type,
            'arrival_timing': arrival_timing,
            'method': 'SENSOR_FUSION',
            'trends': trends,
            'accuracy_estimate': f"{88 + (confidence * 0.12):.0f}%"
        }
    
    def display_startup_screen(self):
        """Optimized startup screen with weather capabilities"""
        if not self.display:
            return
            
        splash = displayio.Group()
        self.display.root_group = splash
        
        splash.append(self.create_text_line("AI FIELD", 8, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("ANALYZER", 20, 0xFFFFFF, True, 1))
        splash.append(self.create_text_line("v2.6 OPTIMIZED", 32, 0x888888))
        splash.append(self.create_text_line("2-Screen Weather", 44, 0x666666))
        
        # Add triangle spinner to startup screen
        if self.spinner_enabled:
            spinner_element = self.triangle_spinner.create_element()
            if spinner_element:
                splash.append(spinner_element)
        
        time.sleep(3)

def test_optimized_weather_display():
    """Test the optimized weather display system"""
    print("🌦️ Testing Optimized Weather Display Manager")
    print("=" * 50)
    
    display_manager = DisplayManager()
    
    if not display_manager.initialize_display():
        print("❌ Display initialization failed")
        return
    
    # Enhanced test data with weather forecast
    test_sensor_data = {
        'co2': 420,
        'voc': 15,
        'temperature': 22.5,
        'humidity': 78.0,  # Higher humidity for fog demo
        'lux': 8000,       # Moderate light for weather demo
        'pressure_hpa': 1008.2,  # Lower pressure for storm demo
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
        'active_temperature_sensors': 2,
        'weather_forecast': {
            'storm_probability': 65,
            'confidence': 92,
            'storm_type': 'STORM_LIKELY',
            'arrival_timing': '3-5 hours',
            'method': 'SENSOR_FUSION',
            'trends': {
                'pressure_hpa_per_hour': -1.5,
                'temp_c_per_hour': -0.8,
                'humidity_pct_per_hour': 4.2,
                'light_change_factor': -0.4
            },
            'accuracy_estimate': '95%'
        }
    }
    
    print("✅ Optimized Weather Display Manager initialized")
    print("🌦️ Consolidated weather features:")
    print("   - WEATHER STATUS: Pressure, storms, fog, trends")
    print("   - WEATHER FORECAST: Type, timing, confidence, visibility")
    print("   - Atmospheric trend analysis")
    print("   - Fog and visibility warnings")
    print("   - Weather-aware radiation alerts")
    print("   - Storm arrival timing predictions")
    print("\n🔺 Triangle spinner active (no flicker)")
    print("🔄 Cycling through 10 optimized screens...")
    print("⏰ 15 seconds per screen")
    
    try:
        start_time = time.monotonic()
        screen_demo_time = 0
        
        while time.monotonic() - start_time < 150:  # Run for 2.5 minutes
            current_time = time.monotonic()
            
            # Simulate changing weather conditions
            if current_time - screen_demo_time > 30:  # Change conditions every 30 seconds
                # Simulate storm approaching
                test_sensor_data['weather_forecast']['storm_probability'] = min(95, 
                    test_sensor_data['weather_forecast']['storm_probability'] + 5)
                test_sensor_data['pressure_hpa'] = max(995, 
                    test_sensor_data['pressure_hpa'] - 1.5)
                test_sensor_data['humidity'] = min(95, 
                    test_sensor_data['humidity'] + 2)
                test_sensor_data['lux'] = max(2000, 
                    test_sensor_data['lux'] - 1000)
                
                # Fixed f-string syntax
                print(f"🌩️ Simulated conditions: Storm {test_sensor_data['weather_forecast']['storm_probability']}%, Pressure {test_sensor_data['pressure_hpa']:.1f} hPa")
                screen_demo_time = current_time
            
            display_manager.update_display(test_sensor_data)
            time.sleep(0.05)  # Smooth updates
            
    except KeyboardInterrupt:
        print("\n🛑 Optimized weather display test stopped by user")
    
    print("\n✅ Optimized Weather Display Test Complete!")
    print("🌦️ Features demonstrated:")
    print("   ✓ Consolidated 2-screen weather monitoring")
    print("   ✓ Pressure, storm probability, and confidence")
    print("   ✓ Atmospheric trends and fog risk assessment")
    print("   ✓ Weather-aware alerts and timing")
    print("   ✓ Visibility status and navigation warnings")
    print("   ✓ Efficient information density")
    print("   ✓ No screen flicker with triangle spinner")

if __name__ == "__main__":
    test_optimized_weather_display()
