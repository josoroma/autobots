# Design

## Context

The worker's guard pauses every request and logs top-frame navigations. Each model request passes `guarded` before admission, which already refuses one after a bot check.

## Goals / Non-Goals

**Goals:** US-20.2's scenarios, on fixtures and the qualification hosts.

**Non-Goals:** solving a check, and a person answering one.

## Decisions

**C1. The wait is at the model request.** Nothing moves between browser-use's cells but a request to the endpoint, so holding it there means no step runs and nothing is pressed.

**C2. Cleared means another page.** A check has cleared when its page session's top frame commits another page that shows none for 2 seconds. A page that shows one again gets no more time.

**C3. Per page session.** A check is kept by the session whose page shows it, so another tab's navigation doesn't clear it.

**C4. The proxy's list is by host, the guard's by role.** The sidecar lets the hosts through, and the guard refuses them as a page.

**C5. Told, not enforced, on a widget.** browser-use's own code drives the browser, so pressing a Turnstile widget can't be told from pressing a button (Z10).

## Risks / Trade-offs

- **A site that moves its check to another address** is seen as an ordinary page, and the model reads it.
