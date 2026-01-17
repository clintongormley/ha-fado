"""Constants for the Fade Lights integration."""

DOMAIN = "fade_lights"

# Services
SERVICE_FADE_LIGHTS = "fade_lights"

# Service attributes
ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_TRANSITION = "transition"

# Storage
STORAGE_KEY = f"{DOMAIN}.last_brightness"
STORAGE_VERSION = 2

# Storage keys
KEY_ORIG_BRIGHTNESS = "orig"
KEY_CURR_BRIGHTNESS = "curr"

# Option keys
OPTION_DEFAULT_BRIGHTNESS_PCT = "default_brightness_pct"
OPTION_DEFAULT_TRANSITION = "default_transition"
OPTION_STEP_DELAY_MS = "step_delay_ms"

# Defaults (used when options are not set)
DEFAULT_BRIGHTNESS_PCT = 40
DEFAULT_TRANSITION = 3  # seconds
DEFAULT_STEP_DELAY_MS = 100  # milliseconds
