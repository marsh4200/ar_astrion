"""Constants for the AR Astrion Remote integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ar_astrion"

DEFAULT_PORT: Final = 8080
DEFAULT_NAME: Final = "Astrion Remote"

CONF_WEBHOOK_ID: Final = "webhook_id"
CONF_RELEASE_REPO: Final = "release_repo"

# Where the device's own updater looks for a newer APK. Configurable because a
# fork publishes its own releases; the device has no endpoint that reports the
# latest available version as data (its /check-update answers with an HTML
# redirect meant for a browser), so the update entity resolves it here.
DEFAULT_RELEASE_REPO: Final = "dckiller51/astrion-custom-dashboard"

# Backstop only — everything below is pushed to the webhook the moment it
# changes, so polling exists purely to recover from a missed push or a webhook
# that was never configured.
UPDATE_INTERVAL_MINUTES: Final = 10

PRESS_SHORT: Final = "short"
PRESS_LONG: Final = "long"
PRESS_TYPES: Final = [PRESS_SHORT, PRESS_LONG]

SIGNAL_BUTTON: Final = "ar_astrion_button_{entry_id}"

ATTR_KEY: Final = "key"
ATTR_KEY_CODE: Final = "key_code"
ATTR_BOUND: Final = "bound"
ATTR_PAGE: Final = "page"

# The HA100's buttons, as MainActivity reports them. Keyed by the logical name
# the app pushes (HardwareKey), valued by a human label for the entity name.
#
# POWER is deliberately absent: Android's window manager swallows every real
# KEYCODE_POWER press before an app can see it, so the remote can never report
# that button — only the on-screen power tile uses that key internally.
HARDWARE_KEYS: Final[dict[str, str]] = {
    "BACK": "Back",
    "HOME": "Home",
    "VOLUME_UP": "Volume up",
    "VOLUME_DOWN": "Volume down",
    "MUTE": "Mute",
    "PAGE_UP": "Page up",
    "PAGE_DOWN": "Page down",
    "UP": "Up",
    "DOWN": "Down",
    "LEFT": "Left",
    "RIGHT": "Right",
    "CENTER": "OK",
    "VOICE": "Microphone",
    "MAIN": "Menu",
    # Printed as the media-transport row; the stock firmware tables call these
    # four light / curtain / scene / ac (keycodes 134-137).
    "REWIND": "Rewind",
    "PLAY": "Play / pause",
    "STOP": "Stop",
    "FASTFORWARD": "Fast-forward",
    "RED_BUTTON": "Red",
    "GREEN_BUTTON": "Green",
    "BLUE_BUTTON": "Blue",
    "YELLOW_BUTTON": "Yellow",
}

# Anything the app couldn't map to a known keycode arrives as UNKNOWN; it still
# carries its raw keyCode, so one catch-all entity keeps those automatable on a
# hardware variant this list doesn't cover.
KEY_UNKNOWN: Final = "UNKNOWN"

SERVICE_PUSH_DASHBOARD: Final = "push_dashboard"
SERVICE_RING: Final = "ring"

ATTR_CONFIG: Final = "config"
ATTR_PATH: Final = "path"
ATTR_SOUND: Final = "sound"
ATTR_VOLUME: Final = "volume"
ATTR_DURATION: Final = "duration"

RING_SOUNDS: Final = ["ringtone", "alarm", "notification"]
