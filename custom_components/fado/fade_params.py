"""FadeParams model for the Fado integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.util.color import (
    color_RGB_to_hs,
    color_rgbw_to_rgb,
    color_rgbww_to_rgb,
    color_xy_to_hs,
)

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EASING,
    ATTR_FROM,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DEFAULT_TRANSITION,
)


@dataclass
class FadeParams:
    """Normalized parameters for a fade operation.

    All color inputs are converted to internal representations:
    - RGB/RGBW/RGBWW/XY colors -> hs_color (hue 0-360, saturation 0-100)
    - color_temp_kelvin is stored directly (no conversion)

    Brightness can be specified as:
    - brightness_pct: 0-100 percentage value
    - brightness: 1-255 raw value (advanced)
    Only one can be specified at a time.

    Type/range validation and mutual exclusion are handled by the voluptuous
    schema in __init__.py. This class handles extraction and color conversion.
    """

    brightness_pct: int | None = None
    brightness: int | None = None  # Raw brightness value (1-255)
    hs_color: tuple[float, float] | None = None  # (hue, saturation)
    color_temp_kelvin: int | None = None
    transition_ms: int = DEFAULT_TRANSITION * 1000
    easing: str = "auto"  # "auto", "linear", or explicit curve name

    # Starting values (from: parameter)
    from_brightness_pct: int | None = None
    from_brightness: int | None = None  # Raw brightness starting value (1-255)
    from_hs_color: tuple[float, float] | None = None
    from_color_temp_kelvin: int | None = None

    def has_target(self) -> bool:
        """Check if any fade target values are specified."""
        return (
            self.brightness_pct is not None
            or self.brightness is not None
            or self.hs_color is not None
            or self.color_temp_kelvin is not None
        )

    def has_from_target(self) -> bool:
        """Check if any from values are specified."""
        return (
            self.from_brightness_pct is not None
            or self.from_brightness is not None
            or self.from_hs_color is not None
            or self.from_color_temp_kelvin is not None
        )

    @classmethod
    def from_service_data(cls, data: dict) -> FadeParams:
        """Create FadeParams from validated service call data.

        Assumes the data has already been validated by the voluptuous schema
        (type coercion, range checks, mutual exclusion).

        Extracts and converts color values to internal representations.
        """
        brightness_pct, brightness, hs_color, color_temp_kelvin = cls._extract_fade_values(data)

        from_brightness_pct = None
        from_brightness = None
        from_hs_color = None
        from_color_temp_kelvin = None

        from_data = data.get(ATTR_FROM, {})
        if from_data:
            (
                from_brightness_pct,
                from_brightness,
                from_hs_color,
                from_color_temp_kelvin,
            ) = cls._extract_fade_values(from_data)

        transition_ms = int(1000 * float(data.get(ATTR_TRANSITION, DEFAULT_TRANSITION)))
        easing = str(data.get(ATTR_EASING, "auto"))

        return cls(
            brightness_pct=brightness_pct,
            brightness=brightness,
            hs_color=hs_color,
            color_temp_kelvin=color_temp_kelvin,
            transition_ms=transition_ms,
            easing=easing,
            from_brightness_pct=from_brightness_pct,
            from_brightness=from_brightness,
            from_hs_color=from_hs_color,
            from_color_temp_kelvin=from_color_temp_kelvin,
        )

    @classmethod
    def _extract_fade_values(
        cls, data: dict
    ) -> tuple[int | None, int | None, tuple[float, float] | None, int | None]:
        """Extract brightness values, HS color, and color temp from data dict.

        Returns:
            Tuple of (brightness_pct, brightness, hs_color, color_temp_kelvin)
        """
        brightness_pct = int(data[ATTR_BRIGHTNESS_PCT]) if ATTR_BRIGHTNESS_PCT in data else None
        brightness = int(data[ATTR_BRIGHTNESS]) if ATTR_BRIGHTNESS in data else None
        hs, kelvin = cls._extract_color(data)
        return brightness_pct, brightness, hs, kelvin

    @staticmethod
    def _extract_color(data: dict) -> tuple[tuple[float, float] | None, int | None]:
        """Extract color from data dict, converting to HS or keeping kelvin.

        Returns:
            Tuple of (hs_color, color_temp_kelvin) - one will be None
        """
        # Handle HS color (pass through)
        if ATTR_HS_COLOR in data:
            hs = data[ATTR_HS_COLOR]
            return (float(hs[0]), float(hs[1])), None

        # Handle RGB -> HS
        if ATTR_RGB_COLOR in data:
            rgb = data[ATTR_RGB_COLOR]
            hs = color_RGB_to_hs(rgb[0], rgb[1], rgb[2])
            return hs, None

        # Handle RGBW -> RGB -> HS
        if ATTR_RGBW_COLOR in data:
            rgbw = data[ATTR_RGBW_COLOR]
            rgb = color_rgbw_to_rgb(rgbw[0], rgbw[1], rgbw[2], rgbw[3])
            hs = color_RGB_to_hs(rgb[0], rgb[1], rgb[2])
            return hs, None

        # Handle RGBWW -> RGB -> HS
        if ATTR_RGBWW_COLOR in data:
            rgbww = data[ATTR_RGBWW_COLOR]
            rgb = color_rgbww_to_rgb(
                rgbww[0],
                rgbww[1],
                rgbww[2],
                rgbww[3],
                rgbww[4],
                min_kelvin=2700,
                max_kelvin=6500,
            )
            hs = color_RGB_to_hs(rgb[0], rgb[1], rgb[2])
            return hs, None

        # Handle XY -> HS
        if ATTR_XY_COLOR in data:
            xy = data[ATTR_XY_COLOR]
            hs = color_xy_to_hs(xy[0], xy[1])
            return hs, None

        # Handle color temperature (keep as kelvin)
        if ATTR_COLOR_TEMP_KELVIN in data:
            return None, int(data[ATTR_COLOR_TEMP_KELVIN])

        return None, None
