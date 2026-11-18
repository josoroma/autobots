## Why

US-15.1, [PRD-Studio SH-01](../../../../docs/PRD/PRD-Studio.md#shell) and [Decision 0022 D2](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision): the owner chose the Studio concepts' navigation, with Tools under **Build**. Decision 0017 C9's "Tools directly before Settings" is amended, and so is Decision 0021 R5's grouping, which put Tools under System to keep that rule.

## What Changes

- The sidebar's groups become the work group (Home, Runs, Approvals), **Build** (Experts, Workflows, Tools) and **System** (Operations, Models, Settings). Link names, hrefs, roles and the current-page marker are unchanged.
- The skip link stays the first tab stop, and Home the first link after it.
- `tools.spec.ts` asserts Tools directly after Workflows, under Build. No spec asserts Tools directly before Settings.

## Capabilities

### New Capabilities

- `studio-shell`: the grouped sidebar navigation.

### Modified Capabilities

- `tool-catalog`: the Tools entry's placement.

## Impact

`apps/web/components/sidebar-nav.tsx` and `apps/web/tests/browser/tools.spec.ts`. No API, contract or migration change.
