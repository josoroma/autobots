# Tasks

## 1. Loop and page (Each step is an admitted call; An answer that isn't one valid action ends the call)

- [x] 1.1 Implement the loop with the page as text, the four typed actions, refused targets, step and time limits, and `invalid_action`
- [x] 1.2 Implement the CDP page over the executor's session with the locked `websockets` client, adding no package

## 2. Admission (Each step is an admitted call; An uncertain outcome follows the existing rules; No other model path)

- [x] 2.1 Route each step through the middleware's admission on a given route, the model wrapped so it answers only inside an admitted dispatch
- [x] 2.2 Let the inference source bind the run's frozen `researcher` route

## 3. Tool support (Actions are required tool calls, refused on a route lacking tool support)

- [x] 3.1 Require a tool call on every step, and refuse a route whose catalog entry lacks tools before anything is sent

## 4. Coverage

- [x] 4.1 Cover the scenarios offline and on a disposable database with a scripted model and the real middleware
