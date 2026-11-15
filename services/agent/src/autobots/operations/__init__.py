"""Process entry points, operator commands and paid qualification, with the process configuration
they share in `composition.py` (Decision 0029 F6). The API's own entry, `api/main.py`, builds from
`composition.py` too. No layer below imports this package, apart from the cronjob tool's lazy
credential check."""
