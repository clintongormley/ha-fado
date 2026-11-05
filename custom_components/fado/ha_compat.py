"""Cross-version compatibility helpers.

Isolates Home Assistant APIs that differ across the supported version range so
the rest of the integration can stay version-agnostic.

Imports inside the resolver functions are intentionally deferred to call time,
not hoisted to module scope: none of the helpers exists on every supported HA
version. ``helpers.target.TargetSelection`` only exists from HA 2026.1.0 (the
``helpers.target`` module itself arrived in HA 2025.8.0, without that symbol);
``helpers.target.async_extract_excluded_entity_ids`` only exists from HA
2026.11.0; ``helpers.service``'s extractor is removed in HA 2026.8. A
module-scope import of any of these symbols would crash the integration on the
HA versions where it is absent. Deferring keeps each import on the branch that
is only taken when the symbol exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant, ServiceCall, callback

if TYPE_CHECKING:
    # The type checker always sees the upstream class; the runtime fallback
    # below is behaviourally identical from a caller's perspective.
    from homeassistant.config_entries import OptionsFlowWithReload
else:
    try:  # HA >= 2025.8.0
        from homeassistant.config_entries import OptionsFlowWithReload
    except ImportError:  # pragma: no cover - exercised only on HA < 2025.8.0
        from homeassistant.config_entries import OptionsFlow

        class OptionsFlowWithReload(OptionsFlow):
            """Backport of HA 2025.8.0's ``OptionsFlowWithReload`` for older HA.

            Schedules a config-entry reload when the options flow finishes with
            changed options, matching upstream behaviour. The reload is scoped to
            flow completion, so unrelated entry updates (e.g. the live websocket
            settings save) do not trigger a reload. Upstream forbids combining
            its version with config-entry update listeners; this backport adds
            none, so the same constraint holds.
            """

            @callback
            def async_create_entry(self, *, data: Any = None, **kwargs: Any) -> ConfigFlowResult:
                result = super().async_create_entry(data=data, **kwargs)
                if data is not None and dict(data) != dict(self.config_entry.options):
                    self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
                return result


__all__ = [
    "OptionsFlowWithReload",
    "extract_excluded_entity_ids",
    "extract_referenced_entity_ids",
]


def _extract_via_target(hass: HomeAssistant, call: ServiceCall):
    """Resolve referenced entities using the modern target helper (HA >= 2026.1.0)."""
    from homeassistant.helpers.target import (  # noqa: PLC0415
        TargetSelection,
        async_extract_referenced_entity_ids,
    )

    return async_extract_referenced_entity_ids(hass, TargetSelection(call.data))


def _extract_via_service(hass: HomeAssistant, call: ServiceCall):
    """Resolve referenced entities using the legacy service helper (HA < 2026.1.0).

    ``homeassistant.helpers.service.async_extract_referenced_entity_ids`` accepts
    a ``ServiceCall`` directly and predates the ``target`` helper. It is
    deprecated on newer HA (removed in 2026.8), but this path only runs on older
    HA where it remains the canonical API. Once the integration's floor reaches
    2026.1.0, this resolver shim can be dropped in favour of importing the target
    helper directly (the OptionsFlowWithReload backport above can go at 2025.8.0).
    """
    from homeassistant.helpers.service import (  # noqa: PLC0415
        async_extract_referenced_entity_ids,
    )

    return async_extract_referenced_entity_ids(hass, call)


def _has_target_selection() -> bool:
    """Return True if the modern ``TargetSelection`` API is available."""
    try:
        from homeassistant.helpers.target import TargetSelection  # noqa: F401, PLC0415
    except ImportError:  # pragma: no cover - only on HA < 2026.1.0
        return False
    return True


# Select the resolution strategy once, at import time, based on the running HA.
if _has_target_selection():
    extract_referenced_entity_ids = _extract_via_target
else:  # pragma: no cover - exercised only on HA < 2026.1.0
    extract_referenced_entity_ids = _extract_via_service


def _extract_excluded_via_target(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Resolve the target's ``exclude`` block using the target helper (HA >= 2026.11.0)."""
    from homeassistant.helpers.target import (  # noqa: PLC0415
        TargetSelection,
        async_extract_excluded_entity_ids,
    )

    return async_extract_excluded_entity_ids(hass, TargetSelection(call.data))


def _no_excluded_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Return an empty set: the helper that resolves ``exclude`` needs HA >= 2026.11.0."""
    return set()


def _has_exclude_helper() -> bool:
    """Return True if HA can resolve a target's ``exclude`` block."""
    try:
        from homeassistant.helpers.target import (  # noqa: F401, PLC0415
            async_extract_excluded_entity_ids,
        )
    except ImportError:
        return False
    return True


if _has_exclude_helper():
    extract_excluded_entity_ids = _extract_excluded_via_target
else:  # pragma: no cover - exercised only on HA < 2026.11.0
    extract_excluded_entity_ids = _no_excluded_entity_ids
