## REMOVED Requirements

### Requirement: Inflation is annual, sourced and metered

**Reason**: The owner removed `inflation_rates` and the World Bank provider (Decision 0036 R1). No other inflation source replaces it.

**Migration**: `inflation_rates` is a retired tool (`retired-tools`). A saved Expert version or routine that names it runs with its other tools, a revision drops it, and a paused run continues, its call refused with `tool_not_registered`. A run that needs inflation reads a published source with the search and extraction tools, or a file a person attaches.
