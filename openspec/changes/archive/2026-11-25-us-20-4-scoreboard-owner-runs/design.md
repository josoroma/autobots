# Design

## Context

The executor starts a session for any hosts it is given, and the guard says what a page did.

## Goals / Non-Goals

**Goals:** US-20.4's scenarios.

**Non-Goals:** judging a site's terms, and opening any address the owner didn't name.

## Decisions

**B1. The same box.** Each opening is one executor session for that address's site, with the guard and, on the stealth browser, Z7's challenge hosts and Z8's wait.

**B2. `blocked` is an answer, `error` is none.** A document status of 400 or more is `blocked`. No answer is `error`. A check outranks both.

**B3. Images, not qualification.** It is the owner's own look at addresses they name, so it needs the images and Docker, and refuses to start without them.

## Risks / Trade-offs

- **One opening is one moment.** A site may answer differently tomorrow, or after many openings from one address.
