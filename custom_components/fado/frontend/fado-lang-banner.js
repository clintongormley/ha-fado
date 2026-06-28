/**
 * Translation-request banner. Shown only when the user's HA language is not
 * covered (intersection of backend + frontend catalogs) and hasn't been
 * dismissed for that locale. Its audience always lacks a catalog for their
 * language, so the copy renders in the English fallback — expected.
 *
 * lit-element 2.4.0 has no willUpdate; state is resolved in update() before
 * super.update(), off the per-render path.
 */
import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

import {
  getLanguageSupport,
  languageDisplayName,
  buildTranslationRequestUrl,
  splitMessageParts,
  isLangRequestDismissed,
  persistDismissedLangRequest,
} from "./fado-logic.js";

import { defaultLocalize } from "./fado-i18n.js";

const PRODUCT = "Fado Light Fader";

class FadoLangBanner extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      localize: { attribute: false },
    };
  }

  constructor() {
    super();
    this.localize = defaultLocalize;
    this._view = null;
    this._dismissedCode = null;
  }

  update(changedProperties) {
    if (changedProperties.has("hass")) this._resolve();
    super.update(changedProperties);
  }

  _resolve() {
    const { available, code } = getLanguageSupport(this.hass);
    if (
      available ||
      !code ||
      this._dismissedCode === code ||
      isLangRequestDismissed(code)
    ) {
      this._view = null;
      return;
    }
    const displayName = languageDisplayName(code);
    this._view = {
      code,
      displayName,
      url: buildTranslationRequestUrl(code, displayName),
    };
  }

  _dismiss(e) {
    e.stopPropagation();
    if (!this._view) return;
    this._dismissedCode = this._view.code;
    persistDismissedLangRequest(this._view.code);
    this._view = null;
    this.requestUpdate();
  }

  render() {
    if (!this._view) return html``;
    const { displayName, url } = this._view;
    const parts = splitMessageParts(this.localize("language_request.message"), {
      language: displayName,
      product: PRODUCT,
    });
    return html`
      <div class="banner" role="status">
        <span class="globe" aria-hidden="true">🌐</span>
        <span class="msg">
          ${parts.map((p) =>
            "bold" in p ? html`<strong>${p.bold}</strong>` : p.text,
          )}
        </span>
        <a class="action" href=${url} target="_blank" rel="noopener noreferrer">
          ${this.localize("language_request.action")}
        </a>
        <ha-icon-button
          class="dismiss"
          .label=${this.localize("language_request.dismiss")}
          @click=${this._dismiss}
        >
          <ha-icon icon="mdi:close"></ha-icon>
        </ha-icon-button>
      </div>
    `;
  }

  static get styles() {
    return css`
      .banner {
        display: flex;
        align-items: center;
        gap: var(--fado-space-3, 12px);
        padding: var(--fado-space-2, 8px) var(--fado-space-4, 16px);
        margin-bottom: var(--fado-space-4, 16px);
        border: 1px solid var(--fado-border, var(--divider-color));
        border-left: var(--fado-space-1, 4px) solid
          var(--fado-accent, var(--primary-color, #03a9f4));
        border-radius: var(--fado-radius, 8px);
        background: var(
          --fado-surface-2,
          var(--secondary-background-color, rgba(0, 0, 0, 0.05))
        );
        color: var(--fado-text, var(--primary-text-color));
        font-size: var(--fado-font-md, 14px);
      }
      .globe {
        font-size: 18px;
        line-height: 1;
      }
      .msg {
        flex: 1;
      }
      .action {
        color: var(--fado-accent, var(--primary-color, #03a9f4));
        font-weight: 500;
        text-decoration: none;
        white-space: nowrap;
      }
      .action:hover {
        text-decoration: underline;
      }
      .dismiss {
        color: var(--fado-text-muted, var(--secondary-text-color));
        --mdc-icon-button-size: 36px;
        --mdc-icon-size: 18px;
      }
    `;
  }
}

if (!customElements.get("fado-lang-banner")) {
  customElements.define("fado-lang-banner", FadoLangBanner);
}
