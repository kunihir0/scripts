#!/usr/bin/env python3

import sys
import time
import math
import random
import shutil # For shutil.get_terminal_size()
from typing import List, Dict, Tuple, Optional, Set, Any, Callable

# == Visual Design System ==

# === Color Palette Specification ===
# Terminal Colors (ANSI Escape Codes)
COLORS: Dict[str, str] = {
    "pink": "\033[38;5;219m",
    "purple": "\033[38;5;183m",
    "cyan": "\033[38;5;123m",
    "yellow": "\033[38;5;228m",
    "blue": "\033[38;5;111m",
    "orange": "\033[38;5;216m",
    "green": "\033[38;5;156m",
    "red": "\033[38;5;210m",
    "magenta": "\033[38;5;201m",
    "light_blue": "\033[38;5;159m",
    "lavender": "\033[38;5;147m",
    "peach": "\033[38;5;223m",
    "mint": "\033[38;5;121m",
    "reset": "\033[0m",
    "black_bg": "\033[40m",
    "purple_bg": "\033[45m",
    "cyan_bg": "\033[46m",
    "pink_bg": "\033[48;5;219m",
    "dark_bg": "\033[48;5;236m",
}

# Text Styling
STYLES: Dict[str, str] = {
    "bold": "\033[1m",
    "italic": "\033[3m",  # Terminal support varies
    "underline": "\033[4m",
    "blink": "\033[5m",  # Terminal support varies
    "reset_style": "\033[22m\033[23m\033[24m\033[25m", # Resets bold, italic, underline, blink
}

# === Icon System & Special Characters ===

# Spinner Character Sets
SPINNER_SETS: Dict[str, List[str]] = {
    "flower": ["✿", "❀", "✾", "❁", "✽", "✼", "✻", "✺", "✹", "✸"],
    "star": ["✦", "✧", "✩", "✪", "✫", "✬", "✭", "✮"],
    "braille": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "arrows": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    "pulse": ["•", "○", "●", "○"],
    "bounce": ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"],
}

# Effect & Particle Characters
EFFECT_CHARS: Dict[str, List[str]] = {
    "sparkles": ["✨", "✧", "✦", "⋆", "✩", "✫", "✬", "✭", "✮", "✯", "★", "*"],
    "bubbles": ["○", "◌", "◍", "◎", "●", "◉"],
    "progress_indicators": ["•", "·"],
}

# Status Symbol System
STATUS_SYMBOLS: Dict[str, Tuple[str, str]] = {
    "success": ("✓", "green"),
    "warning": ("!", "yellow"),
    "error": ("✗", "red"),
    "info": ("✧", "cyan"),
    "progress": ("→", "blue"),
    "star": ("★", "purple"),
    "heart": ("♥", "pink"),
    "note": ("•", "lavender"),
}

# Border & Frame Character Sets
FRAME_STYLES: Dict[str, Dict[str, str]] = {
    "single": {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"},
    "double": {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"},
    "bold": {"tl": "┏", "tr": "┓", "bl": "┗", "br": "┛", "h": "━", "v": "┃"},
    "dotted": {"tl": ".", "tr": ".", "bl": ".", "br": ".", "h": ".", "v": "."},
    "ascii": {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"},
    "stars": {"tl": "✦", "tr": "✦", "bl": "✦", "br": "✦", "h": "✧", "v": "✧"},
}
FADE_CHARS: str = " ░▒▓█"

# == Terminal Control Helper Functions ==

def _get_terminal_size() -> Tuple[int, int]:
    """Gets the current terminal size (width, height)."""
    try:
        # shutil.get_terminal_size is the preferred standard library way
        columns, rows = shutil.get_terminal_size(fallback=(80, 24))
        return columns, rows
    except Exception:
        # Fallback if shutil fails (e.g., not a real TTY)
        try:
            # This is a more platform-dependent fallback
            # For Linux/macOS, using stty via subprocess
            import subprocess
            result = subprocess.run(['stty', 'size'], capture_output=True, text=True, check=True)
            rows, columns = map(int, result.stdout.split())
            return columns, rows
        except Exception:
            return 80, 24 # Default fallback

def _hide_cursor() -> None:
    """Hides the terminal cursor."""
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

def _show_cursor() -> None:
    """Shows the terminal cursor."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def _move_cursor(row: int, col: int) -> None:
    """Moves the terminal cursor to the specified row and column (1-indexed)."""
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()

def _clear_screen() -> None:
    """Clears the entire terminal screen."""
    sys.stdout.write("\033[2J")
    _move_cursor(1, 1) # Move cursor to top-left after clearing
    sys.stdout.flush()

def _clear_line() -> None:
    """Clears the current line from the cursor position to the end."""
    sys.stdout.write("\033[K")
    sys.stdout.flush()

def _color_text(
    text: str,
    color_name: Optional[str] = None,
    styles: Optional[List[str]] = None,
    background_name: Optional[str] = None,
) -> str:
    """Applies color and styles to text."""
    prefix = ""
    if color_name and color_name in COLORS:
        prefix += COLORS[color_name]
    if background_name and background_name in COLORS: # Using COLORS dict for bg too
        prefix += COLORS[background_name]
    if styles:
        for style in styles:
            if style in STYLES:
                prefix += STYLES[style]
    
    suffix = COLORS["reset"] + STYLES["reset_style"] if prefix else ""
    return f"{prefix}{text}{suffix}"

# == Animation Techniques & Effects ==

# === Text Animation Methods ===

def _gradient_text(text: str, color_names: Optional[List[str]] = None) -> str:
    """Create a color gradient across text."""
    if not text:
        return ""
    if color_names is None:
        color_names = ["pink", "purple", "cyan", "blue", "magenta"]
    if not color_names: # Fallback if empty list provided
        return text

    gradient_parts: List[str] = []
    text_len = len(text)
    num_colors = len(color_names)

    for i, char in enumerate(text):
        # Calculate color position
        color_idx_float = (i / text_len) * num_colors
        color_idx = int(color_idx_float)
        if color_idx >= num_colors:
            color_idx = num_colors - 1
        
        actual_color_name = color_names[color_idx]
        gradient_parts.append(COLORS.get(actual_color_name, "") + char)
    
    return "".join(gradient_parts) + COLORS["reset"]

def _rainbow_text_animation(text: str, delay: float = 0.05) -> None:
    """Animates text with character-by-character rainbow color cycling."""
    rainbow_colors = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink"]
    color_idx = 0
    _hide_cursor()
    for char_idx, char in enumerate(text):
        color_name = rainbow_colors[color_idx % len(rainbow_colors)]
        sys.stdout.write(COLORS.get(color_name, "") + char + COLORS["reset"])
        sys.stdout.flush()
        time.sleep(delay)
        color_idx += 1
    print() # Newline at the end
    _show_cursor()

def _bubble_effect(text: str, duration: float = 2.0, speed: float = 0.08) -> None:
    """Create bubbling text effect."""
    bubbles = EFFECT_CHARS["bubbles"]
    bubble_colors = ["pink", "purple", "cyan", "yellow", "light_blue", "lavender"]
    
    _hide_cursor()
    term_width, _ = _get_terminal_size()
    
    start_time = time.time()
    # Store (char_index, bubble_char_index, bubble_color_index, vertical_pos)
    active_bubbles: List[Tuple[int, int, int, int]] = [] 

    original_y = _get_terminal_size()[1] // 2 # Approximate starting row
    _move_cursor(original_y, 1)
    print(" " * term_width, end="\r") # Clear line initially

    while time.time() - start_time < duration:
        # Add new bubbles
        if random.random() < 0.3 and len(active_bubbles) < len(text) // 1.5:
            char_index = random.randint(0, len(text) - 1)
            # Avoid adding too many bubbles for the same char index if already active
            if not any(b[0] == char_index for b in active_bubbles):
                active_bubbles.append((
                    char_index, 
                    random.randrange(len(bubbles)), 
                    random.randrange(len(bubble_colors)),
                    0 # Start at relative y=0 (on the text line)
                ))

        # Prepare display string
        display_chars = list(text)
        
        # Update and draw bubbles
        next_active_bubbles = []
        for i in range(len(active_bubbles)):
            char_idx, bubble_char_idx, color_idx, y_offset = active_bubbles[i]
            
            # "Pop" bubble or move it up
            if random.random() < 0.1 or y_offset < -3: # Pop if moved too high or randomly
                pass # Bubble disappears
            else:
                y_offset -= 1 # Move up
                display_chars[char_idx] = _color_text(bubbles[bubble_char_idx], bubble_colors[color_idx])
                next_active_bubbles.append((char_idx, bubble_char_idx, color_idx, y_offset))
        active_bubbles = next_active_bubbles
        
        # Render
        padding = (term_width - len(text)) // 2
        padding_str = " " * max(0, padding)
        
        _move_cursor(original_y, 1) # Go to the text line
        sys.stdout.write(padding_str + "".join(display_chars) + " " * (term_width - len(text) - len(padding_str)) + "\r")
        sys.stdout.flush()
        time.sleep(speed)

    _move_cursor(original_y, 1)
    print(" " * term_width, end="\r") # Clear line finally
    print(padding_str + text) # Print final text
    _show_cursor()


def _wave_text(text: str, cycles: int = 2, speed: float = 0.05, amplitude: int = 2) -> None:
    """Create a sine wave animation of text."""
    if not text: return
    _hide_cursor()
    term_width, term_height = _get_terminal_size()
    text_len = len(text)
    
    base_y = term_height // 2
    base_x = (term_width - text_len) // 2
    
    # Total steps for the animation
    # Each cycle is 2*PI, let's say 20 steps per PI for smoothness
    total_steps = int(cycles * 2 * math.pi * 10) 

    for step in range(total_steps):
        _clear_screen() # Or clear specific lines if performance is an issue
        phase = step / 10.0
        
        for i, char_in_text in enumerate(text):
            # Calculate the sine wave position
            # (i / (text_len / (2 * math.pi))) makes one full wave over the text length
            # Add phase for movement
            wave_offset = int(amplitude * math.sin((i / (text_len / (2*math.pi))) * (cycles/2) + phase)) 
            char_y = base_y + wave_offset
            char_x = base_x + i

            if 0 < char_y <= term_height and 0 < char_x <= term_width:
                _move_cursor(char_y, char_x)
                sys.stdout.write(char_in_text)
        
        sys.stdout.flush()
        time.sleep(speed)
    
    _clear_screen()
    _move_cursor(base_y, base_x)
    print(text)
    _show_cursor()


def _typing_effect(text: str, speed: float = 0.03, variance: float = 0.02) -> None:
    """Simulates typing with realistic timing variations."""
    _hide_cursor()
    for char in text:
        delay = speed + random.uniform(-variance, variance)
        delay = max(0.001, delay) # Ensure minimum delay
        
        if char in ".!?,:;":
            delay *= 3 # Longer pauses for punctuation
            
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print() # Newline at the end
    _show_cursor()


def _exploding_text(text: str, duration: float = 1.5, particle_count_factor: int = 3, speed: float = 0.05) -> None:
    """Create an explosion animation with text characters as particles."""
    _hide_cursor()
    term_width, term_height = _get_terminal_size()
    
    text_center_x = term_width // 2
    text_center_y = term_height // 2

    particles_data: List[Dict[str, Any]] = []
    source_chars = [char for char in text if char.strip()]
    if not source_chars:
        source_chars = list("BOOM!") # Fallback if text is all whitespace

    num_particles = min(100, len(source_chars) * particle_count_factor)

    for _ in range(num_particles):
        char = random.choice(source_chars)
        angle = random.uniform(0, 2 * math.pi)
        velocity = random.uniform(1.0, 3.0) # Initial speed
        color_name = random.choice(["pink", "purple", "cyan", "yellow", "green", "blue", "red", "orange"])
        
        particles_data.append({
            "char": char,
            "x": float(text_center_x + random.uniform(-1,1)), # Start near center
            "y": float(text_center_y + random.uniform(-0.5,0.5)),
            "dx": math.cos(angle) * velocity,
            "dy": math.sin(angle) * velocity * 0.5,  # Vertical motion often appears slower in terminals
            "color": color_name,
            "life": random.uniform(duration * 0.5, duration * 1.2) # How long this particle lives
        })

    start_time = time.time()
    elapsed_time = 0

    while elapsed_time < duration and any(p["life"] > elapsed_time for p in particles_data):
        _clear_screen() # Simple clearing for this effect
        
        for p in particles_data:
            if elapsed_time < p["life"]:
                # Update position
                p["x"] += p["dx"]
                p["y"] += p["dy"]
                
                # Apply some "gravity" or drag
                p["dy"] += 0.1 # Simple gravity
                p["dx"] *= 0.98 # Air resistance
                p["dy"] *= 0.98

                # Draw if on screen
                draw_x, draw_y = int(p["x"]), int(p["y"])
                if 0 < draw_x <= term_width and 0 < draw_y <= term_height:
                    _move_cursor(draw_y, draw_x)
                    sys.stdout.write(_color_text(p["char"], p["color"]))
        
        sys.stdout.flush()
        time.sleep(speed)
        elapsed_time = time.time() - start_time
    
    _clear_screen()
    _show_cursor()


# === Progress & Status Indicators ===

def _countdown(seconds: int, message: str = "Starting in", color_names: Optional[List[str]] = None) -> None:
    """Display a countdown with optional color cycling and simple pulse."""
    if color_names is None:
        color_names = ["pink", "purple", "cyan", "blue", "lavender"]
    if not color_names: color_names = ["cyan"] # Fallback

    _hide_cursor()
    term_width, _ = _get_terminal_size()
    
    for i in range(seconds, 0, -1):
        color_name = color_names[i % len(color_names)]
        
        # Pulse effect by changing character slightly
        for pulse_step in range(4): # Simple 2-state pulse, 2 times
            pulse_char = "✨" if pulse_step % 2 == 0 else "✧"
            display_text = f"{message} {_color_text(str(i), color_name)} {pulse_char}"
            padding = (term_width - len(f"{message} {i}  ")) // 2 # Approx len for centering
            
            sys.stdout.write("\r" + " " * term_width + "\r") # Clear line
            sys.stdout.write(" " * max(0, padding) + display_text)
            sys.stdout.flush()
            time.sleep(0.125) # 8 pulses per second total
            
    sys.stdout.write("\r" + " " * term_width + "\r") # Clear line finally
    _show_cursor()


def _progress_bar(
    text: str,
    progress: float, # 0.0 to 1.0
    width: int = 40,
    fill_char: str = "•",
    empty_char: str = "·",
    bar_color: str = "cyan",
    text_color: str = "yellow",
    pulse: bool = False,
    show_percentage: bool = True
) -> str:
    """Generates a progress bar string with a given progress."""
    progress = max(0.0, min(1.0, progress)) # Clamp progress
    
    effective_width = width
    if show_percentage:
        # Reserve space for " 100%"
        effective_width = max(0, width - 5)

    if pulse:
        pulse_factor = abs(math.sin(time.time() * 5)) # Oscillates between 0 and 1
        # Modulate filled width slightly (e.g., between 90% and 100% of actual progress)
        current_progress_display = progress * (0.9 + 0.1 * pulse_factor)
    else:
        current_progress_display = progress
        
    filled_count = int(effective_width * current_progress_display)
    empty_count = effective_width - filled_count
    
    bar = _color_text(fill_char * filled_count, bar_color) + \
          empty_char * empty_count
          
    percentage_str = f" {int(progress * 100):3d}%" if show_percentage else ""
    
    return f"{_color_text(text, text_color)} [{bar}]{percentage_str}"


def _spinner(text: str, duration: float = 2.0, spin_type: str = "flower", speed: float = 0.1) -> None:
    """Text-based spinner with various character sets."""
    _hide_cursor()
    spinner_chars = SPINNER_SETS.get(spin_type, SPINNER_SETS["braille"])
    num_chars = len(spinner_chars)
    
    start_time = time.time()
    idx = 0
    while time.time() - start_time < duration:
        # Oscillate spinner speed using sine wave for some types
        current_speed = speed
        if spin_type in ["flower", "star", "pulse"]: # Add more types if desired
             speed_factor = abs(math.sin((time.time() - start_time) * 2)) # Modulate speed
             current_speed = speed * (0.5 + speed_factor) # Varies between 0.5x and 1.5x speed

        char = spinner_chars[idx % num_chars]
        sys.stdout.write(f"\r{_color_text(char, 'cyan')} {text} ")
        _clear_line() # Clear rest of the line
        sys.stdout.flush()
        time.sleep(current_speed)
        idx += 1
        
    sys.stdout.write(f"\r{' ' * (len(text) + 5)}\r") # Clear spinner line
    _show_cursor()

# === Scene Transitions ===

def _fade_transition(duration: float = 0.5, to_black: bool = True) -> None:
    """Screen fades to black then back using gradient characters, or just one way."""
    _hide_cursor()
    term_width, term_height = _get_terminal_size()
    
    num_steps = len(FADE_CHARS)
    delay_per_step = duration / num_steps

    # Fade out (to black)
    if to_black:
        for char_code in range(num_steps -1, -1, -1): # From█ to space
            char_to_print = FADE_CHARS[char_code]
            for y in range(term_height):
                _move_cursor(y + 1, 1)
                sys.stdout.write(char_to_print * term_width)
            sys.stdout.flush()
            time.sleep(delay_per_step)
        _clear_screen() # Ensure fully black/cleared
    
    # Fade in (from black) - This part is usually followed by drawing new content
    # For a full fade-out-fade-in, you'd call this, then draw, then call again with to_black=False
    # For now, this function handles one direction or a full cycle if not to_black initially.
    # The AsciiDoc suggests a full cycle, so if to_black=False, it means start from black.
    if not to_black: # Assumed to be fade-in part
        for char_code in range(num_steps): # From space to █ (or rather, from cleared to full)
            # This part is tricky without knowing what to fade *in* to.
            # Typically, you'd clear, draw new content faintly, then more strongly.
            # For simplicity, we'll just "unfade" with characters.
            char_to_print = FADE_CHARS[char_code]
            # This isn't a true fade-in of content, but a visual effect.
            # A real fade-in would require redrawing content with increasing opacity.
            # For terminal, we can simulate by filling with increasingly dense chars.
            for y in range(term_height):
                _move_cursor(y + 1, 1)
                sys.stdout.write(char_to_print * term_width)
            sys.stdout.flush()
            time.sleep(delay_per_step)
    _show_cursor()


def _sparkle_effect_on_text(text: str, duration: float = 1.5, density_factor: int = 3, 
                      colors: Optional[List[str]] = None, speed: float = 0.1) -> None:
    """Create a sparkle effect that twinkles around provided text."""
    if colors is None:
        colors = ["pink", "purple", "cyan", "yellow", "light_blue", "lavender"]
    
    _hide_cursor()
    term_width, term_height = _get_terminal_size()
    
    text_len = len(text)
    text_start_x = (term_width - text_len) // 2
    text_y = term_height // 2

    sparkle_chars = EFFECT_CHARS["sparkles"]
    
    # Calculate number of sparkles based on text length and density
    num_sparkles = min(term_width * term_height // 10, max(10, text_len * density_factor))

    sparkles_data: List[Dict[str, Any]] = []
    for _ in range(num_sparkles):
        # Concentrate sparkles around the text area
        rand_val = random.random()
        if rand_val < 0.7: # 70% chance near text
            x = random.randint(max(0, text_start_x - 5), min(term_width - 1, text_start_x + text_len + 4))
            y_spread = 2 
            y = random.randint(max(0, text_y - y_spread), min(term_height - 1, text_y + y_spread))
        elif rand_val < 0.9: # 20% chance slightly further
            x = random.randint(max(0, text_start_x - 15), min(term_width - 1, text_start_x + text_len + 14))
            y_spread = 4
            y = random.randint(max(0, text_y - y_spread), min(term_height - 1, text_y + y_spread))
        else: # 10% chance anywhere
            x = random.randint(0, term_width - 1)
            y = random.randint(0, term_height - 1)

        # Avoid placing sparkle directly on text characters initially
        if text_y == y and text_start_x <= x < text_start_x + text_len:
            # If it lands on text, try to shift it slightly
            x += random.choice([-2, -1, 1, 2])
            x = max(0, min(term_width - 1, x))


        sparkles_data.append({
            "x": x, "y": y,
            "char": random.choice(sparkle_chars),
            "color": random.choice(colors),
            "life": random.uniform(0.2, 0.8) # Time until it changes/disappears
        })

    start_time = time.time()
    while time.time() - start_time < duration:
        _clear_screen() # Simple clear for this effect

        # Draw the main text
        _move_cursor(text_y, text_start_x)
        sys.stdout.write(text)

        # Draw and update sparkles
        for s_idx, s_data in enumerate(sparkles_data):
            _move_cursor(s_data["y"] + 1, s_data["x"] + 1) # +1 for 1-indexed cursor
            sys.stdout.write(_color_text(s_data["char"], s_data["color"]))
            
            # Update sparkle for next frame (twinkle/move/fade)
            s_data["life"] -= speed
            if s_data["life"] <= 0 or random.random() < 0.1: # Respawn or change
                # For simplicity, just re-randomize this sparkle
                s_data["char"] = random.choice(sparkle_chars)
                s_data["color"] = random.choice(colors)
                s_data["life"] = random.uniform(0.2, 0.8)
                # Optionally, slightly move it
                if random.random() < 0.3:
                    s_data["x"] += random.choice([-1, 1])
                    s_data["y"] += random.choice([-1, 1])
                    s_data["x"] = max(0, min(term_width - 1, s_data["x"]))
                    s_data["y"] = max(0, min(term_height - 1, s_data["y"]))
        
        sys.stdout.flush()
        time.sleep(speed)
        
    _clear_screen()
    _move_cursor(text_y, text_start_x)
    print(text) # Print final text
    _show_cursor()


def _display_floating_particles(duration: float = 3.0, num_particles: int = 30, speed: float = 0.1) -> None:
    """Display floating particle effects in the background."""
    _hide_cursor()
    term_width, term_height = _get_terminal_size()
    
    particles: List[Dict[str, Any]] = []
    for _ in range(num_particles):
        particles.append({
            "x": random.uniform(0, term_width -1), 
            "y": random.uniform(0, term_height -1),
            "char": random.choice(EFFECT_CHARS["sparkles"][:6]), # Use smaller sparkles
            "color": random.choice(["light_blue", "lavender", "cyan", "pink", "purple"]),
            "dx": random.uniform(-0.3, 0.3), 
            "dy": random.uniform(-0.15, 0.15) 
        })

    start_time = time.time()
    while time.time() - start_time < duration:
        _clear_screen() # Or a more sophisticated draw if there's foreground content
        
        for p in particles:
            # Update position
            p["x"] += p["dx"] + random.uniform(-0.05, 0.05) # Add slight jitter
            p["y"] += p["dy"] + random.uniform(-0.05, 0.05)
            
            # Wrap around screen edges
            p["x"] = p["x"] % term_width
            p["y"] = p["y"] % term_height
            
            # Change direction occasionally
            if random.random() < 0.01:
                p["dx"] = random.uniform(-0.3, 0.3)
                p["dy"] = random.uniform(-0.15, 0.15)

            # Draw particle
            draw_x, draw_y = int(p["x"]), int(p["y"])
            if 0 < draw_x <= term_width and 0 < draw_y <= term_height:
                 _move_cursor(draw_y, draw_x)
                 sys.stdout.write(_color_text(p["char"], p["color"]))
        
        sys.stdout.flush()
        time.sleep(speed)
        
    _clear_screen()
    _show_cursor()

# == UI/UX Design Patterns ==

def _bordered_text(text_content: str, frame_style_name: str = "single", 
                   color: str = "cyan", padding: int = 1) -> str:
    """Frames the given text (can be multi-line) with a specified border style."""
    if frame_style_name not in FRAME_STYLES:
        frame_style_name = "single" # Default if style not found
    frame = FRAME_STYLES[frame_style_name]

    lines = text_content.split('\n')
    max_length = 0
    if lines:
        max_length = max(len(line) for line in lines)
    
    content_width = max_length + padding * 2
    
    output_lines: List[str] = []
    # Top border
    output_lines.append(_color_text(frame["tl"] + frame["h"] * content_width + frame["tr"], color))
    
    # Content lines
    for line in lines:
        line_padding_right = " " * (max_length - len(line))
        padded_line = " " * padding + line + line_padding_right + " " * padding
        output_lines.append(_color_text(frame["v"] + padded_line + frame["v"], color))
        
    # Bottom border
    output_lines.append(_color_text(frame["bl"] + frame["h"] * content_width + frame["br"], color))
    
    return "\n".join(output_lines)


def _show_interactive_menu(options: List[str], title: str = "Select an option", 
                           prompt: str = "Enter your choice: ",
                           gradient_title: bool = True, frame: bool = True) -> Optional[int]:
    """Display an interactive menu and return the selected option index (0-based)."""
    _hide_cursor()
    
    title_display: str
    if gradient_title:
        title_display = _gradient_text(f"✨ {title} ✨", ["purple", "pink", "cyan"])
    else:
        title_display = _color_text(f"✨ {title} ✨", "purple", styles=["bold"])
    
    menu_items_str = ""
    for i, option_text in enumerate(options):
        option_num = _color_text(str(i + 1), "pink", styles=["bold"])
        menu_items_str += f"  {option_num}. {option_text}\n"
    
    menu_content = f"{title_display}\n\n{menu_items_str}\n{_color_text(prompt, 'lavender')}"
    
    if frame:
        # Calculate where to print the menu for centering (approximate)
        term_width, term_height = _get_terminal_size()
        menu_lines = menu_content.split('\n')
        menu_height = len(menu_lines)
        
        start_row = (term_height - menu_height) // 2
        _clear_screen()
        
        bordered_content = _bordered_text(menu_content.strip(), frame_style_name="double", color="light_blue")
        bordered_lines = bordered_content.split('\n')
        bordered_height = len(bordered_lines)
        bordered_width = len(bordered_lines[0]) if bordered_lines else 0

        start_row_bordered = (term_height - bordered_height) // 2
        start_col_bordered = (term_width - bordered_width) // 2


        for i, line in enumerate(bordered_lines):
            _move_cursor(max(1, start_row_bordered + i), max(1, start_col_bordered))
            sys.stdout.write(line)
        
        # Position cursor for input at the end of the prompt line (approximated)
        # The prompt is inside the border, so we need to find its position
        prompt_line_index_in_menu = -1
        for i, line in enumerate(menu_lines):
            if prompt.strip() in line: # Find the line containing the prompt
                prompt_line_index_in_menu = i
                break
        
        if prompt_line_index_in_menu != -1:
            # +1 for top border, +1 for 1-based cursor
            cursor_row = max(1, start_row_bordered + 1 + prompt_line_index_in_menu) 
            # +1 for left border, +2 for "  " indent, + len of prompt
            cursor_col = max(1, start_col_bordered + 1 + 2 + len(prompt)) 
            _move_cursor(cursor_row, cursor_col)

    else:
        _clear_screen()
        print(menu_content, end="")

    sys.stdout.flush()
    _show_cursor() # Show cursor for input

    while True:
        try:
            choice_str = input()
            if choice_str.strip().isdigit():
                choice_int = int(choice_str.strip())
                if 1 <= choice_int <= len(options):
                    _hide_cursor() # Hide again before leaving
                    return choice_int - 1 # Return 0-based index
            
            # If invalid, reprint prompt part or error
            # For simplicity, just re-position cursor if possible, or user retypes
            if frame and prompt_line_index_in_menu != -1:
                 _move_cursor(cursor_row, cursor_col)
                 sys.stdout.write(" " * len(choice_str) + "\r") # Clear previous input
                 _move_cursor(cursor_row, cursor_col)
            else: # If not framed or prompt position tricky, just print error on new line
                print(_color_text("Invalid choice. Please try again.", "red"))
                print(_color_text(prompt, 'lavender'), end="")

            sys.stdout.flush()

        except (EOFError, KeyboardInterrupt):
            print("\nMenu selection cancelled.")
            _hide_cursor()
            return None

def _print_step(message: str, status_key: str = "", animate_spinner: bool = True, duration: float = 0.5) -> None:
    """Prints a step message with an optional status indicator and spinner."""
    symbol_info = STATUS_SYMBOLS.get(status_key)
    
    if symbol_info:
        symbol, color = symbol_info
        status_indicator = _color_text(f"[{symbol}]", color)
        full_message = f"{status_indicator} {message}"
    else:
        full_message = f"  {message}" # Indent if no symbol

    if animate_spinner and not status_key: # Only spin if no final status
        _spinner(message, duration=duration, spin_type="braille", speed=0.08)
        # After spinner, print the message without spinner
        sys.stdout.write(f"\r  {message}")
        _clear_line()
        print() # Newline
    else:
        print(full_message)
    sys.stdout.flush()


# == Demo Main Function ==
def main_demo() -> None:
    """Demonstrates various animation effects."""
    _clear_screen()
    _hide_cursor()

    print(_color_text("Terminal Animation System Demo", "pink", styles=["bold", "underline"]))
    time.sleep(1)

    _print_step("Initializing system...", animate_spinner=True, duration=1.5)
    _print_step("System initialized.", status_key="success")
    time.sleep(0.5)

    print("\n" + _gradient_text("Gradient Text Example", ["red", "orange", "yellow", "green", "blue", "purple"]))
    time.sleep(1.5)
    
    _clear_line()
    sys.stdout.write("\r")
    _rainbow_text_animation("Rainbow Animation!", delay=0.08)
    time.sleep(0.5)

    _typing_effect("Simulating a typing effect with variable speed...", speed=0.04)
    time.sleep(1)

    _countdown(3, "Effect starting in:", ["peach", "orange", "red"])
    
    _clear_screen()
    _bubble_effect("Bubbly Fun Text!", duration=3.0)
    time.sleep(0.5)
    
    _clear_screen()
    _sparkle_effect_on_text("✨ Sparkles! ✨", duration=3.0, density_factor=4)
    time.sleep(0.5)

    _print_step("Performing a task...", animate_spinner=False) # No spinner here
    for i in range(101):
        progress_str = _progress_bar(f"Processing item {i}/100", progress=i/100.0, width=50, pulse=(i%20 < 10))
        sys.stdout.write(f"\r{progress_str}")
        sys.stdout.flush()
        time.sleep(0.02)
    print() # Newline after progress bar
    _print_step("Task complete.", status_key="success")
    time.sleep(1)

    _clear_screen()
    _exploding_text("EXPLOSION!", duration=2.0)
    time.sleep(0.5)

    _clear_screen()
    _wave_text("Wavy Text Animation", cycles=2, amplitude=2, speed=0.03)
    time.sleep(0.5)

    _fade_transition(duration=1.0, to_black=True)
    _move_cursor(10,10)
    print(_color_text("Faded In Content", "mint"))
    sys.stdout.flush()
    time.sleep(1)
    _fade_transition(duration=1.0, to_black=True) # Fade out again

    _display_floating_particles(duration=3.0, num_particles=40)
    
    options = ["Option Alpha", "Option Beta (longer)", "Option Gamma"]
    selected_index = _show_interactive_menu(options, title="Demo Menu", frame=True)

    _clear_screen()
    if selected_index is not None:
        _print_step(f"You selected: {options[selected_index]} (Index: {selected_index})", status_key="info")
    else:
        _print_step("Menu selection was cancelled.", status_key="warning")
    time.sleep(1)
    
    print("\n" + _bordered_text("This is some text\ninside a single-line border.", frame_style_name="single", color="yellow"))
    time.sleep(1)
    print("\n" + _bordered_text("And this is in a\ndouble-line border.", frame_style_name="double", color="blue", padding=2))
    time.sleep(1)

    _print_step("Demo finished.", status_key="star")
    _show_cursor()

if __name__ == "__main__":
    try:
        main_demo()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")
    finally:
        _show_cursor() # Ensure cursor is always shown on exit
        print(COLORS["reset"]) # Reset all attributes

