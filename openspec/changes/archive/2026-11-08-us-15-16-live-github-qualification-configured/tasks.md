# Tasks

## 1. Runner (Not run without the owner; One live pass per tool on the owner's repository)

- [x] 1.1 Extend `scripts/qualify_github_connector.py`, in no verification profile, with a `studio` suite covering the read tools, labels and pull requests. It refuses to start without the token and the recorded authorization, and counts every request against the cap
- [x] 1.2 Exercise its refusals offline: no authorization, no token, a repository the authorization doesn't name, and no `--live`. Each refuses with nothing sent

## 2. Live pass (One live pass per tool on the owner's repository)

- [x] 2.1 Run phase `review` and show the owner the pull request's diff
- [x] 2.2 After the owner approves, run phase `apply` once. Record the redacted evidence: the outputs' shapes, the markers, the retry readback and the absence of the token
