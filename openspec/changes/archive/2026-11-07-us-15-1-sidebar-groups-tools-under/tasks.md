# Tasks

## 1. Navigation (Three named groups; The skip link stays first)

- [x] 1.1 Move Tools into the Build group after Workflows in the sidebar, keeping link names, hrefs and the current-page marker
- [x] 1.2 Confirm the skip link stays the first tab stop and Home the first link after it
- [x] 1.3 Name the work group in screen-reader text and label its list, and assert in `tools.spec.ts` that every group is named and that activating the skip link moves focus into the main content

## 2. Specs (The browser specs follow the decision; Browse tools by group)

- [x] 2.1 Update `tools.spec.ts` to assert Tools directly after Workflows under Build, and remove any assertion of Tools before Settings
- [x] 2.2 Run the appearance, boundary and tools suites with axe through the `full` profile
