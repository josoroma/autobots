## Decisions

- **Through the application layer, not SQL**, so every Expert config and workflow graph is validated exactly as a person's would be. The seed acts as the workspace's owner and uses the runtime role.
- **"Bounded upserts with no user-edit overwrites"** means insert only when the name is absent. An existing Expert or workflow is kept as it is, whoever made or edited it. Idempotency keys make a retried write return the first one.
- **What makes a workflow a draft:** SD-02 names the conditions, and the seed follows them. Nightly test triage and Release notes depend on the GitHub tools. Interview synthesis is a draft until executions carry files. The other three are published even when an Expert lost a keyed tool, such as Research analyst without the web-search keys. That Expert's purpose says so, and a run's admission still refuses an unavailable tool.
- **Inputs:** SD-02 lists two inputs for some workflows, such as "competitors, question". An agent's goal is a single text input, so each of these workflows takes one text input that holds both, and its description says what to put in it. Vendor due diligence takes a list and runs one research step per vendor, up to 10.
