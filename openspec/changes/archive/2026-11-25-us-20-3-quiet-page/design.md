# Design

## Context

Each browser-use step keeps its page, submits and screenshot at the next model request. The screenshots show the highlights, which is how a person sees what was pressed.

## Goals / Non-Goals

**Goals:** US-20.3's scenarios, on fixtures and the qualification hosts.

**Non-Goals:** recording elements inside child frames, and pacing the box.

## Decisions

**Q1. An isolated world.** `Page.addScriptToEvaluateOnNewDocument` with a world name runs before the page and shares no variable with it. Reading it needs `Page.createIsolatedWorld` and `Runtime.evaluate` in that context, and never `Runtime.enable`, which a page can notice. A binding in that world was tried and delivers nothing without `Runtime.enable`.

**Q2. Long polls.** Ten evaluations wait in each page's world, each answered by one touch as it happens, so a press that navigates away isn't lost with its page. Reading at the navigation instead was tried: Chrome holds every command to a page whose navigation is paused. The worker's DevTools client also drops a late reply to a command that timed out, which used to end its reader.

**Q3. Never the typed value.** Values stay in that world. A label that holds one, as a page echoing it would, leaves it empty.

**Q4. A site.** The registrable part of each domain a call names, taken in one order. Reading one label too few only makes two sites share a turn.

**Q5. A session advisory lock** on the attempt's connection, so a lost worker frees it. Two calls of one attempt share that connection, so a site held in the process waits too.

## Risks / Trade-offs

- **A label is the page's own words.** It is third-party text, bounded to 80 characters and shown as text.
- **Main frame only.** A press inside a child frame isn't named.
