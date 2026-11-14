import assert from "node:assert/strict";
import { test } from "node:test";

import { ConfigurationError, configFrom } from "../../lib/server-env.ts";

const COMPLETE = {
  AUTOBOTS_API_URL: "http://127.0.0.1:8101",
  AUTOBOTS_INTERNAL_TOKEN: "internal-value",
  AUTOBOTS_ALLOWED_ORIGIN: "http://127.0.0.1:3100",
  AUTOBOTS_SUPABASE_URL: "http://127.0.0.1:54421",
  AUTOBOTS_SUPABASE_ANON_KEY: "anon-value",
};

function refusal(env: Record<string, string | undefined>): ConfigurationError {
  try {
    configFrom(env);
  } catch (error) {
    if (error instanceof ConfigurationError) return error;
    throw error;
  }
  throw new Error("the configuration was accepted");
}

test("a complete environment is read as it is", () => {
  assert.deepEqual(configFrom(COMPLETE), {
    apiUrl: "http://127.0.0.1:8101",
    internalToken: "internal-value",
    allowedOrigin: "http://127.0.0.1:3100",
    supabaseUrl: "http://127.0.0.1:54421",
    supabaseAnonKey: "anon-value",
  });
});

test("the local addresses have defaults, and the two secrets do not", () => {
  assert.deepEqual(
    configFrom({
      AUTOBOTS_INTERNAL_TOKEN: "internal-value",
      AUTOBOTS_SUPABASE_ANON_KEY: "anon-value",
    }),
    {
      apiUrl: "http://127.0.0.1:8001",
      internalToken: "internal-value",
      allowedOrigin: "http://127.0.0.1:3000",
      supabaseUrl: "http://127.0.0.1:54321",
      supabaseAnonKey: "anon-value",
    },
  );
  assert.deepEqual(refusal({}).variables, [
    "AUTOBOTS_INTERNAL_TOKEN",
    "AUTOBOTS_SUPABASE_ANON_KEY",
  ]);
  assert.deepEqual(
    refusal({
      ...COMPLETE,
      AUTOBOTS_INTERNAL_TOKEN: "",
      AUTOBOTS_SUPABASE_ANON_KEY: "",
    }).variables,
    ["AUTOBOTS_INTERNAL_TOKEN", "AUTOBOTS_SUPABASE_ANON_KEY"],
  );
});

test("the allowed origin must be an exact http(s) origin", () => {
  for (const origin of [
    "127.0.0.1:3000",
    "http://127.0.0.1:3000/",
    "http://127.0.0.1:3000/app",
    "ftp://127.0.0.1",
    "not an origin",
    "",
  ]) {
    assert.deepEqual(
      refusal({ ...COMPLETE, AUTOBOTS_ALLOWED_ORIGIN: origin }).variables,
      ["AUTOBOTS_ALLOWED_ORIGIN"],
      origin,
    );
  }
  assert.deepEqual(
    refusal({
      ...COMPLETE,
      AUTOBOTS_API_URL: "file:///tmp/api",
      AUTOBOTS_SUPABASE_URL: "nowhere",
    }).variables,
    ["AUTOBOTS_API_URL", "AUTOBOTS_SUPABASE_URL"],
  );
});

test("the error names the variables and never a value", () => {
  const error = refusal({
    ...COMPLETE,
    AUTOBOTS_ALLOWED_ORIGIN: "http://origin-value.example/path",
  });
  assert.equal(error.name, "ConfigurationError");
  assert.match(error.message, /AUTOBOTS_ALLOWED_ORIGIN/);
  for (const value of ["internal-value", "anon-value", "origin-value"]) {
    assert.equal(error.message.includes(value), false, value);
  }
});
