# Tasks

## 1. Record and contract (Show each route's stored qualification, Refuse to infer qualification)

- [x] 1.1 Add the `agent_runtime.route_qualifications` table, readable by the runtime role only, with each route's result from US-3.4 in the same migration
- [x] 1.2 Replace `qualification_status` with one entry per approved route, not qualified when no record matches the route's canonical model, and regenerate the clients

## 2. Screens (all three scenarios)

- [x] 2.1 Show each route's record in Settings, apart from authentication and catalog status
- [x] 2.2 Correct the goal composer's message and the tests that pin the old text

## 3. Observe (all three scenarios)

- [x] 3.1 Add a browser suite that the identity qualifier runs after restarting the API, and again with one record removed under a valid key
