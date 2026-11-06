# US-12.3 independent review, round 2

`autobots-reviewer`, in a fresh read-only context, over the fixes for round 1. Saved in substance. Nothing was executed by the reviewer.

**Outcome: changes_required.** 3 blocking, 6 nonblocking. F-4 and F-5 read as resolved, and the walk's control exercises the same functions as the real measurement.

| ID | Severity | Finding | What was done |
|---|---|---|---|
| F2-1 | Blocking | Fixing F-1 and F-15 separately made them contradict: the workflow editor said a version with no agent step would start nothing | The disclosure knows whether the chosen version calls a model, and a test holds both cases |
| F2-2 | Blocking | "Change it in settings" was false for an Expert's binding, which outranks settings and which a session pins | It names the Expert's revision and a new session, and a test holds it |
| F2-3 | Blocking | The stray-dispatch case passed for a loopback port or a literal address, as neither is looked up | An audit hook on Python's connects, with a control for each way out |
| F2-4 | Nonblocking | `request_unencodable` wasn't exercised, and might never be reached | A scripted model returning one was run, and the run ends `failed` with nothing reserved after it |
| F2-5 | Nonblocking | The tree case compared the ledger's wire ID, not each request's model | Compared |
| F2-6 | Nonblocking | Every save silently dropped `skills` | A save keeps what the form doesn't edit, and a test holds it |
| F2-7 | Nonblocking | The summary named the wrong base | Corrected |
| F2-8 | Nonblocking | A closed `details`'s own summary was left out of the count, and the control's upward case could pass on another link | Both fixed |
| F2-9 | Nonblocking | "No later child made a tool call" passed with no later child | Asserts one exists |

Outcome line as returned: `outcome: changes_required`
