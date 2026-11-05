# Fixture product requirements

## Scope
A local Autobots settings screen uses OpenRouter. The application is not built.

## REQ-01 Missing key
When the OpenRouter key is missing, keep the current composer draft and let the owner open Settings. Do not dispatch a model request.

## REQ-02 Local storage
Store application records locally on this Mac. No hosted application database is in scope.

## REQ-03 Retry policy
Show retryable provider failures to the owner. The maximum automatic retry count has not been decided.

## REQ-04 Cancellation
Cancelled runs are terminal and cannot be resumed.

## REQ-05 Resume
A user can resume a cancelled run in place.

## REQ-06 Composer autosave
When the composer draft changes, save the current draft automatically using the local storage required by REQ-02. This behavior cannot be delivered until local storage is delivered.
