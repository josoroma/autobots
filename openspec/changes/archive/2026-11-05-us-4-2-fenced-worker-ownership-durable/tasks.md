## 1. Ownership

- [x] 1.1 Add the checkpoint tables and the ownership triggers in a migration (Fence both product and checkpoint writes)
- [x] 1.2 Add lease, heartbeat and generation checks by database time (Recover persisted execution)
- [x] 1.3 Add the scoped direct checkpointer (Fence both product and checkpoint writes, Recover persisted execution)

## 2. Failure injection

- [x] 2.1 Inject a stale owner at both boundaries, including a race with a claim (Fence both product and checkpoint writes)
- [x] 2.2 Kill a real worker process and recover from its checkpoint (Recover persisted execution)
