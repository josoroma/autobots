# Tasks

## 1. Guide (Every tool carries a guide; A tool without a guide fails a test)

- [x] 1.1 Write a what, when and why for every registered and planned tool in `domain/tool_guides.py`, and expose it as `guide` in the catalog contract. Regenerate the contract and client
- [x] 1.2 Add a unit test that fails, naming the tool, when its guide is missing or a text is empty

## 2. Modal (Choosing a tool opens its modal; Granted to, Copy schema and the full page; Closing returns focus; Accessible in both themes)

- [x] 2.1 Replace the side panel with a native `dialog` modal holding the guide, the Inputs and Outputs, Granted to, Copy schema and the full-page link, keeping `?tool=<id>`
- [x] 2.2 Close it on Escape, Close or an outside click, returning focus to the tool's link

## 3. Coverage and docs

- [x] 3.1 Update the Tools browser suites, with axe in both themes, and CODEBASE
