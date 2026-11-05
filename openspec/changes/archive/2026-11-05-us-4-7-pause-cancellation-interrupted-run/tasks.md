## 1. Control

- [x] 1.1 Implement cancellation with unsettled work and its propagation to the loop (Cancel any nonterminal run)
- [x] 1.2 Preserve wait context across pause, and bindings across resume (Resume only paused work)
- [x] 1.3 Classify interrupted work before any dispatch (Recover after sleep or loss)

## 2. Fixtures

- [x] 2.1 Run late-result and competing completion and cancellation fixtures (Cancel any nonterminal run)
- [x] 2.2 Run sleep and retry fixtures with a stopped process (Recover after sleep or loss)
- [x] 2.3 Test readiness and linked runs through the API (Resume only paused work)
