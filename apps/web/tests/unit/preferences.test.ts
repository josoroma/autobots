/**
 * The browser preferences' one definition (XWEB-18, WSHL-11): the before-paint script built from it,
 * run against a fake storage and root element, and the read and apply the Appearance control uses.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { runInNewContext } from "node:vm";

import {
  applyPreference,
  beforePaintScript,
  PRESENTATION,
  readPreference,
  storageKey,
  streamWanted,
  THEME_KEY,
} from "../../lib/preferences.ts";

// The before-paint script written out in full. The built one must equal it byte for byte, so first
// paint can't change unnoticed (DS-02).
const WRITTEN_OUT = `try{var s=localStorage,k="autobots.theme",v=s.getItem(k);if(v!==null&&v!=="dark"&&v!=="light"&&v!=="system")s.removeItem(k);var d=document.documentElement;if(s.getItem("autobots.serif")==="off")d.dataset.serif="off";if(s.getItem("autobots.density")==="compact")d.dataset.density="compact";if(s.getItem("autobots.motion")==="reduce")d.dataset.motion="reduce";if(s.getItem("autobots.stream")==="off")d.dataset.stream="off"}catch(e){}`;

function fakeStorage(entries: Record<string, string>) {
  const items = new Map(Object.entries(entries));
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
  };
}

function paint(storage: unknown): Record<string, string | undefined> {
  const dataset: Record<string, string | undefined> = {};
  runInNewContext(beforePaintScript(), {
    localStorage: storage,
    document: { documentElement: { dataset } },
  });
  return dataset;
}

test("the built script is the written-out one, byte for byte", () => {
  assert.equal(beforePaintScript(), WRITTEN_OUT);
});

test("before paint, an allowed theme stays and any other is removed", () => {
  for (const theme of ["dark", "light", "system"]) {
    const storage = fakeStorage({ [THEME_KEY]: theme });
    paint(storage);
    assert.equal(storage.items.get(THEME_KEY), theme);
  }
  const storage = fakeStorage({ [THEME_KEY]: "garbage" });
  paint(storage);
  assert.equal(storage.items.has(THEME_KEY), false);
});

test("before paint, each preference stored as its other value is marked", () => {
  const stored = Object.fromEntries(
    Object.entries(PRESENTATION).map(([name, { attribute }]) => [
      `autobots.${name}`,
      attribute,
    ]),
  );
  assert.deepEqual(paint(fakeStorage(stored)), {
    serif: "off",
    density: "compact",
    motion: "reduce",
    stream: "off",
  });
});

test("before paint, fallbacks and unknown values mark nothing", () => {
  assert.deepEqual(
    paint(
      fakeStorage({
        "autobots.serif": "on",
        "autobots.density": "compat",
        "autobots.motion": "system",
      }),
    ),
    {},
  );
});

test("storage that can't be read changes nothing before paint", () => {
  const throwing = {
    getItem: () => {
      throw new Error("blocked");
    },
  };
  assert.deepEqual(paint(throwing), {});
});

test("the control reads a stored value, or else the fallback", () => {
  const root = { dataset: {} as DOMStringMap };
  const storage = fakeStorage({ "autobots.density": "compact" });
  assert.equal(
    readPreference("density", () => storage, root),
    "compact",
  );
  assert.equal(
    readPreference("serif", () => storage, root),
    "on",
  );
  storage.items.set("autobots.motion", "sideways");
  assert.equal(
    readPreference("motion", () => storage, root),
    "system",
  );
});

test("unreadable storage reads what the page shows", () => {
  const blocked = () => {
    throw new Error("blocked");
  };
  assert.equal(
    readPreference("stream", blocked, { dataset: { stream: "off" } }),
    "off",
  );
  assert.equal(readPreference("stream", blocked, { dataset: {} }), "on");
});

test("applying a value marks the root and stores only a non-fallback", () => {
  const root = { dataset: {} as DOMStringMap };
  const storage = fakeStorage({});
  applyPreference("serif", "off", () => storage, root);
  assert.equal(root.dataset.serif, "off");
  assert.equal(storage.items.get(storageKey("serif")), "off");
  assert.equal(streamWanted(root), true);
  applyPreference("serif", "on", () => storage, root);
  assert.equal(root.dataset.serif, undefined);
  assert.equal(storage.items.has(storageKey("serif")), false);
  applyPreference("stream", "off", () => storage, root);
  assert.equal(streamWanted(root), false);
});

test("storage that can't be written keeps the choice on the page", () => {
  const root = { dataset: {} as DOMStringMap };
  applyPreference(
    "density",
    "compact",
    () => {
      throw new Error("blocked");
    },
    root,
  );
  assert.equal(root.dataset.density, "compact");
});
