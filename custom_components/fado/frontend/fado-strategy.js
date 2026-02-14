/**
 * Fado dashboard strategy.
 *
 * Usage: create a dashboard with raw config:
 *   strategy:
 *     type: custom:fado
 */

class FadoStrategy {
  static async generate(_config, _hass) {
    return {
      title: "Fado",
      views: [
        {
          title: "Light Configuration",
          icon: "mdi:lightbulb-variant",
          panel: true,
          cards: [{ type: "custom:fado-card" }],
        },
      ],
    };
  }
}

customElements.define("ll-strategy-dashboard-fado", FadoStrategy);
