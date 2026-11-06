# Tasks

## 1. First sleep (Observe one real sleep)

- [x] 1.1 Write the sleep procedure, with what to observe before and after
- [x] 1.2 Have the owner run it on a disposable stack with a scripted model, and record the observations

## 2. Wake handling (Build wake handling only if the test shows it's needed)

- [x] 2.1 Detect a real sleep from a process's own clocks
- [x] 2.2 Take back a lease that expired with nobody claiming it, with fencing unchanged, and leave the time asleep out of active time

## 3. Second sleep (Prove a fix under real sleep)

- [x] 3.1 Have the owner repeat the test, and record that the failures are gone
