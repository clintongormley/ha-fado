// Node 26 exposes `localStorage` as a non-functional global (requires
// --localstorage-file). Vitest's populateGlobal skips happy-dom's localStorage
// because the key already exists in globalThis. Replace it with an in-memory
// implementation so dismissal-set and other storage tests work.
if (typeof localStorage === "undefined" || !localStorage || !("setItem" in (localStorage ?? {}))) {
  const store = Object.create(null);
  const impl = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (n) => Object.keys(store)[n] ?? null,
    get length() { return Object.keys(store).length; },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: impl,
    writable: true,
    configurable: true,
  });
}
