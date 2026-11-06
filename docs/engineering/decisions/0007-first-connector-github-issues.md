# Decision 0007: The first connector creates GitHub issues

**Date:** 2026-11-05. **Authority:** the user asked to fix or implement US-7.2, was asked which service and how to test it, and answered "No preference" to both. This records the recommended option on each question, so it's a delegated choice, not one the user argued for. It can be reversed cheaply until a live run depends on it.

## Decision

- **Service and operation:** one operation, creating an issue in one configured GitHub repository. No other GitHub operation, and the repository isn't something a model can choose.
- **Grant:** an owner opts in per Expert. Goals without an Expert don't get the tool.
- **Approval:** every call needs a person's approval first, as any consequential tool does.
- **Credential:** a fine-grained token limited to that repository's issues, read by the worker per attempt from the environment, and never stored in the database, a checkpoint or evidence.
- **Qualification fixture:** a throwaway private repository the owner creates, with its own token. Nothing else is written to.

## Why

It can be tested for real without touching anything that matters, and an issue can be closed afterwards. GitHub has no idempotency key for this call, so a retry is only safe if the connector can find its own earlier attempt. A marker holding the operation ID goes in the issue body and is read back through the repository's issue list, which is what the story's uncertain-outcome scenario needs to exercise.

## What this gives up

- **Duplicate protection is weaker than a real key:** a call that fails after GitHub accepted it, whose issue isn't yet visible when read back, could be created twice. The approval and the marker make that rare and detectable, but not impossible.
- **No connector catalog, OAuth or credential screen:** those stay later scope, and the token is server configuration.

## What this doesn't establish

That the connector works against GitHub, until a live run against the owner's fixture is recorded. A fake transport can't mark US-7.2 `DONE`, and neither H1 nor product acceptance follows from it.

## Reversal

Remove the tool and its grant. Saved runs that recorded the tool's version would stop as `incompatible_version`, with a linked new run as the way forward. Issues already created stay in the repository.
