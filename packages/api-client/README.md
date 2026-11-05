# @autobots/api-client

`src/generated.ts` is generated from the Pydantic contracts by `scripts/generate_contracts.py` and is never hand-written. `src/runtime.ts` is the hand-written validator behind every generated `parse` function, because a TypeScript type checks nothing at runtime.
