# Tasks

## 1. Worker (Result deltas, ephemeral and coalesced; Nothing private is streamed)

- [x] 1.1 Emit ephemeral, coalesced `result.text.delta` events for the final result's text only, on the live stream and never into durable events

## 2. Contract and consumer (Result deltas; Reconnect rebuilds from the artifact)

- [x] 2.1 Add the event type to the typed union, the generated client and the consumer in the same change, with the consumer ignoring unknown types

## 3. Preference (The preference turns live text off)

- [x] 3.1 Add the "Stream text as it's written" preference to Appearance, and honor it in the run view

## 4. Coverage

- [x] 4.1 Cover the scenarios with a scripted model on a disposable stack, including a scan for reasoning, tool arguments and secrets
