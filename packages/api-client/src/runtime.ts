// Runtime validation for values crossing a trust boundary. A TypeScript type checks nothing at runtime.

export interface Schema {
  $ref?: string;
  anyOf?: readonly Schema[];
  const?: unknown;
  enum?: readonly unknown[];
  type?: string;
  format?: string;
  pattern?: string;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  items?: Schema;
  properties?: Readonly<Record<string, Schema>>;
  required?: readonly string[];
  additionalProperties?: boolean | Schema;
  [key: string]: unknown;
}

export class ContractError extends Error {
  readonly path: string;

  constructor(path: string, message: string) {
    super(`${path}: ${message}`);
    this.name = "ContractError";
    this.path = path;
  }
}

type Schemas = Readonly<Record<string, Schema>>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

function checkString(schema: Schema, value: string, path: string): void {
  if (schema.format === "uuid" && !UUID.test(value)) {
    throw new ContractError(path, "not a UUID");
  }
  if (schema.format === "date-time" && (!DATE_TIME.test(value) || Number.isNaN(Date.parse(value)))) {
    throw new ContractError(path, "not a timestamp with an offset");
  }
  if (schema.pattern !== undefined && !new RegExp(schema.pattern).test(value)) {
    throw new ContractError(path, "does not match its pattern");
  }
  if (schema.minLength !== undefined && value.length < schema.minLength) {
    throw new ContractError(path, "too short");
  }
  if (schema.maxLength !== undefined && value.length > schema.maxLength) {
    throw new ContractError(path, "too long");
  }
}

function checkNumber(schema: Schema, value: number, path: string): void {
  if (!Number.isFinite(value) || (schema.type === "integer" && !Number.isSafeInteger(value))) {
    throw new ContractError(path, "not an exact integer");
  }
  if ((schema.minimum !== undefined && value < schema.minimum) || (schema.maximum !== undefined && value > schema.maximum)) {
    throw new ContractError(path, "out of range");
  }
}

function checkObject(schemas: Schemas, schema: Schema, value: object, path: string): void {
  const record = value as Record<string, unknown>;
  for (const name of schema.required ?? []) {
    if (!(name in record)) {
      throw new ContractError(`${path}.${name}`, "required");
    }
  }
  for (const [name, item] of Object.entries(record)) {
    const property = schema.properties?.[name];
    if (property !== undefined) {
      check(schemas, property, item, `${path}.${name}`);
    } else if (schema.additionalProperties === false) {
      throw new ContractError(`${path}.${name}`, "not part of the contract");
    }
  }
}

function check(schemas: Schemas, schema: Schema, value: unknown, path: string): void {
  if (schema.$ref !== undefined) {
    const target = schemas[schema.$ref.slice(schema.$ref.lastIndexOf("/") + 1)];
    if (target === undefined) {
      throw new ContractError(path, `unknown schema ${schema.$ref}`);
    }
    check(schemas, target, value, path);
    return;
  }
  if (schema.anyOf !== undefined) {
    for (const option of schema.anyOf) {
      try {
        check(schemas, option, value, path);
        return;
      } catch (error) {
        if (!(error instanceof ContractError)) {
          throw error;
        }
      }
    }
    throw new ContractError(path, "matches no allowed form");
  }
  if ("const" in schema && value !== schema.const) {
    throw new ContractError(path, "not the required value");
  }
  if (schema.enum !== undefined && !schema.enum.includes(value)) {
    throw new ContractError(path, "not an allowed value");
  }
  switch (schema.type) {
    case "string":
      if (typeof value !== "string") throw new ContractError(path, "not a string");
      checkString(schema, value, path);
      return;
    case "integer":
    case "number":
      if (typeof value !== "number") throw new ContractError(path, "not a number");
      checkNumber(schema, value, path);
      return;
    case "boolean":
      if (typeof value !== "boolean") throw new ContractError(path, "not a boolean");
      return;
    case "null":
      if (value !== null) throw new ContractError(path, "not null");
      return;
    case "array":
      if (!Array.isArray(value)) throw new ContractError(path, "not an array");
      value.forEach((item, index) => {
        if (schema.items !== undefined) check(schemas, schema.items, item, `${path}[${index}]`);
      });
      return;
    case "object":
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        throw new ContractError(path, "not an object");
      }
      checkObject(schemas, schema, value, path);
      return;
    default:
      return;
  }
}

export function parseWith(schemas: Schemas, name: string, value: unknown): unknown {
  const schema = schemas[name];
  if (schema === undefined) {
    throw new ContractError(name, "unknown schema");
  }
  check(schemas, schema, value, name);
  return value;
}

export interface ClientOptions {
  baseUrl: string;
  fetch: typeof globalThis.fetch;
  headers?: Record<string, string>;
}

/** Per-call additions: headers such as an Idempotency-Key, and a signal to abort the request. */
export interface RequestOptions {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

/** The service's error body (`ErrorResponse`). The generated parser checks it fully. */
export interface ErrorEnvelope {
  code: string;
  message: string;
}

/**
 * A reply outside 2xx (R-02). `envelope` is the service's error body when the reply carries one, and
 * null otherwise, such as a proxy's page or an empty body. A shape mismatch on success is a
 * `ContractError` instead, so a refusal can be told from contract drift.
 */
export class HttpFailure extends Error {
  readonly status: number;
  readonly envelope: ErrorEnvelope | null;

  constructor(path: string, status: number, envelope: ErrorEnvelope | null) {
    super(`${path}: request failed with status ${status}`);
    this.name = "HttpFailure";
    this.status = status;
    this.envelope = envelope;
  }
}

async function readEnvelope(
  response: Response,
  parseError: ((value: unknown) => ErrorEnvelope) | undefined,
): Promise<ErrorEnvelope | null> {
  if (parseError === undefined) return null;
  const text = await response.text().catch(() => "");
  try {
    return parseError(JSON.parse(text));
  } catch {
    return null;
  }
}

export async function requestJson(
  options: ClientOptions,
  method: string,
  path: string,
  body?: unknown,
  request?: RequestOptions,
  parseError?: (value: unknown) => ErrorEnvelope,
): Promise<unknown> {
  const response = await options.fetch(`${options.baseUrl}${path}`, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
      ...request?.headers,
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    ...(request?.signal === undefined ? {} : { signal: request.signal }),
  });
  if (!response.ok) {
    throw new HttpFailure(path, response.status, await readEnvelope(response, parseError));
  }
  try {
    return (await response.json()) as unknown;
  } catch {
    throw new ContractError(path, "not JSON");
  }
}
