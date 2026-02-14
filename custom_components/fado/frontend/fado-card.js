/**
 * Fado Lovelace card — thin wrapper around the shared FadoCoreMixin.
 *
 * Lovelace sets the `hass` property on card elements and calls
 * `setConfig()` with the card YAML config.
 */

import { FadoCoreMixin, LitElement, html } from "./fado-common.js";

class FadoCard extends FadoCoreMixin(LitElement) {
  setConfig(_config) {
    // No user-configurable options for now
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return {
      columns: "full",
      min_columns: 6,
      min_rows: 3,
    };
  }

  render() {
    return this._renderContent();
  }
}

customElements.define("fado-card", FadoCard);

// Register with the Lovelace card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "fado-card",
  name: "Fado Light Fader",
  description: "Configure light fading delays and exclusions for the Fado integration.",
});
