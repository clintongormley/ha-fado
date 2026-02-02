import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class FadeLightsPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      panel: { type: Object },
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
      }
      h1 {
        margin: 0 0 16px 0;
        font-size: 24px;
        font-weight: 400;
      }
    `;
  }

  render() {
    return html`
      <h1>Fade Lights</h1>
      <p>Panel loaded successfully. Lights will appear here.</p>
    `;
  }
}

customElements.define("fade-lights-panel", FadeLightsPanel);
