/**
 * Shared Fado module — core logic, rendering, and styles used by both
 * the sidebar panel (panel.js) and the Lovelace card (fado-card.js).
 */

import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

import {
  needsSetup,
  areaNeedsSetupCount,
  needsSetupLabel,
  getCheckboxState,
  getExcludeState,
  collapseKeyForArea,
  collapseKeyForLight,
  nativeTransitionsToValue,
  valueToNativeTransitions,
  pruneCollapsedState,
} from "./fado-logic.js";

import { EN, localize, loadCatalog } from "./fado-i18n.js";
import "./fado-lang-banner.js";

// Re-export for consumers
export { LitElement, html, css };

/**
 * Mixin that adds all Fado core behaviour to a LitElement subclass.
 *
 * Usage:
 *   class FadoPanel extends FadoCoreMixin(LitElement) { … }
 */
export const FadoCoreMixin = (superClass) =>
  class extends superClass {
    static get properties() {
      return {
        hass: { type: Object },
        narrow: { type: Boolean },
        panel: { type: Object },
        _data: { type: Object },
        _loading: { type: Boolean },
        _authError: { type: Boolean },
        _collapsed: { type: Object },
        _configureChecked: { type: Object },
        _testing: { type: Object },
        _testErrors: { type: Object },
        _globalMinDelayMs: { type: Number },
        _entryId: { type: String },
        _compact: { type: Boolean, reflect: true, attribute: "compact" },
        _catalog: { type: Object },
      };
    }

    static get styles() {
      return [fadoTokens, fadoStyles];
    }

    constructor() {
      super();
      this._data = null;
      this._loading = true;
      this._authError = false;
      this._collapsed = this._loadCollapsedState();
      this._configureChecked = new Set();
      this._testing = new Set();
      this._testErrors = new Map();
      this._globalMinDelayMs = 100;
      this._entryId = null;
      this._lastConnection = null;
      this._compact = false;
      this._resizeObserver = null;
      this._catalog = null;
      this._catalogLang = null;
    }

    // ── Lifecycle ──────────────────────────────────────────────

    connectedCallback() {
      super.connectedCallback();
      if (this.hass) {
        this._fetchAll();
        this._subscribeConfigUpdates();
        this._maybeLoadCatalog();
      }
      this._locationChangedHandler = () => {
        if (this._data && !this._isTesting()) {
          this._initConfigureChecked();
        }
      };
      window.addEventListener("location-changed", this._locationChangedHandler);
      this._resizeObserver = new ResizeObserver((entries) => {
        const width = entries[0]?.contentRect?.width ?? 0;
        const compact = width > 0 && width < 720;
        if (compact !== this._compact) this._compact = compact;
      });
      this._resizeObserver.observe(this);
    }

    disconnectedCallback() {
      super.disconnectedCallback();
      if (this._locationChangedHandler) {
        window.removeEventListener("location-changed", this._locationChangedHandler);
        this._locationChangedHandler = null;
      }
      if (this._fetchTimeout) {
        clearTimeout(this._fetchTimeout);
      }
      this._cleanupAutoconfigure();
      if (this._configUpdateUnsub) {
        this._configUpdateUnsub();
        this._configUpdateUnsub = null;
      }
      if (this._entityRegUnsub) {
        this._entityRegUnsub();
        this._entityRegUnsub = null;
      }
      if (this._deviceRegUnsub) {
        this._deviceRegUnsub();
        this._deviceRegUnsub = null;
      }
      if (this._resizeObserver) {
        this._resizeObserver.disconnect();
        this._resizeObserver = null;
      }
    }

    updated(changedProperties) {
      super.updated(changedProperties);
      if (changedProperties.has("hass") && this.hass) {
        this._maybeLoadCatalog();
        const isReconnect =
          this._lastConnection && this._lastConnection !== this.hass.connection;
        this._lastConnection = this.hass.connection;

        if (isReconnect) {
          this._cleanupAutoconfigure();
          this._configUpdateUnsub = null;
          this._entityRegUnsub = null;
          this._deviceRegUnsub = null;
          this._subscribeConfigUpdates();
          this._fetchAll();
          return;
        }

        this._subscribeConfigUpdates();

        if (!this._data && this._loading) {
          this._fetchAll();
        }
      }
    }

    // ── Data fetching ──────────────────────────────────────────

    _debouncedFetch() {
      if (this._fetchTimeout) {
        clearTimeout(this._fetchTimeout);
      }
      this._fetchTimeout = setTimeout(async () => {
        await this._fetchLightsQuiet();
      }, 1000);
    }

    async _subscribeConfigUpdates() {
      if (this._configUpdateUnsub || !this.hass) return;
      try {
        this._configUpdateUnsub = await this.hass.connection.subscribeEvents(
          () => this._debouncedFetch(),
          "fado_config_updated",
        );
      } catch {
        // Subscription may fail if connection is not ready
      }

      if (!this._entityRegUnsub) {
        try {
          this._entityRegUnsub = await this.hass.connection.subscribeEvents((ev) => {
            const data = ev.data;
            if (data && data.entity_id && data.entity_id.startsWith("light.")) {
              this._debouncedFetch();
            }
          }, "entity_registry_updated");
        } catch {
          // Subscription may fail if connection is not ready
        }
      }
      if (!this._deviceRegUnsub) {
        try {
          this._deviceRegUnsub = await this.hass.connection.subscribeEvents(
            () => this._debouncedFetch(),
            "device_registry_updated",
          );
        } catch {
          // Subscription may fail if connection is not ready
        }
      }
    }

    async _fetchAll() {
      await Promise.all([this._fetchSettings(), this._fetchLights()]);
      await this._enforceGlobalMinimum(this._globalMinDelayMs);
    }

    async _fetchSettings() {
      try {
        const result = await this.hass.callWS({ type: "fado/get_settings" });
        this._globalMinDelayMs = result.default_min_delay_ms;
        this._entryId = result.entry_id || null;
      } catch (err) {
        // Non-admins are not allowed to read Fado config; _fetchLights renders
        // the "administrator access required" notice, so stay quiet here.
        if (err?.code === "unauthorized") return;
        console.error("Failed to fetch settings:", err);
      }
    }

    async _fetchLights() {
      this._loading = true;
      try {
        const result = await this.hass.callWS({ type: "fado/get_lights" });
        this._data = result;
        this._authError = false;
        this._initCollapsedState();
        this._initConfigureChecked();
        this._fetchRetries = 0;
      } catch (err) {
        // Fado config is admin-only: a non-admin user (e.g. the card on a
        // shared dashboard) gets "unauthorized". Show a clear notice instead
        // of retrying — retries would never succeed.
        if (err?.code === "unauthorized") {
          this._authError = true;
          this._loading = false;
          return;
        }
        console.error("Failed to fetch lights:", err);
        this._fetchRetries = (this._fetchRetries || 0) + 1;
        if (this._fetchRetries <= 5) {
          const delay = Math.min(1000 * 2 ** (this._fetchRetries - 1), 15000);
          console.log(`[Fado] Retrying fetch in ${delay}ms (attempt ${this._fetchRetries}/5)`);
          this._fetchTimeout = setTimeout(() => this._fetchAll(), delay);
          return;
        }
      }
      this._loading = false;
    }

    async _fetchLightsQuiet() {
      try {
        const result = await this.hass.callWS({ type: "fado/get_lights" });
        if (!result || !result.areas) return;
        this._mergeData(result);
      } catch (err) {
        if (err?.code === "unauthorized") return;
        console.error("Failed to fetch lights:", err);
      }
    }

    // ── State management ───────────────────────────────────────

    _loadCollapsedState() {
      const STORAGE_VERSION = 3;
      try {
        const stored = JSON.parse(localStorage.getItem("fado_collapsed") || "{}");
        if (stored._version !== STORAGE_VERSION) {
          localStorage.removeItem("fado_collapsed");
          return {};
        }
        return stored;
      } catch {
        return {};
      }
    }

    _saveCollapsedState() {
      const toSave = { ...this._collapsed, _version: 3 };
      localStorage.setItem("fado_collapsed", JSON.stringify(toSave));
    }

    _initCollapsedState() {
      // Prune keys for areas/lights that no longer exist, then seed defaults
      // for current ones — keeps the persisted fado_collapsed blob bounded.
      const newCollapsed = pruneCollapsedState(this._collapsed, this._data);
      if (this._data && this._data.areas) {
        for (const area of this._data.areas) {
          const areaKey = collapseKeyForArea(area);
          if (!(areaKey in newCollapsed)) {
            newCollapsed[areaKey] = true;
          }
          for (const light of area.lights) {
            const lightKey = collapseKeyForLight(light.entity_id);
            if (!(lightKey in newCollapsed)) {
              newCollapsed[lightKey] = true;
            }
          }
        }
      }
      this._collapsed = newCollapsed;
    }

    _initConfigureChecked() {
      const toCheck = new Set();
      if (this._data && this._data.areas) {
        for (const area of this._data.areas) {
          for (const light of area.lights) {
            if (needsSetup(light)) {
              toCheck.add(light.entity_id);
            }
          }
        }
      }
      this._configureChecked = toCheck;
    }

    _mergeData(newData) {
      if (this._data && JSON.stringify(this._data) === JSON.stringify(newData)) {
        return;
      }

      const existingLightIds = new Set();
      if (this._data && this._data.areas) {
        for (const area of this._data.areas) {
          for (const light of area.lights) {
            existingLightIds.add(light.entity_id);
          }
        }
      }

      this._data = newData;
      this._initCollapsedState();

      const newLightIds = new Set();
      for (const area of newData.areas) {
        for (const light of area.lights) {
          newLightIds.add(light.entity_id);
        }
      }

      const updatedChecked = new Set();
      for (const id of this._configureChecked) {
        if (newLightIds.has(id)) {
          updatedChecked.add(id);
        }
      }
      for (const area of newData.areas) {
        for (const light of area.lights) {
          if (!existingLightIds.has(light.entity_id) && needsSetup(light)) {
            updatedChecked.add(light.entity_id);
          }
        }
      }
      this._configureChecked = updatedChecked;
    }

    // ── Configuration / event handlers ─────────────────────────

    _toggleCollapse(key) {
      this._collapsed = {
        ...this._collapsed,
        [key]: !this._collapsed[key],
      };
      this._saveCollapsedState();
    }

    async _saveConfig(entityId, field, value) {
      try {
        await this.hass.callWS({
          type: "fado/save_light_config",
          entity_id: entityId,
          [field]: value,
        });
      } catch (err) {
        console.error("Failed to save config:", err);
      }
    }

    async _saveGlobalMinDelay(value) {
      try {
        await this.hass.callWS({
          type: "fado/save_settings",
          default_min_delay_ms: value,
        });
        this._globalMinDelayMs = value;
        await this._enforceGlobalMinimum(value);
      } catch (err) {
        console.error("Failed to save global min delay:", err);
      }
    }

    async _enforceGlobalMinimum(globalMin) {
      if (!this._data?.areas) return;
      for (const area of this._data.areas) {
        for (const light of area.lights) {
          if (light.min_delay_ms && light.min_delay_ms < globalMin) {
            light.min_delay_ms = globalMin;
            await this._saveConfig(light.entity_id, "min_delay_ms", globalMin);
          }
        }
      }
      this.requestUpdate();
    }

    _handleGlobalDelayChange(e) {
      const value = e.target.value ? parseInt(e.target.value, 10) : null;
      if (value && value >= 50 && value <= 2000) {
        this._saveGlobalMinDelay(value);
      }
    }

    _handleDelayChange(entityId, e) {
      let value = e.target.value ? parseInt(e.target.value, 10) : null;
      if (value !== null && value < this._globalMinDelayMs) {
        value = this._globalMinDelayMs;
        e.target.value = value;
      }
      const light = this._findLight(entityId);
      if (light) {
        light.min_delay_ms = value;
      }
      this._saveConfig(entityId, "min_delay_ms", value);
    }

    _handleCheckboxChange(entityId, field, e) {
      const checked = e.target.checked;
      this._saveConfig(entityId, field, checked);

      if (field === "exclude") {
        const light = this._findLight(entityId);
        if (light) {
          light.exclude = checked;
        }
        const newSet = new Set(this._configureChecked);
        if (checked) {
          newSet.delete(entityId);
        } else {
          if (light && !light.min_delay_ms) {
            newSet.add(entityId);
          }
        }
        this._configureChecked = newSet;
        this.requestUpdate();
      }
    }

    _findLight(entityId) {
      if (!this._data || !this._data.areas) {
        return null;
      }
      for (const area of this._data.areas) {
        for (const light of area.lights) {
          if (light.entity_id === entityId) {
            return light;
          }
        }
      }
      return null;
    }

    _handleConfigureChange(entityId, e) {
      const newSet = new Set(this._configureChecked);
      if (e.target.checked) {
        newSet.add(entityId);
      } else {
        newSet.delete(entityId);
      }
      this._configureChecked = newSet;
    }

    _openLightDialog(entityId) {
      const event = new CustomEvent("hass-more-info", {
        bubbles: true,
        composed: true,
        detail: { entityId },
      });
      this.dispatchEvent(event);
    }

    _getAreaLightIds(area) {
      return area.lights.filter((light) => !light.exclude).map((light) => light.entity_id);
    }

    _getAllLightIds() {
      if (!this._data || !this._data.areas) {
        return [];
      }
      const entityIds = [];
      for (const area of this._data.areas) {
        for (const light of area.lights) {
          if (!light.exclude) {
            entityIds.push(light.entity_id);
          }
        }
      }
      return entityIds;
    }

    _getCheckboxState(entityIds) {
      return getCheckboxState(entityIds, this._configureChecked);
    }

    _handleAreaCheckboxChange(area, e) {
      e.stopPropagation();
      const entityIds = this._getAreaLightIds(area);
      const currentState = this._getCheckboxState(entityIds);
      const newSet = new Set(this._configureChecked);

      if (currentState === "all") {
        for (const id of entityIds) newSet.delete(id);
      } else {
        for (const id of entityIds) newSet.add(id);
      }
      this._configureChecked = newSet;
    }

    _handleAllLightsCheckboxChange() {
      const entityIds = this._getAllLightIds();
      const currentState = this._getCheckboxState(entityIds);
      const newSet = new Set(this._configureChecked);

      if (currentState === "all") {
        for (const id of entityIds) newSet.delete(id);
      } else {
        for (const id of entityIds) newSet.add(id);
      }
      this._configureChecked = newSet;
    }

    _getExcludeState(lights) {
      return getExcludeState(lights);
    }

    async _handleAreaExcludeChange(area, e) {
      e.stopPropagation();
      const currentState = this._getExcludeState(area.lights);
      const newExclude = currentState !== "all";

      const newConfigureSet = new Set(this._configureChecked);
      for (const light of area.lights) {
        light.exclude = newExclude;
        await this._saveConfig(light.entity_id, "exclude", newExclude);
        if (newExclude) {
          newConfigureSet.delete(light.entity_id);
        }
      }
      this._configureChecked = newConfigureSet;
      this.requestUpdate();
    }

    // ── Autoconfigure ──────────────────────────────────────────

    _getButtonText() {
      const c = this._configureChecked.size;
      return c > 0
        ? this._t("actions.autoconfigure_count", { count: c })
        : this._t("actions.autoconfigure");
    }

    _isTesting() {
      return this._testing.size > 0;
    }

    _getTestingText() {
      const c = this._testing.size;
      return this._t(c === 1 ? "actions.configuring_one" : "actions.configuring_other", {
        count: c,
        done: this._completedTests,
        total: this._totalToTest,
      });
    }

    _isButtonDisabled() {
      return this._configureChecked.size === 0 || this._testing.size > 0;
    }

    async _runAutoconfigure() {
      const entityIds = Array.from(this._configureChecked);
      if (entityIds.length === 0) return;

      this._testErrors = new Map();
      this._totalToTest = entityIds.length;
      this._completedTests = 0;

      try {
        console.log("[Fado] Starting autoconfigure for", entityIds.length, "lights:", entityIds);
        const unsub = await this.hass.connection.subscribeMessage(
          (event) => this._handleAutoconfigureEvent(event),
          { type: "fado/autoconfigure", entity_ids: entityIds },
          { resubscribe: false },
        );
        this._autoconfigureUnsub = unsub;
        console.log("[Fado] Autoconfigure subscription created (resubscribe=false)");
      } catch (err) {
        console.error("[Fado] Failed to start autoconfigure:", err);
        this._testing = new Set();
      }
    }

    _cleanupAutoconfigure() {
      if (this._autoconfigureUnsub) {
        this._autoconfigureUnsub();
        this._autoconfigureUnsub = null;
      }
      this._testing = new Set();
    }

    _handleAutoconfigureEvent(event) {
      console.log("[Fado] Autoconfigure event:", event.type, event.entity_id || "");
      if (event.type === "started") {
        const newTesting = new Set(this._testing);
        newTesting.add(event.entity_id);
        this._testing = newTesting;
      } else if (event.type === "result") {
        const newTesting = new Set(this._testing);
        newTesting.delete(event.entity_id);
        this._testing = newTesting;
        this._completedTests++;
        this._updateLightConfig(event.entity_id, event.min_delay_ms, event.native_transitions, event.min_brightness);
        const newChecked = new Set(this._configureChecked);
        newChecked.delete(event.entity_id);
        this._configureChecked = newChecked;
      } else if (event.type === "error") {
        const newTesting = new Set(this._testing);
        newTesting.delete(event.entity_id);
        this._testing = newTesting;
        this._completedTests++;
        const newErrors = new Map(this._testErrors);
        newErrors.set(event.entity_id, event.message);
        this._testErrors = newErrors;
        const newChecked = new Set(this._configureChecked);
        newChecked.delete(event.entity_id);
        this._configureChecked = newChecked;
      }

      if (this._testing.size === 0 && this._configureChecked.size === 0) {
        this._cleanupAutoconfigure();
      }
    }

    _updateLightConfig(entityId, minDelayMs, nativeTransitions, minBrightness) {
      if (!this._data?.areas) return;
      for (const area of this._data.areas) {
        const light = area.lights.find((l) => l.entity_id === entityId);
        if (light) {
          light.min_delay_ms = minDelayMs;
          if (nativeTransitions !== undefined) light.native_transitions = nativeTransitions;
          if (minBrightness !== undefined) light.min_brightness = minBrightness;
          this.requestUpdate();
          return;
        }
      }
    }

    async _handleNativeTransitionsValue(entityId, value) {
      const nativeTransitions = valueToNativeTransitions(value);
      const light = this._findLight(entityId);
      if (light) light.native_transitions = nativeTransitions;
      await this._saveConfig(entityId, "native_transitions", nativeTransitions);
    }

    async _downloadDiagnostics() {
      if (!this._entryId) return;
      try {
        const resp = await fetch(
          `/api/diagnostics/config_entry/${this._entryId}`,
          { headers: { Authorization: `Bearer ${this.hass.auth.data.access_token}` } }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `fado-${this._entryId}.json`;
        a.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Failed to download diagnostics:", err);
      }
    }

    // ── i18n ───────────────────────────────────────────────────

    _t(key, params) {
      return localize(this._catalog, EN, key, params);
    }

    async _maybeLoadCatalog() {
      const lang =
        this.hass?.locale?.language ?? this.hass?.language ?? "en";
      if (lang === this._catalogLang) return;
      this._catalogLang = lang;
      const cat = await loadCatalog(lang); // null -> EN fallback
      // Ignore a superseded load (language changed again while awaiting).
      if (lang === this._catalogLang) this._catalog = cat;
    }

    _nativeTransitionsOptions() {
      return [
        { value: "", label: "" },
        { value: "true", label: this._t("native_transitions.yes") },
        { value: "false", label: this._t("native_transitions.no") },
        { value: "disable", label: this._t("native_transitions.disable") },
      ];
    }

    // ── Rendering ──────────────────────────────────────────────

    _renderHeader() {
      const isTesting = this._isTesting();
      return html`
        <div class="header-row">
          <h1>${this._t("header.title")}</h1>
        </div>
        <div class="controls-row">
          ${isTesting
            ? html`<ha-button unelevated disabled>
                <span class="button-spinner"></span>${this._getTestingText()}
              </ha-button>`
            : html`<ha-button
                unelevated
                ?disabled=${this._isButtonDisabled()}
                @click=${this._runAutoconfigure}
              >${this._getButtonText()}</ha-button>`
          }
        </div>
      `;
    }

    _renderContent() {
      if (!this.hass || this._loading) {
        return html`
          <div class="header-row">
            <h1>${this._t("header.title")}</h1>
          </div>
          <div class="loading-container">
            <div class="spinner"></div>
            <span>${this._t("states.loading")}</span>
          </div>
        `;
      }

      if (this._authError) {
        return html`
          <div class="header-row">
            <h1>${this._t("header.title")}</h1>
          </div>
          <div class="auth-error">
            <ha-icon icon="mdi:shield-lock-outline"></ha-icon>
            <p>${this._t("states.auth_error")}</p>
          </div>
        `;
      }

      if (!this._data || !this._data.areas) {
        return html`${this._renderHeader()}<p>${this._t("states.no_lights_found")}</p>`;
      }

      const totalLights = this._data.areas.reduce((sum, area) => sum + area.lights.length, 0);
      if (totalLights === 0) {
        return html`
          <div class="header-row">
            <h1>${this._t("header.title")}</h1>
          </div>
          <div class="empty-state">
            <ha-icon icon="mdi:lightbulb-off-outline"></ha-icon>
            <div class="empty-message">${this._t("states.no_active_lights")}</div>
          </div>
        `;
      }

      return html`
        <fado-lang-banner
          class="lang-banner"
          .hass=${this.hass}
          .localize=${(k, p) => this._t(k, p)}
        ></fado-lang-banner>
        ${this._renderHeader()}
        ${this._compact ? this._renderCardView() : this._renderTableView()}
      `;
    }

    _renderSettingsCard() {
      return html`
        <ha-card>
          <div class="settings-row">
            <label>${this._t("settings.global_min_delay")}</label>
            ${this._renderNumberInput({
              value: this._globalMinDelayMs || "",
              min: 50, max: 2000, step: 10, suffix: this._t("units.ms"),
              onChange: (e) => this._handleGlobalDelayChange(e),
            })}
            <span class="hint">${this._t("settings.global_min_delay_hint")}</span>
          </div>
          ${this._entryId ? html`
            <div class="settings-row">
              <a href="#" @click=${(e) => { e.preventDefault(); this._downloadDiagnostics(); }}>
                <ha-icon icon="mdi:download" style="--mdc-icon-size: 18px; vertical-align: middle; margin-right: 4px;"></ha-icon>${this._t("settings.download_diagnostics")}
              </a>
            </div>
          ` : ""}
        </ha-card>
      `;
    }

    _renderTableView() {
      const allIds = this._getAllLightIds();
      const allState = this._getCheckboxState(allIds);
      return html`
        <ha-card>
          <table class="lights-table">
            <thead>
              <tr>
                <th class="col-light"></th>
                <th class="col-delay">${this._t("table.min_delay")}</th>
                <th class="col-min-brightness">${this._t("table.min_brightness")}</th>
                <th class="col-native-transitions">${this._t("table.native_transitions")}</th>
                <th class="col-exclude">${this._t("labels.exclude")}</th>
                <th class="col-configure">
                  <ha-checkbox
                    .checked=${allState === "all"}
                    .indeterminate=${allState === "some"}
                    @change=${() => this._handleAllLightsCheckboxChange()}
                  ></ha-checkbox>
                </th>
              </tr>
            </thead>
            <tbody>
              ${this._data.areas.map((area) => this._renderAreaRows(area))}
            </tbody>
          </table>
        </ha-card>
        ${this._renderSettingsCard()}
      `;
    }

    _renderCardView() {
      return html`
        ${this._data.areas.map((area) => this._renderAreaCard(area))}
        ${this._renderSettingsCard()}
      `;
    }

    _renderAreaCard(area) {
      const areaKey = collapseKeyForArea(area);
      const isCollapsed = this._collapsed[areaKey];
      const areaIcon = area.icon || "mdi:texture-box";
      const setupLabel = needsSetupLabel(areaNeedsSetupCount(area), (k, p) => this._t(k, p));
      const areaLightIds = this._getAreaLightIds(area);
      const configureState = this._getCheckboxState(areaLightIds);
      const excludeState = this._getExcludeState(area.lights);
      return html`
        <ha-card class="area-card">
          <div class="area-card-header" @click=${() => this._toggleCollapse(areaKey)}>
            <ha-icon class="chevron ${isCollapsed ? "collapsed" : ""}" icon="mdi:chevron-down"></ha-icon>
            <ha-icon class="header-icon" icon="${areaIcon}"></ha-icon>
            <span class="area-name">${area.name}</span>
            ${setupLabel ? html`<span class="needs-setup-rollup">· ${setupLabel}</span>` : ""}
            <span class="spacer"></span>
            <span class="area-card-check" @click=${(e) => e.stopPropagation()}>
              <span class="mini-label">${this._t("labels.exclude")}</span>
              <ha-checkbox
                .checked=${excludeState === "all"}
                .indeterminate=${excludeState === "some"}
                @change=${(e) => this._handleAreaExcludeChange(area, e)}
              ></ha-checkbox>
            </span>
            <span class="area-card-check" @click=${(e) => e.stopPropagation()}>
              <span class="mini-label">${this._t("labels.configure")}</span>
              <ha-checkbox
                .checked=${configureState === "all"}
                .indeterminate=${configureState === "some"}
                @change=${(e) => this._handleAreaCheckboxChange(area, e)}
              ></ha-checkbox>
            </span>
          </div>
          ${isCollapsed
            ? ""
            : area.lights.length > 0
              ? area.lights.map((light) => this._renderLightCard(light))
              : html`<div class="no-lights card-no-lights">${this._t("states.no_lights_in_area")}</div>`}
        </ha-card>
      `;
    }

    _renderLightCard(light) {
      const lightKey = collapseKeyForLight(light.entity_id);
      const isCollapsed = this._collapsed[lightKey];
      const lightIcon = light.icon || "mdi:lightbulb";
      const state = this.hass.states[light.entity_id];
      const isOn = state && state.state === "on";
      const isTesting = this._testing.has(light.entity_id);
      const errorMessage = this._testErrors.get(light.entity_id);
      const isExcluded = light.exclude;
      const flagSetup = needsSetup(light);
      return html`
        <div class="light-card ${isExcluded ? "excluded" : ""}">
          <div class="light-card-header" @click=${() => this._toggleCollapse(lightKey)}>
            <ha-icon class="chevron ${isCollapsed ? "collapsed" : ""}" icon="mdi:chevron-down"></ha-icon>
            <ha-icon class="light-icon ${isOn ? "on" : ""}" icon="${lightIcon}"></ha-icon>
            <div class="light-info">
              <div class="light-name">${light.name}</div>
              <div class="light-substatus">
                ${flagSetup
                  ? html`<span class="needs-setup">● ${this._t("status.needs_setup")}</span>`
                  : html`<span class="entity-id">${light.min_delay_ms ? `${light.min_delay_ms} ms` : light.entity_id}</span>`}
              </div>
            </div>
            <span class="spacer"></span>
            <span class="light-card-check" @click=${(e) => e.stopPropagation()}>
              <ha-checkbox
                ?disabled=${isTesting || isExcluded}
                .checked=${this._configureChecked.has(light.entity_id)}
                @change=${(e) => this._handleConfigureChange(light.entity_id, e)}
              ></ha-checkbox>
            </span>
          </div>
          ${isCollapsed ? "" : html`
            <div class="light-card-body">
              <div class="field-row" @click=${() => this._openLightDialog(light.entity_id)}>
                <span class="field-label">${this._t("card.entity")}</span>
                <span class="entity-id">${light.entity_id}</span>
              </div>
              <div class="field-row">
                <span class="field-label">${this._t("card.min_delay")}</span>
                ${isTesting
                  ? html`<div class="testing-spinner"><div class="spinner"></div></div>`
                  : html`${this._renderNumberInput({
                      value: light.min_delay_ms || "",
                      min: this._globalMinDelayMs, max: 2000, step: 10,
                      disabled: isExcluded, suffix: this._t("units.ms"),
                      onChange: (e) => this._handleDelayChange(light.entity_id, e),
                    })}`}
              </div>
              ${errorMessage ? html`<div class="test-error">${errorMessage}</div>` : ""}
              <div class="field-row">
                <span class="field-label">${this._t("card.min_brightness")}</span>
                <span>${light.min_brightness != null ? light.min_brightness : "—"}</span>
              </div>
              <div class="field-row">
                <span class="field-label">${this._t("card.native_transitions")}</span>
                ${this._renderSelect({
                  value: nativeTransitionsToValue(light.native_transitions),
                  disabled: isExcluded,
                  options: this._nativeTransitionsOptions(),
                  onChange: (value) => this._handleNativeTransitionsValue(light.entity_id, value),
                })}
              </div>
              <div class="field-row">
                <span class="field-label">${this._t("labels.exclude")}</span>
                <ha-checkbox
                  .checked=${light.exclude}
                  @change=${(e) => this._handleCheckboxChange(light.entity_id, "exclude", e)}
                ></ha-checkbox>
              </div>
            </div>
          `}
        </div>
      `;
    }

    _renderAreaRows(area) {
      const areaKey = collapseKeyForArea(area);
      const isCollapsed = this._collapsed[areaKey];
      const areaIcon = area.icon || "mdi:texture-box";
      const areaLightIds = this._getAreaLightIds(area);
      const configureState = this._getCheckboxState(areaLightIds);
      const excludeState = this._getExcludeState(area.lights);
      const setupLabel = needsSetupLabel(areaNeedsSetupCount(area), (k, p) => this._t(k, p));

      return html`
        <tr class="area-row" @click=${() => this._toggleCollapse(areaKey)}>
          <td colspan="2">
            <div class="group-cell">
              <ha-icon class="chevron ${isCollapsed ? "collapsed" : ""}" icon="mdi:chevron-down"></ha-icon>
              <ha-icon class="header-icon" icon="${areaIcon}"></ha-icon>
              ${area.name}
              ${setupLabel ? html`<span class="needs-setup-rollup">· ${setupLabel}</span>` : ""}
            </div>
          </td>
          <td class="col-min-brightness"></td>
          <td class="col-native-transitions"></td>
          <td class="col-exclude">
            <ha-checkbox
              .checked=${excludeState === "all"}
              .indeterminate=${excludeState === "some"}
              @click=${(e) => e.stopPropagation()}
              @change=${(e) => this._handleAreaExcludeChange(area, e)}
            ></ha-checkbox>
          </td>
          <td class="col-configure">
            <ha-checkbox
              .checked=${configureState === "all"}
              .indeterminate=${configureState === "some"}
              @click=${(e) => e.stopPropagation()}
              @change=${(e) => this._handleAreaCheckboxChange(area, e)}
            ></ha-checkbox>
          </td>
        </tr>
        ${isCollapsed
          ? ""
          : area.lights.length > 0
            ? area.lights.map((light) => this._renderLightRow(light))
            : html`<tr><td colspan="6" class="no-lights">${this._t("states.no_lights_in_area")}</td></tr>`}
      `;
    }

    _renderSelect({ value, options, disabled, onChange }) {
      // ha-select is the modern HA control; fall back to a native <select>
      // on much-older HA that hasn't registered it yet.
      if (customElements.get("ha-select")) {
        return html`
          <ha-select
            naturalMenuWidth
            ?disabled=${disabled}
            .value=${value}
            @selected=${(e) => {
              e.stopPropagation();
              const newValue = e.target.value;
              if (newValue !== undefined && newValue !== value) onChange(newValue);
            }}
            @closed=${(e) => e.stopPropagation()}
          >
            ${options.map(
              (o) => html`<ha-list-item .value=${o.value}>${o.label}</ha-list-item>`,
            )}
          </ha-select>
        `;
      }
      return html`
        <select
          ?disabled=${disabled}
          .value=${value}
          @change=${(e) => onChange(e.target.value)}
        >
          ${options.map(
            (o) => html`<option value=${o.value} ?selected=${o.value === value}>${o.label}</option>`,
          )}
        </select>
      `;
    }

    _renderNumberInput({ value, min, max, step, placeholder, disabled, suffix, onChange }) {
      // ha-textfield is being phased out in HA in favor of ha-input as part of
      // the migration from Material Design to Web Awesome. Pick whichever is
      // registered so the field renders on both old and new HA versions.
      if (customElements.get("ha-input")) {
        return html`
          <ha-input
            type="number"
            min="${min}"
            max="${max}"
            step="${step}"
            placeholder="${placeholder || ""}"
            ?disabled=${disabled}
            .value=${value}
            @change=${onChange}
          >${suffix ? html`<span slot="end">${suffix}</span>` : ""}</ha-input>
        `;
      }
      return html`
        <ha-textfield
          type="number"
          min="${min}"
          max="${max}"
          step="${step}"
          placeholder="${placeholder || ""}"
          suffix="${suffix || ""}"
          ?disabled=${disabled}
          .value=${value}
          @change=${onChange}
        ></ha-textfield>
      `;
    }

    _renderLightRow(light) {
      const lightIcon = light.icon || "mdi:lightbulb";
      const state = this.hass.states[light.entity_id];
      const isOn = state && state.state === "on";
      const isTesting = this._testing.has(light.entity_id);
      const errorMessage = this._testErrors.get(light.entity_id);
      const isExcluded = light.exclude;

      return html`
        <tr class="light-row ${isExcluded ? "excluded" : ""}">
          <td class="col-light" style="padding-left: 24px;">
            <div class="light-cell" @click=${() => this._openLightDialog(light.entity_id)}>
              <ha-icon class="light-icon ${isOn ? "on" : ""}" icon="${lightIcon}"></ha-icon>
              <div class="light-info">
                <div class="light-name">${light.name}</div>
                <div class="entity-id">${light.entity_id}</div>
              </div>
            </div>
          </td>
          <td class="col-delay">
            ${isTesting
              ? html`<div class="testing-spinner"><div class="spinner"></div></div>`
              : html`
                  ${this._renderNumberInput({
                    value: light.min_delay_ms || "",
                    min: this._globalMinDelayMs,
                    max: 2000,
                    step: 10,
                    disabled: isExcluded,
                    onChange: (e) => this._handleDelayChange(light.entity_id, e),
                  })}
                  ${errorMessage ? html`<div class="test-error">${errorMessage}</div>` : ""}
                `
            }
          </td>
          <td class="col-min-brightness">
            ${light.min_brightness != null ? light.min_brightness : ""}
          </td>
          <td class="col-native-transitions">
            ${this._renderSelect({
              value: nativeTransitionsToValue(light.native_transitions),
              disabled: isExcluded,
              options: this._nativeTransitionsOptions(),
              onChange: (value) =>
                this._handleNativeTransitionsValue(light.entity_id, value),
            })}
          </td>
          <td class="col-exclude">
            <ha-checkbox
              .checked=${light.exclude}
              @change=${(e) => this._handleCheckboxChange(light.entity_id, "exclude", e)}
            ></ha-checkbox>
          </td>
          <td class="col-configure">
            <ha-checkbox
              ?disabled=${isTesting || isExcluded}
              .checked=${this._configureChecked.has(light.entity_id)}
              @change=${(e) => this._handleConfigureChange(light.entity_id, e)}
            ></ha-checkbox>
          </td>
        </tr>
      `;
    }
  };

// ── Shared styles ────────────────────────────────────────────

export const fadoTokens = css`
  :host {
    /* Colour — mapped to HA theme vars with real fallbacks */
    --fado-accent: var(--primary-color, #03a9f4);
    --fado-warning: var(--warning-color, #e09112);
    --fado-error: var(--error-color, #db4437);
    --fado-on: var(--amber-color, #ffc107);
    --fado-on-accent: var(--text-primary-color, #fff);
    --fado-text: var(--primary-text-color);
    --fado-text-muted: var(--secondary-text-color);
    --fado-border: var(--divider-color);
    --fado-surface: var(--card-background-color);
    --fado-surface-2: var(--secondary-background-color, rgba(0, 0, 0, 0.05));
    --fado-disabled: var(--disabled-text-color);

    /* Structural — fixed but overridable */
    --fado-space-1: 4px;
    --fado-space-2: 8px;
    --fado-space-3: 12px;
    --fado-space-4: 16px;
    --fado-space-5: 24px;
    --fado-space-6: 32px;
    --fado-radius: 8px;
    --fado-radius-sm: 4px;
    --fado-font-sm: var(--ha-font-size-s, var(--paper-font-caption_-_font-size, 12px));
    --fado-font-md: var(--ha-font-size-m, var(--paper-font-body1_-_font-size, 14px));
    --fado-font-lg: 20px;
    --fado-font-h1: var(--ha-card-header-font-size, 24px);
    --fado-font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, sans-serif));
    --fado-control-height: 40px;
  }
`;

export const fadoStyles = css`
  :host {
    display: block;
    padding: 16px;
    max-width: 1200px;
    margin: 0 auto;
    font-family: var(--fado-font-family);
    font-size: var(--fado-font-md);
    color: var(--fado-text);
  }

  h1 {
    margin: 0;
    font-size: var(--fado-font-h1);
    font-weight: 400;
    color: var(--fado-text);
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .header h1 { margin: 0; }

  ha-card {
    display: block;
    margin-bottom: 16px;
    overflow-x: auto;
  }

  ha-button { --mdc-theme-primary: var(--fado-accent); }
  ha-button[disabled] { --mdc-theme-primary: var(--fado-disabled); }

  .settings-row {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 16px;
  }

  .settings-row label { font-weight: 500; color: var(--fado-text); }

  .settings-row ha-textfield,
  .settings-row ha-input {
    width: 140px;
    --mdc-text-field-fill-color: transparent;
  }

  .settings-row .hint {
    font-size: var(--fado-font-sm);
    color: var(--fado-text-muted);
  }

  ha-select { --mdc-menu-min-width: 120px; min-width: 120px; }
  td.col-native-transitions ha-select { min-width: 110px; }

  .header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .controls-row {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    margin-bottom: 16px;
  }

  .chevron {
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.15s ease-in-out;
    --mdc-icon-size: 24px;
    color: var(--fado-text-muted);
    margin-right: 8px;
  }

  .chevron.collapsed { transform: rotate(-90deg); }

  .header-icon { margin-right: 8px; --mdc-icon-size: 20px; }

  .lights-table { width: 100%; border-collapse: collapse; }

  .lights-table th,
  .lights-table td {
    padding: 8px 16px;
    border-bottom: 1px solid var(--fado-border);
  }

  .lights-table th {
    text-align: left;
    font-size: var(--fado-font-sm);
    font-weight: 500;
    color: var(--fado-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .lights-table th.col-configure { text-align: center; }

  .col-light { width: auto; min-width: 200px; }
  .col-delay { width: 120px; text-align: center; }
  .col-min-brightness { width: 100px; text-align: center; }
  .col-exclude { width: 80px; text-align: center; }
  .col-configure { width: 80px; text-align: center; }

  .lights-table td.col-delay,
  .lights-table td.col-min-brightness,
  .lights-table td.col-exclude,
  .lights-table td.col-configure { text-align: center; }

  ha-textfield,
  ha-input { width: 120px; --mdc-text-field-fill-color: transparent; }

  ha-checkbox { --mdc-checkbox-unchecked-color: var(--fado-text-muted); }

  .area-row td {
    background: var(--fado-surface-2);
    font-size: var(--fado-font-md);
    font-weight: 500;
    color: var(--fado-text);
    cursor: pointer;
    user-select: none;
    height: 48px;
    padding: 0 16px;
  }

  .group-cell { display: flex; align-items: center; }

  .light-row td { background: transparent; }

  .light-cell { display: flex; align-items: center; cursor: pointer; }
  .light-cell:hover { opacity: 0.8; }

  .light-icon { margin-right: 12px; --mdc-icon-size: 24px; color: var(--fado-text-muted); }
  .light-icon.on { color: var(--fado-on); }

  .light-info { overflow: hidden; }

  .light-name {
    font-size: var(--fado-font-md);
    font-weight: 500;
    color: var(--fado-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .entity-id {
    font-size: var(--fado-font-sm);
    color: var(--fado-text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  input[type="number"] {
    width: 80px;
    padding: 4px 8px;
    border: 1px solid var(--fado-border);
    border-radius: var(--fado-radius-sm);
    background: var(--fado-surface);
    color: var(--fado-text);
  }

  input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }

  .hidden { display: none; }
  .no-lights { color: var(--fado-text-muted); }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 16px;
    color: var(--fado-text-muted);
  }

  .empty-state ha-icon { --mdc-icon-size: 64px; margin-bottom: 16px; opacity: 0.5; }
  .empty-state .empty-message { font-size: var(--fado-font-lg); font-weight: 400; }

  .testing-spinner { display: flex; justify-content: center; align-items: center; }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--fado-border);
    border-top-color: var(--fado-accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .loading-container {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 24px 16px;
    color: var(--fado-text-muted);
    font-size: var(--fado-font-md);
  }

  .auth-error {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 24px 16px;
    color: var(--fado-text-muted);
    font-size: var(--fado-font-md);
  }

  .auth-error ha-icon {
    color: var(--fado-text-muted);
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .button-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid color-mix(in srgb, var(--fado-on-accent) 30%, transparent);
    border-top-color: var(--fado-on-accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    display: inline-block;
    vertical-align: middle;
    margin-right: 8px;
  }

  .test-error {
    color: var(--fado-error);
    font-size: var(--fado-font-sm);
    margin-top: 4px;
  }

  .light-row.excluded td { opacity: 0.5; }
  .light-row.excluded td.col-exclude { opacity: 1; }

  .col-native-transitions { width: 130px; text-align: center; }

  .settings-row a {
    color: var(--fado-accent);
    text-decoration: none;
    font-size: var(--fado-font-md);
    cursor: pointer;
  }

  .settings-row a:hover { text-decoration: underline; }

  /* Card view (compact / narrow) */
  .area-card { margin-bottom: var(--fado-space-4); }
  .area-card-header {
    display: flex; align-items: center; gap: var(--fado-space-2);
    padding: var(--fado-space-3) var(--fado-space-4);
    background: var(--fado-surface-2); cursor: pointer; user-select: none;
    font-weight: 500;
  }
  .area-card-header .area-name { font-weight: 500; }
  .needs-setup-rollup { color: var(--fado-warning); font-size: var(--fado-font-sm); }
  .spacer { flex: 1; }
  .area-card-check, .light-card-check { display: flex; align-items: center; }
  .mini-label { font-size: var(--fado-font-sm); color: var(--fado-text-muted); margin-right: var(--fado-space-1); }

  .light-card { border-top: 1px solid var(--fado-border); }
  .light-card.excluded .light-card-body,
  .light-card.excluded .light-name { opacity: 0.5; }
  .light-card-header {
    display: flex; align-items: center; gap: var(--fado-space-2);
    padding: var(--fado-space-2) var(--fado-space-4); cursor: pointer;
  }
  .light-substatus { font-size: var(--fado-font-sm); color: var(--fado-text-muted); }
  .needs-setup { color: var(--fado-warning); }
  .light-card-body { padding: 0 var(--fado-space-4) var(--fado-space-3) var(--fado-space-4); }
  .field-row {
    display: flex; align-items: center; justify-content: space-between;
    gap: var(--fado-space-3); padding: var(--fado-space-1) 0;
    min-height: var(--fado-control-height);
  }
  .field-label { color: var(--fado-text-muted); }
  .card-no-lights { padding: var(--fado-space-3) var(--fado-space-4); }

  :host([compact]) { padding: var(--fado-space-3); --fado-control-height: 44px; }
  :host([compact]) .controls-row { flex-direction: column; align-items: stretch; gap: var(--fado-space-2); }
  :host([compact]) .controls-row ha-button { width: 100%; }
  :host([compact]) .header-row { margin-bottom: var(--fado-space-3); }
  :host([compact]) .settings-row { flex-wrap: wrap; gap: var(--fado-space-2); padding: var(--fado-space-3); }
  :host([compact]) .settings-row ha-textfield,
  :host([compact]) .settings-row ha-input { width: 100%; }
  :host([compact]) .field-row ha-select,
  :host([compact]) .field-row ha-input,
  :host([compact]) .field-row ha-textfield { min-width: 140px; }
  :host([compact]) ha-checkbox { --mdc-checkbox-ripple-size: 44px; }
`;
