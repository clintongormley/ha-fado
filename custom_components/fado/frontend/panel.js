/**
 * Fado sidebar panel — thin wrapper around the shared FadoCoreMixin.
 *
 * Home Assistant sets `hass`, `narrow`, and `panel` properties directly
 * on panel custom elements.
 */

import { FadoCoreMixin, LitElement, html } from "./fado-common.js";

class FadoPanel extends FadoCoreMixin(LitElement) {
  render() {
    return this._renderContent();
  }
}

customElements.define("fado-panel", FadoPanel);
