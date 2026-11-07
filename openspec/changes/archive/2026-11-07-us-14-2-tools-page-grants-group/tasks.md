# Tasks

## 1. Screen (Browse tools by group; Show unavailable tools honestly)

- [x] 1.1 Add the Tools sidebar entry before Settings, and the `/tools` list with URL filters
- [x] 1.2 Add `/tools/{tool_id}` with versions, field tables, key requirement, repair and the JSON Schema disclosure
- [x] 1.3 Cover both scenarios in a browser spec with axe, run by the web qualifier

## 2. Grants (A group grant stays explicit)

- [x] 2.1 Add `tool_groups` to Expert configs, expand them on save and refuse unavailable or empty grants
- [x] 2.2 Drive the Expert editor from the catalog, with whole groups, an expansion preview and disabled unavailable tools
- [x] 2.3 Fix the generator's array-of-union types and regenerate
- [x] 2.4 Cover the scenario in unit tests and the Experts browser spec on a disposable stack
