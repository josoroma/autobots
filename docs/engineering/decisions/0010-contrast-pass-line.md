# Decision 0010: WCAG 2.1 AA is the contrast pass line

**Date:** 2026-11-06. **Authority:** the owner, who answered US-11.11's open question: "Yes, WCAG 2.1 AA".

## Decision

The design PRD asks for accessible contrast and names no ratio. WCAG 2.1 AA is the pass line for US-11.11's measurements, which is what the browser suites' axe checks already apply:

- 4.5:1 for normal text, and 3:1 for large text.
- 3:1 for what a person needs to see a control and its state, such as a focus indicator or an input's boundary.

## What this doesn't change

DS-04 still applies. A combination that fails is corrected first in its pairing, focus, label or structure, and a token value changes only by a recorded proposal.
