"""FadeChange and FadeStep models for the Fado integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_SUPPORTED_COLOR_MODES
from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN as HA_ATTR_COLOR_TEMP_KELVIN
from homeassistant.components.light import ATTR_HS_COLOR as HA_ATTR_HS_COLOR
from homeassistant.components.light import (
    ATTR_MAX_COLOR_TEMP_KELVIN as HA_ATTR_MAX_COLOR_TEMP_KELVIN,
)
from homeassistant.components.light import (
    ATTR_MIN_COLOR_TEMP_KELVIN as HA_ATTR_MIN_COLOR_TEMP_KELVIN,
)
from homeassistant.components.light.const import ColorMode

from .const import (
    HYBRID_HS_PHASE_RATIO,
    MIN_BRIGHTNESS_DELTA,
    MIN_HUE_DELTA,
    MIN_MIREDS_DELTA,
    MIN_SATURATION_DELTA,
    PLANCKIAN_LOCUS_HS,
    PLANCKIAN_LOCUS_SATURATION_THRESHOLD,
)
from .easing import auto_select_easing, get_easing_func, linear

if TYPE_CHECKING:
    from .fade_params import FadeParams

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Unit Conversion Utilities
# =============================================================================


def _pct_to_brightness(pct: int, min_brightness: int) -> int:
    """Convert brightness percentage (0-100) to raw brightness (0-255).

    Special case: 1% means "dimmest possible" and uses min_brightness
    when it exceeds the normal conversion.
    """
    raw = int(pct * 255 / 100)
    if pct == 1 and min_brightness > raw:
        return min_brightness
    return raw


def _kelvin_to_mireds(kelvin: int) -> int:
    """Convert color temperature from kelvin to mireds."""
    return int(1_000_000 / kelvin)


def _mireds_to_kelvin(mireds: int) -> int:
    """Convert color temperature from mireds to kelvin."""
    return int(1_000_000 / mireds)


def _clamp_mireds(mireds: int, min_mireds: int | None, max_mireds: int | None) -> int:
    """Clamp mireds to the light's supported range.

    Args:
        mireds: The mireds value to clamp
        min_mireds: Minimum mireds (coolest/highest kelvin), or None for no limit
        max_mireds: Maximum mireds (warmest/lowest kelvin), or None for no limit

    Returns:
        Clamped mireds value
    """
    if min_mireds is None and max_mireds is None:
        return mireds
    result = mireds
    if min_mireds is not None:
        result = max(result, min_mireds)
    if max_mireds is not None:
        result = min(result, max_mireds)
    return result


# =============================================================================
# Light Capability Helpers
# =============================================================================


def _get_supported_color_modes(state_attributes: dict[str, Any]) -> set[ColorMode]:
    """Extract supported color modes from state attributes.

    Args:
        state_attributes: Light state attributes dict

    Returns:
        Set of supported ColorMode values
    """
    modes_raw = state_attributes.get(ATTR_SUPPORTED_COLOR_MODES, [])
    return set(modes_raw)


def _supports_brightness(supported_modes: set[ColorMode]) -> bool:
    """Check if light supports brightness control (dimming).

    Args:
        supported_modes: Set of supported ColorMode values

    Returns:
        True if light can be dimmed
    """
    # Any color mode implies brightness support except ONOFF and UNKNOWN
    dimmable_modes = {
        ColorMode.BRIGHTNESS,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
        ColorMode.XY,
        ColorMode.COLOR_TEMP,
    }
    return bool(supported_modes & dimmable_modes)


def _supports_hs(supported_modes: set[ColorMode]) -> bool:
    """Check if light supports HS color.

    Args:
        supported_modes: Set of supported ColorMode values

    Returns:
        True if light can use HS color
    """
    hs_modes = {
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
        ColorMode.XY,
    }
    return bool(supported_modes & hs_modes)


def _supports_color_temp(supported_modes: set[ColorMode]) -> bool:
    """Check if light supports color temperature.

    Args:
        supported_modes: Set of supported ColorMode values

    Returns:
        True if light can use color temperature
    """
    return ColorMode.COLOR_TEMP in supported_modes


# =============================================================================
# Planckian Locus Utilities
# =============================================================================


def _is_on_planckian_locus(hs_color: tuple[float, float]) -> bool:
    """Check if an HS color is on or near the Planckian locus.

    The Planckian locus represents the colors of blackbody radiation
    (color temperatures). Colors on the locus have low saturation
    (white/off-white appearance).

    Args:
        hs_color: Tuple of (hue 0-360, saturation 0-100)

    Returns:
        True if the color is close enough to the locus to transition
        directly to mireds-based fading.
    """
    _, saturation = hs_color
    return saturation <= PLANCKIAN_LOCUS_SATURATION_THRESHOLD


def _hs_to_mireds(hs_color: tuple[float, float]) -> int:
    """Convert an HS color to approximate mireds using Planckian locus lookup.

    Finds the closest matching color temperature on the Planckian locus
    based on hue matching. Used when transitioning from HS to color temp.

    Args:
        hs_color: Tuple of (hue 0-360, saturation 0-100)

    Returns:
        Approximate color temperature in mireds
    """
    hue, saturation = hs_color

    # For very low saturation, return neutral white
    if saturation < 3:
        return 286  # ~3500K neutral white

    # Find closest match in the lookup table based on hue
    best_mireds = 286  # Default to neutral white
    best_distance = float("inf")

    for mireds, (locus_hue, _) in PLANCKIAN_LOCUS_HS:
        # Calculate hue distance (circular)
        distance = abs(hue - locus_hue)
        if distance > 180:
            distance = 360 - distance

        if distance < best_distance:
            best_distance = distance
            best_mireds = mireds

    return best_mireds


def _mireds_to_hs(mireds: int) -> tuple[float, float]:
    """Convert mireds to approximate HS using Planckian locus lookup.

    Interpolates between lookup table entries to find the HS color
    that corresponds to the given color temperature.

    Args:
        mireds: Color temperature in mireds

    Returns:
        Tuple of (hue 0-360, saturation 0-100)
    """
    # Handle values outside the lookup range
    if mireds <= PLANCKIAN_LOCUS_HS[0][0]:
        return PLANCKIAN_LOCUS_HS[0][1]
    if mireds >= PLANCKIAN_LOCUS_HS[-1][0]:
        return PLANCKIAN_LOCUS_HS[-1][1]

    # Find the two bracketing entries
    for i in range(len(PLANCKIAN_LOCUS_HS) - 1):
        lower_mireds, lower_hs = PLANCKIAN_LOCUS_HS[i]
        upper_mireds, upper_hs = PLANCKIAN_LOCUS_HS[i + 1]

        if lower_mireds <= mireds <= upper_mireds:
            # Interpolate between the two entries
            t = (mireds - lower_mireds) / (upper_mireds - lower_mireds)
            hue = lower_hs[0] + (upper_hs[0] - lower_hs[0]) * t
            sat = lower_hs[1] + (upper_hs[1] - lower_hs[1]) * t
            return (round(hue, 2), round(sat, 2))

    # Fallback (should not reach here)
    return (38.0, 12.0)  # Neutral white


# =============================================================================
# Value Resolution
# =============================================================================


def _resolve_start_brightness(
    params: FadeParams, state: dict[str, Any], min_brightness: int = 1
) -> int:
    """Resolve starting brightness from params or current state, with clamping.

    Priority order:
    1. params.from_brightness (raw 1-255) - used directly
    2. params.from_brightness_pct (1-100%) - converted to 0-255
       - Special case: 1% maps to min_brightness when min_brightness > normal conversion
    3. Current state brightness
    4. 0 if light is off

    The result is clamped to min_brightness floor (ensuring fade doesn't start from 0).

    Args:
        params: FadeParams with optional from_brightness_pct/from_brightness
        state: Light attributes dict from state.attributes
        min_brightness: Minimum brightness floor (1-255)

    Returns:
        Starting brightness (min_brightness to 255 scale)
    """
    brightness: int

    if params.from_brightness is not None:
        # Raw brightness value - use directly
        brightness = params.from_brightness
    elif params.from_brightness_pct is not None:
        brightness = _pct_to_brightness(params.from_brightness_pct, min_brightness)
    else:
        # Use state brightness, or 0 if light is off
        state_brightness = state.get(ATTR_BRIGHTNESS)
        brightness = int(state_brightness) if state_brightness is not None else 0

    # Clamp to min_brightness floor
    return max(brightness, min_brightness)


def _resolve_end_brightness(params: FadeParams, min_brightness: int = 1) -> int | None:
    """Resolve ending brightness from params, with clamping.

    Priority order:
    1. params.brightness (raw 1-255) - used directly
    2. params.brightness_pct (1-100%) - converted to 0-255
       - Special case: 1% maps to min_brightness when min_brightness > normal conversion

    The result is clamped to min_brightness floor, EXCEPT when targeting 0
    (user explicitly wants to turn off the light).

    Args:
        params: FadeParams with optional brightness_pct/brightness
        min_brightness: Minimum brightness floor (1-255)

    Returns:
        Ending brightness (0 or min_brightness to 255 scale), or None if not specified
    """
    brightness: int | None = None

    if params.brightness is not None:
        # Raw brightness value - use directly
        brightness = params.brightness
    elif params.brightness_pct is not None:
        brightness = _pct_to_brightness(params.brightness_pct, min_brightness)

    if brightness is None:
        return None

    # Clamp to min_brightness floor, but allow 0 (turn off)
    if brightness == 0:
        return 0
    return max(brightness, min_brightness)


def _resolve_start_hs(params: FadeParams, state: dict[str, Any]) -> tuple[float, float] | None:
    """Resolve starting HS from params.from_hs_color or current state.

    Only returns HS if the light is actually in HS mode (not emulated HS from COLOR_TEMP).
    If from_color_temp_kelvin is explicitly set, returns None (user wants to start from color_temp).

    Args:
        params: FadeParams with optional from_hs_color
        state: Light attributes dict from state.attributes

    Returns:
        Starting HS color (hue 0-360, saturation 0-100), or None if not available
    """
    # If from_color_temp_kelvin is explicitly set, user wants to start from color_temp, not HS
    if params.from_color_temp_kelvin is not None:
        return None
    if params.from_hs_color is not None:
        return params.from_hs_color
    # Only use state HS if light is actually in HS mode (not emulated from COLOR_TEMP)
    color_mode = state.get("color_mode")
    if color_mode == ColorMode.COLOR_TEMP:
        return None
    return state.get(HA_ATTR_HS_COLOR)


def _resolve_start_mireds(params: FadeParams, state: dict[str, Any]) -> int | None:
    """Resolve starting mireds from params.from_color_temp_kelvin or current state.

    FadeParams stores kelvin, but FadeChange needs mireds for linear interpolation.
    This function handles the kelvin->mireds conversion at the boundary.
    Only returns mireds if the light is in COLOR_TEMP mode, or if color_mode is unknown.
    Does NOT return mireds if light is explicitly in HS/RGB mode (those would be emulated).
    If from_hs_color is explicitly set, returns None (user wants to start from HS).

    Args:
        params: FadeParams with optional from_color_temp_kelvin
        state: Light attributes dict from state.attributes

    Returns:
        Starting color temperature in mireds, or None if not available
    """
    # If from_hs_color is explicitly set, user wants to start from HS, not color_temp
    if params.from_hs_color is not None:
        return None
    if params.from_color_temp_kelvin is not None:
        return _kelvin_to_mireds(params.from_color_temp_kelvin)
    # Check color_mode to avoid using emulated values
    color_mode = state.get("color_mode")
    # If color_mode is explicitly HS or other color mode, don't use color_temp (it's emulated)
    if color_mode is not None and color_mode != ColorMode.COLOR_TEMP:
        return None
    # Either color_mode is COLOR_TEMP or unknown - use kelvin if available
    kelvin = state.get(HA_ATTR_COLOR_TEMP_KELVIN)
    if kelvin is not None:
        return _kelvin_to_mireds(kelvin)
    return None


def _resolve_end_mireds(params: FadeParams) -> int | None:
    """Resolve ending mireds from params.color_temp_kelvin.

    Args:
        params: FadeParams with optional color_temp_kelvin

    Returns:
        Ending color temperature in mireds, or None if not specified
    """
    if params.color_temp_kelvin is not None:
        return _kelvin_to_mireds(params.color_temp_kelvin)
    return None


def _from_brightness_if_changed(
    params: FadeParams, state: dict[str, Any], min_brightness: int
) -> int | None:
    """Resolve from-brightness and return it only if it differs from current state."""
    from_bri: int | None = None
    if params.from_brightness is not None:
        from_bri = max(params.from_brightness, min_brightness)
    elif params.from_brightness_pct is not None:
        from_bri = max(
            _pct_to_brightness(params.from_brightness_pct, min_brightness), min_brightness
        )

    if from_bri is None:
        return None

    actual_bri = state.get(ATTR_BRIGHTNESS)
    if actual_bri is None or int(actual_bri) != from_bri:
        return from_bri
    return None


def _from_hs_if_changed(params: FadeParams, state: dict[str, Any]) -> tuple[float, float] | None:
    """Resolve from-HS and return it only if it differs from current state."""
    if params.from_hs_color is None:
        return None

    color_mode = state.get("color_mode")
    if color_mode == ColorMode.COLOR_TEMP:
        # Different color space — always apply
        return params.from_hs_color

    actual_hs = state.get(HA_ATTR_HS_COLOR)
    if actual_hs is None or tuple(actual_hs) != params.from_hs_color:
        return params.from_hs_color
    return None


def _from_color_temp_if_changed(params: FadeParams, state: dict[str, Any]) -> int | None:
    """Resolve from-color-temp and return it only if it differs from current state."""
    if params.from_color_temp_kelvin is None:
        return None

    color_mode = state.get("color_mode")
    if color_mode is not None and color_mode != ColorMode.COLOR_TEMP:
        # Different color space — always apply
        return params.from_color_temp_kelvin

    actual_kelvin = state.get(HA_ATTR_COLOR_TEMP_KELVIN)
    if actual_kelvin is None or int(actual_kelvin) != params.from_color_temp_kelvin:
        return params.from_color_temp_kelvin
    return None


def _build_from_step(
    params: FadeParams, state: dict[str, Any], min_brightness: int
) -> FadeStep | None:
    """Build a FadeStep from explicit 'from' values, only if they differ from current state.

    Compares each from dimension against the light's actual state.
    Only includes dimensions where the from value differs, to avoid
    unnecessary service calls and state-change timeouts.

    Returns None if no from values are specified or all match current state.
    """
    brightness = _from_brightness_if_changed(params, state, min_brightness)
    hs_color = _from_hs_if_changed(params, state)
    color_temp_kelvin = _from_color_temp_if_changed(params, state)

    if brightness is None and hs_color is None and color_temp_kelvin is None:
        return None

    return FadeStep(brightness=brightness, hs_color=hs_color, color_temp_kelvin=color_temp_kelvin)


# =============================================================================
# Resolve Orchestrators (used by FadeChange.resolve)
# =============================================================================


def _resolve_and_filter_colors(
    params: FadeParams,
    state_attributes: dict[str, Any],
    can_hs: bool,
    can_color_temp: bool,
    min_mireds: int | None,
    max_mireds: int | None,
) -> tuple[
    tuple[float, float] | None,
    tuple[float, float] | None,
    int | None,
    int | None,
]:
    """Resolve, clamp, and filter color values based on light capabilities.

    Resolves start/end HS and mireds from params or state, clamps mireds to
    the light's range, converts unsupported modes to supported equivalents,
    and handles the Planckian locus HS-to-mireds optimisation.

    Returns:
        Tuple of (start_hs, end_hs, start_mireds, end_mireds).
    """
    # Resolve from params or state
    start_hs = _resolve_start_hs(params, state_attributes)
    end_hs = params.hs_color
    start_mireds = _resolve_start_mireds(params, state_attributes)
    end_mireds = _resolve_end_mireds(params)

    # Clamp mireds to light's supported range
    if start_mireds is not None:
        start_mireds = _clamp_mireds(start_mireds, min_mireds, max_mireds)
    if end_mireds is not None:
        end_mireds = _clamp_mireds(end_mireds, min_mireds, max_mireds)

    # Convert unsupported color modes to supported equivalents
    if end_mireds is not None and not can_color_temp and can_hs:
        end_hs = _mireds_to_hs(end_mireds)
        end_mireds = None
    if end_hs is not None and not can_hs and can_color_temp:
        if _is_on_planckian_locus(end_hs):
            end_mireds = _hs_to_mireds(end_hs)
            end_mireds = _clamp_mireds(end_mireds, min_mireds, max_mireds)
        end_hs = None

    # Filter out unsupported modes entirely
    if not can_hs:
        start_hs = None
        end_hs = None
    if not can_color_temp:
        start_mireds = None
        end_mireds = None

    # Convert HS on Planckian locus to mireds for smooth interpolation
    if (
        start_hs is not None
        and start_mireds is None
        and end_mireds is not None
        and _is_on_planckian_locus(start_hs)
    ):
        start_mireds = _hs_to_mireds(start_hs)
        start_mireds = _clamp_mireds(start_mireds, min_mireds, max_mireds)
        start_hs = None
        _LOGGER.debug(
            "FadeChange.resolve: Converted on-locus start_hs to start_mireds=%s",
            start_mireds,
        )

    return start_hs, end_hs, start_mireds, end_mireds


def _resolve_auto_turn_on_brightness(
    start_brightness: int,
    end_brightness: int | None,
    end_hs: tuple[float, float] | None,
    end_mireds: int | None,
    state_attributes: dict[str, Any],
    min_brightness: int,
    stored_brightness: int,
) -> int | None:
    """Resolve auto-turn-on brightness when fading color from an off state.

    When fading color from an off/dim state without an explicit brightness
    target, automatically sets end brightness to the stored value (or 255).

    Returns:
        The resolved end_brightness, or the original value unchanged.
    """
    if end_brightness is not None:
        return end_brightness

    # Only auto-turn-on when targeting a color
    if end_hs is None and end_mireds is None:
        return None

    state_brightness = state_attributes.get(ATTR_BRIGHTNESS)
    light_was_off_or_dim = state_brightness is None or state_brightness < min_brightness
    if start_brightness != min_brightness or not light_was_off_or_dim:
        return None

    target_brightness = stored_brightness if stored_brightness > min_brightness else 255
    result = max(target_brightness, min_brightness)
    _LOGGER.debug(
        "FadeChange.resolve: Auto-turn-on from off state, end_brightness=%s",
        result,
    )
    return result


def _detect_hybrid_transition(
    start_hs: tuple[float, float] | None,
    end_hs: tuple[float, float] | None,
    start_mireds: int | None,
    end_mireds: int | None,
    min_mireds: int | None,
    max_mireds: int | None,
) -> tuple[str | None, tuple[float, float] | None, int | None]:
    """Detect if a fade requires a hybrid HS <-> mireds transition.

    Hybrid transitions occur when starting in one color space (HS or mireds)
    and ending in the other.  The crossover point sits on the Planckian locus.

    Returns:
        Tuple of (hybrid_direction, crossover_hs, crossover_mireds).
        hybrid_direction is ``"hs_to_mireds"``, ``"mireds_to_hs"``, or ``None``.
    """
    # HS -> mireds: starting with HS color and targeting mireds
    if (
        start_hs is not None
        and end_mireds is not None
        and end_hs is None
        and start_mireds is None
        and not _is_on_planckian_locus(start_hs)
    ):
        crossover_hs = _mireds_to_hs(end_mireds)
        crossover_mireds = _hs_to_mireds(crossover_hs)
        crossover_mireds = _clamp_mireds(crossover_mireds, min_mireds, max_mireds)
        return "hs_to_mireds", crossover_hs, crossover_mireds

    # mireds -> HS: starting with color temp and targeting HS
    if start_mireds is not None and end_hs is not None and end_mireds is None and start_hs is None:
        crossover_mireds = _hs_to_mireds(end_hs)
        crossover_mireds = _clamp_mireds(crossover_mireds, min_mireds, max_mireds)
        crossover_hs = _mireds_to_hs(crossover_mireds)
        return "mireds_to_hs", crossover_hs, crossover_mireds

    return None, None, None


def _fill_missing_start_values(
    start_hs: tuple[float, float] | None,
    end_hs: tuple[float, float] | None,
    start_mireds: int | None,
    end_mireds: int | None,
    min_mireds: int | None,
    max_mireds: int | None,
) -> tuple[tuple[float, float] | None, int | None]:
    """Fill in missing start values for non-hybrid transitions.

    When starting from an off/unknown state with a color target but no start
    value, uses reasonable defaults for a visible transition.

    Returns:
        Tuple of (start_hs, start_mireds) with missing values filled in.
    """
    if end_mireds is not None and start_mireds is None:
        # Use closest boundary (min or max mireds) as start
        if min_mireds is not None and max_mireds is not None:
            dist_to_min = abs(end_mireds - min_mireds)
            dist_to_max = abs(end_mireds - max_mireds)
            start_mireds = min_mireds if dist_to_min <= dist_to_max else max_mireds
        elif min_mireds is not None:
            start_mireds = min_mireds
        elif max_mireds is not None:
            start_mireds = max_mireds
        else:
            start_mireds = end_mireds
        _LOGGER.debug(
            "FadeChange.resolve: No start_mireds, using boundary mireds=%s as start",
            start_mireds,
        )

    if end_hs is not None and start_hs is None:
        start_hs = (0.0, 0.0)
        _LOGGER.debug(
            "FadeChange.resolve: No start_hs, using white (0, 0) as start",
        )

    return start_hs, start_mireds


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FadeStep:
    """A single step in a fade sequence.

    All values are optional - only include attributes being faded.
    Color temperature is in kelvin for direct use with Home Assistant.
    """

    brightness: int | None = None
    hs_color: tuple[float, float] | None = None
    color_temp_kelvin: int | None = None


@dataclass
class FadeChange:  # pylint: disable=too-many-instance-attributes
    """A fade operation with flat step generation and hybrid transition support.

    This class represents a change from start to end values for brightness,
    HS color, and/or color temperature. It generates steps on-demand via
    an iterator pattern rather than pre-building a list.

    Hybrid transitions (HS <-> color temp) are handled internally by tracking
    a crossover point where the color mode switches. This enables flat step
    generation for ease-in/ease-out implementation.

    Color temperature is stored internally as mireds for linear interpolation,
    but converted to kelvin when generating FadeStep output.

    All start/end values are optional - only include dimensions being faded.
    """

    # Brightness (0-255 scale)
    start_brightness: int | None = None
    end_brightness: int | None = None

    # HS color (hue 0-360, saturation 0-100)
    start_hs: tuple[float, float] | None = None
    end_hs: tuple[float, float] | None = None

    # Color temperature (mireds, internal use for linear interpolation)
    start_mireds: int | None = None
    end_mireds: int | None = None

    # Timing
    transition_ms: int = 0
    min_step_delay_ms: int = 100

    # Hybrid transition tracking (private)
    # "hs_to_mireds" | "mireds_to_hs" | None
    hybrid_direction: str | None = field(default=None, repr=False)
    crossover_step: int | None = field(default=None, repr=False)
    _crossover_hs: tuple[float, float] | None = field(default=None, repr=False)
    _crossover_mireds: int | None = field(default=None, repr=False)

    # Iterator state (private)
    _current_step: int = field(default=0, repr=False)
    _step_count: int | None = field(default=None, repr=False)

    # Easing function for brightness interpolation (private)
    _easing_func: Callable[[float], float] = field(default=linear, repr=False)
    easing_name: str = field(default="linear", repr=False)

    # Track last emitted step to skip duplicates caused by easing (private)
    _last_emitted_step: FadeStep | None = field(default=None, repr=False)

    # Optional pre-step: applies explicit "from" values before the fade begins.
    # Set when the user provides from values that differ from the light's actual state.
    from_step: FadeStep | None = field(default=None, repr=False)

    @property
    def has_fade(self) -> bool:
        """Whether there are fade steps to iterate (start/end differ on some dimension)."""
        return (
            self.start_brightness is not None
            or self.start_hs is not None
            or self.start_mireds is not None
        )

    @classmethod
    def resolve(
        cls,
        params: FadeParams,
        state_attributes: dict[str, Any],
        min_step_delay_ms: int,
        stored_brightness: int = 0,
        min_brightness: int = 1,
    ) -> FadeChange | None:
        """Factory that resolves fade parameters against light capabilities.

        This method consolidates all resolution and filtering logic:
        - Extracts light capabilities from state attributes
        - Resolves start values from params or state
        - Converts kelvin to mireds (with bounds clamping)
        - Detects hybrid transition scenarios (HS <-> color temp)
        - Filters/converts based on light capabilities
        - Handles non-dimmable lights (single step, zero delay)
        - Auto-fades brightness from 0 when targeting color from off state
        - Clamps brightness values to min_brightness floor
        - Returns None if nothing to fade

        Args:
            params: FadeParams from service call
            state_attributes: Light state attributes dict
            min_step_delay_ms: Minimum delay between steps in milliseconds
            stored_brightness: Previously stored brightness (for auto-turn-on from off)
            min_brightness: Minimum brightness floor (1-255), ensures fade
                doesn't include brightness values below this threshold

        Returns:
            Configured FadeChange, or None if nothing to fade
        """
        # Extract light capabilities from state
        supported_color_modes = _get_supported_color_modes(state_attributes)
        can_dim = _supports_brightness(supported_color_modes)
        can_hs = _supports_hs(supported_color_modes)
        can_color_temp = _supports_color_temp(supported_color_modes)

        # Extract color temp bounds (kelvin -> mireds with inversion)
        min_kelvin = state_attributes.get(HA_ATTR_MIN_COLOR_TEMP_KELVIN)
        max_kelvin = state_attributes.get(HA_ATTR_MAX_COLOR_TEMP_KELVIN)
        min_mireds = _kelvin_to_mireds(max_kelvin) if max_kelvin else None
        max_mireds = _kelvin_to_mireds(min_kelvin) if min_kelvin else None

        # Resolve brightness values (with min_brightness clamping)
        start_brightness = _resolve_start_brightness(params, state_attributes, min_brightness)
        end_brightness = _resolve_end_brightness(params, min_brightness)

        # Resolve easing function for brightness
        easing_name = params.easing
        if easing_name == "auto":
            # Auto-select based on fade direction
            # Use resolved brightness values (start from state, end from params)
            auto_start = start_brightness
            auto_end = end_brightness if end_brightness is not None else start_brightness
            easing_name = auto_select_easing(auto_start, auto_end)
        easing_func = get_easing_func(easing_name)

        # Handle non-dimmable lights (on/off only)
        if not can_dim:
            # Only process if brightness is being targeted
            if end_brightness is None:
                return None
            # Single step with zero delay - just set on/off
            target = 255 if end_brightness > 0 else 0
            return cls(
                start_brightness=start_brightness,
                end_brightness=target,
                transition_ms=0,
                min_step_delay_ms=min_step_delay_ms,
            )

        # Resolve, clamp, and filter color values by light capabilities
        start_hs, end_hs, start_mireds, end_mireds = _resolve_and_filter_colors(
            params, state_attributes, can_hs, can_color_temp, min_mireds, max_mireds
        )

        # Auto-turn-on brightness when fading color from off state
        end_brightness = _resolve_auto_turn_on_brightness(
            start_brightness,
            end_brightness,
            end_hs,
            end_mireds,
            state_attributes,
            min_brightness,
            stored_brightness,
        )

        # Build from_step if explicit from values differ from current state
        from_step = (
            _build_from_step(params, state_attributes, min_brightness)
            if params.has_from_target()
            else None
        )

        # Check if anything is changing (from → to interpolation)
        brightness_changing = end_brightness is not None and start_brightness != end_brightness
        hs_changing = end_hs is not None and start_hs != end_hs
        mireds_changing = end_mireds is not None and start_mireds != end_mireds

        if not brightness_changing and not hs_changing and not mireds_changing:
            if from_step is None:
                return None  # Nothing to do at all
            # Only a from step, no fade — return FadeChange with just the from_step
            return cls(from_step=from_step)

        # Detect hybrid transitions (HS <-> mireds crossover)
        hybrid_direction, crossover_hs, crossover_mireds = _detect_hybrid_transition(
            start_hs,
            end_hs,
            start_mireds,
            end_mireds,
            min_mireds,
            max_mireds,
        )

        # Fill in missing start values for non-hybrid transitions
        if not hybrid_direction:
            start_hs, start_mireds = _fill_missing_start_values(
                start_hs,
                end_hs,
                start_mireds,
                end_mireds,
                min_mireds,
                max_mireds,
            )

        # Create FadeChange
        fade = cls(
            start_brightness=start_brightness if brightness_changing else None,
            end_brightness=end_brightness if brightness_changing else None,
            start_hs=start_hs if (hs_changing or hybrid_direction) else None,
            end_hs=end_hs if (hs_changing or hybrid_direction) else None,
            start_mireds=start_mireds if (mireds_changing or hybrid_direction) else None,
            end_mireds=end_mireds if (mireds_changing or hybrid_direction) else None,
            transition_ms=params.transition_ms,
            min_step_delay_ms=min_step_delay_ms,
            hybrid_direction=hybrid_direction,
            _crossover_hs=crossover_hs,
            _crossover_mireds=crossover_mireds,
            _easing_func=easing_func,
            easing_name=easing_name,
            from_step=from_step,
        )

        # Calculate crossover step if hybrid
        if hybrid_direction:
            total_steps = fade.step_count()
            if hybrid_direction == "hs_to_mireds":
                crossover_step = int(total_steps * HYBRID_HS_PHASE_RATIO)
            else:  # mireds_to_hs
                crossover_step = int(total_steps * (1 - HYBRID_HS_PHASE_RATIO))
            # Update the crossover step (need to set directly since it's a private field)
            fade.crossover_step = crossover_step

        return fade

    def step_count(self) -> int:
        """Calculate optimal step count based on change magnitude and time constraints.

        The algorithm:
        1. Calculate ideal steps per dimension: change / minimum_delta
        2. Take the maximum across all changing dimensions (smoothest dimension wins)
        3. Constrain by time: if ideal * min_step_delay_ms > transition_ms, use time-limited

        Returns:
            Optimal number of steps (at least 1)
        """
        if self._step_count is not None:
            return self._step_count

        ideal_steps: list[int] = []

        # Brightness change
        if self.start_brightness is not None and self.end_brightness is not None:
            brightness_change = abs(self.end_brightness - self.start_brightness)
            if brightness_change > 0:
                ideal_steps.append(brightness_change // MIN_BRIGHTNESS_DELTA)

        # Color changes (HS and/or mireds, accounting for hybrid phases)
        self._add_color_ideal_steps(ideal_steps)

        ideal = max(ideal_steps) if ideal_steps else 1
        max_by_time = (
            self.transition_ms // self.min_step_delay_ms if self.min_step_delay_ms > 0 else ideal
        )

        self._step_count = max(1, min(ideal, max_by_time))
        return self._step_count

    def _add_hs_steps(
        self,
        ideal_steps: list[int],
        start_hs: tuple[float, float],
        end_hs: tuple[float, float],
    ) -> None:
        """Add ideal step counts for HS color change to the list."""
        hue_diff = abs(end_hs[0] - start_hs[0])
        # Handle hue wraparound (shortest path)
        if hue_diff > 180:
            hue_diff = 360 - hue_diff
        if hue_diff > 0:
            ideal_steps.append(int(hue_diff / MIN_HUE_DELTA))

        sat_diff = abs(end_hs[1] - start_hs[1])
        if sat_diff > 0:
            ideal_steps.append(int(sat_diff / MIN_SATURATION_DELTA))

    def _add_mireds_steps(
        self,
        ideal_steps: list[int],
        start_mireds: int,
        end_mireds: int,
    ) -> None:
        """Add ideal step count for mireds color change to the list."""
        mireds_change = abs(end_mireds - start_mireds)
        if mireds_change > 0:
            ideal_steps.append(mireds_change // MIN_MIREDS_DELTA)

    def _add_color_ideal_steps(self, ideal_steps: list[int]) -> None:
        """Compute ideal step counts for color dimensions and append to list."""
        if self.hybrid_direction == "hs_to_mireds":
            # HS phase: from start_hs to crossover_hs
            if self.start_hs is not None and self._crossover_hs is not None:
                self._add_hs_steps(ideal_steps, self.start_hs, self._crossover_hs)
            # Mireds phase: from crossover_mireds to end_mireds
            if self._crossover_mireds is not None and self.end_mireds is not None:
                self._add_mireds_steps(ideal_steps, self._crossover_mireds, self.end_mireds)
        elif self.hybrid_direction == "mireds_to_hs":
            # Mireds phase: from start_mireds to crossover_mireds
            if self.start_mireds is not None and self._crossover_mireds is not None:
                self._add_mireds_steps(ideal_steps, self.start_mireds, self._crossover_mireds)
            # HS phase: from crossover_hs to end_hs
            if self._crossover_hs is not None and self.end_hs is not None:
                self._add_hs_steps(ideal_steps, self._crossover_hs, self.end_hs)
        else:
            # Non-hybrid: standard HS and mireds handling
            if self.start_hs is not None and self.end_hs is not None:
                self._add_hs_steps(ideal_steps, self.start_hs, self.end_hs)
            if self.start_mireds is not None and self.end_mireds is not None:
                self._add_mireds_steps(ideal_steps, self.start_mireds, self.end_mireds)

    def delay_ms(self) -> float:
        """Calculate delay between steps.

        Returns:
            Delay in milliseconds, or 0 if step_count <= 1.
        """
        count = self.step_count()
        if count <= 1:
            return 0.0
        return self.transition_ms / count

    def reset(self) -> None:
        """Reset iterator to beginning."""
        self._current_step = 0
        self._last_emitted_step = None

    def has_next(self) -> bool:
        """Check if more steps remain."""
        return self._current_step < self.step_count()

    def next_step(self) -> FadeStep:
        """Generate and return next step using interpolation.

        For hybrid transitions, emits different color attributes before/after
        the crossover point. Color temperature is converted from internal
        mireds to kelvin.

        Steps that produce identical values to the previous step are skipped
        (can happen with easing functions that compress progress at extremes).

        Raises:
            StopIteration: If no more steps remain.
        """
        count = self.step_count()

        while self.has_next():
            self._current_step += 1

            # Use t=1.0 for the last step to hit target exactly
            t = self._current_step / count

            # Generate the step
            if self.hybrid_direction is not None:
                crossover_step = self.crossover_step or 0
                crossover_t = crossover_step / count if count > 0 else 0.5
                if self.hybrid_direction == "hs_to_mireds":
                    step = self._interpolate_hs_to_mireds_step(t, crossover_t)
                else:
                    step = self._interpolate_mireds_to_hs_step(t, crossover_t)
            else:
                step = FadeStep(
                    brightness=self._interpolate_brightness(t),
                    hs_color=self._interpolate_hs_between(self.start_hs, self.end_hs, t),
                    color_temp_kelvin=self._interpolate_color_temp_kelvin(t),
                )

            # Always emit the last step to hit target exactly
            is_last_step = self._current_step >= count

            # Skip if identical to last emitted step (unless it's the last step)
            if (
                not is_last_step
                and self._last_emitted_step is not None
                and self._steps_equal(step, self._last_emitted_step)
            ):
                _LOGGER.debug(
                    "Skipping duplicate step %d/%d: %s",
                    self._current_step,
                    count,
                    step,
                )
                continue

            self._last_emitted_step = step
            return step

        raise StopIteration

    def _steps_equal(self, step1: FadeStep, step2: FadeStep) -> bool:
        """Check if two FadeSteps have identical values."""
        return (
            step1.brightness == step2.brightness
            and step1.hs_color == step2.hs_color
            and step1.color_temp_kelvin == step2.color_temp_kelvin
        )

    def _interpolate_hs_to_mireds_step(self, t: float, crossover_t: float) -> FadeStep:
        """Interpolate a step for HS -> mireds hybrid transition.

        Before the crossover point, interpolates HS color from start to crossover.
        After the crossover, interpolates mireds from crossover to end.

        Args:
            t: Overall interpolation factor (0.0 = start, 1.0 = end)
            crossover_t: The t value at which the color space switches
        """
        crossover_step = self.crossover_step or 0

        # Before/at crossover: emit hs_color
        if self._current_step <= crossover_step:
            phase_t = t / crossover_t if crossover_t > 0 else 1.0
            hs_color = self._interpolate_hs_between(self.start_hs, self._crossover_hs, phase_t)
            return FadeStep(
                brightness=self._interpolate_brightness(t),
                hs_color=hs_color,
            )
        # After crossover: emit color_temp_kelvin
        remaining_t = 1.0 - crossover_t
        phase_t = (t - crossover_t) / remaining_t if remaining_t > 0 else 1.0
        mireds = self._interpolate_mireds_between(self._crossover_mireds, self.end_mireds, phase_t)
        kelvin = _mireds_to_kelvin(mireds) if mireds else None
        return FadeStep(
            brightness=self._interpolate_brightness(t),
            color_temp_kelvin=kelvin,
        )

    def _interpolate_mireds_to_hs_step(self, t: float, crossover_t: float) -> FadeStep:
        """Interpolate a step for mireds -> HS hybrid transition.

        Before the crossover point, interpolates mireds from start to crossover.
        After the crossover, interpolates HS color from crossover to end.

        Args:
            t: Overall interpolation factor (0.0 = start, 1.0 = end)
            crossover_t: The t value at which the color space switches
        """
        crossover_step = self.crossover_step or 0

        # Before/at crossover: emit color_temp_kelvin
        if self._current_step <= crossover_step:
            phase_t = t / crossover_t if crossover_t > 0 else 1.0
            mireds = self._interpolate_mireds_between(
                self.start_mireds, self._crossover_mireds, phase_t
            )
            kelvin = _mireds_to_kelvin(mireds) if mireds else None
            return FadeStep(
                brightness=self._interpolate_brightness(t),
                color_temp_kelvin=kelvin,
            )
        # After crossover: emit hs_color
        remaining_t = 1.0 - crossover_t
        phase_t = (t - crossover_t) / remaining_t if remaining_t > 0 else 1.0
        hs_color = self._interpolate_hs_between(self._crossover_hs, self.end_hs, phase_t)
        return FadeStep(
            brightness=self._interpolate_brightness(t),
            hs_color=hs_color,
        )

    def _interpolate_hs_between(
        self,
        start: tuple[float, float] | None,
        end: tuple[float, float] | None,
        t: float,
    ) -> tuple[float, float] | None:
        """Interpolate HS color between two points."""
        if start is None or end is None:
            return None

        start_hue, start_sat = start
        end_hue, end_sat = end

        hue_diff = end_hue - start_hue
        if hue_diff > 180:
            hue_diff -= 360
        elif hue_diff < -180:
            hue_diff += 360

        hue = (start_hue + hue_diff * t) % 360
        sat = start_sat + (end_sat - start_sat) * t

        return (round(hue, 2), round(sat, 2))

    def _interpolate_mireds_between(
        self,
        start: int | None,
        end: int | None,
        t: float,
    ) -> int | None:
        """Interpolate mireds between two points."""
        if start is None or end is None:
            return None
        return round(start + (end - start) * t)

    def _interpolate_brightness(self, t: float) -> int | None:
        """Interpolate brightness at factor t with easing applied.

        Args:
            t: Interpolation factor (0.0 = start, 1.0 = end)

        Returns:
            Interpolated brightness, or None if brightness not set.
            Skips brightness level 1 (many lights behave oddly at this level).
        """
        if self.start_brightness is None or self.end_brightness is None:
            return None

        # Apply easing to t for perceptually smooth brightness transitions
        eased_t = self._easing_func(t)

        brightness = round(
            self.start_brightness + (self.end_brightness - self.start_brightness) * eased_t
        )
        # Skip brightness level 1 (many lights behave oddly at this level)
        if brightness == 1:
            brightness = 0 if self.end_brightness < self.start_brightness else 2
        return brightness

    def _interpolate_color_temp_kelvin(self, t: float) -> int | None:
        """Interpolate color temperature, returning kelvin.

        Interpolation is done in mireds (linear in color space),
        then converted to kelvin for the output.

        Args:
            t: Interpolation factor (0.0 = start, 1.0 = end)

        Returns:
            Interpolated color temperature in kelvin, or None if not set.
        """
        mireds = self._interpolate_mireds_between(self.start_mireds, self.end_mireds, t)
        if mireds is None:
            return None
        return _mireds_to_kelvin(mireds)
