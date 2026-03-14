import "@testing-library/jest-dom";

// jsdom 28 changed localStorage internals and may not expose .clear() properly.
// Replace with a stable in-memory Storage implementation for all tests.
const _store: Map<string, string> = new Map();
const stableLocalStorage: Storage = {
  getItem: (key: string) => _store.get(key) ?? null,
  setItem: (key: string, value: string) => { _store.set(key, value); },
  removeItem: (key: string) => { _store.delete(key); },
  clear: () => { _store.clear(); },
  get length() { return _store.size; },
  key: (n: number) => [..._store.keys()][n] ?? null,
};

Object.defineProperty(globalThis, "localStorage", {
  value: stableLocalStorage,
  writable: true,
  configurable: true,
});
