## Why the pieces are where they are

- **DevTools behind Node.** Chrome binds DevTools to 127.0.0.1 whatever `--remote-debugging-address` says, so a Node supervisor (the image already has Node) forwards the internal network's port 9222 to it and exits when Chrome exits.
- **Full Chrome, not the headless shell.** The Playwright build is Chrome for Testing; neither binary visibly honoured a managed policy, so the policy file was dropped rather than claimed. Schemes, methods and downloads are enforced over CDP by the request guard instead, where the live check observes them.
- **Two networks per session.** The browser's network is internal. The sidecar has its own outbound network, not the default bridge, so Docker's DNS can resolve the browser by name.
- **A host allowlist in the proxy.** Left alone, Chrome contacts Google's update, sign-in and component hosts. Each session names the hosts it may reach, and everything else is refused `host_not_allowed`. The qualification names `example.com` and `example.org`; `browse_goal` will pass its `allowed_domains`.
- **Caps from cgroup counters.** Docker enforces memory and processes, and the watcher reads `memory.events` (`oom_kill`) and `pids.events` (`max`) inside the container, one file at a time since both name a `max` counter.
- **Ownership from the gateway's rule.** `attempt_alive` is `ownership_refusal(...) is None`, so a cancelled run or a lost lease ends a session exactly as it refuses a tool call.
