"""What every qualification script shares: one exception per exit code, the case vocabulary, and one runner
for tests/db child checks (refactor plan R-39).

`errors` holds Refused and Unavailable, `records` the verification classes, model transports, case and
report shapes and the Cases recorder, and `children` the child-check runner. They need only the standard
library and harness_lib, and `errors` and `records` are strictly typed, as the verifier, evidence and
toolchain scripts that import them are (mypy.ini).
"""
