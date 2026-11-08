# Tasks

## 1. Shipped record (The shipped count can't drift)

- [x] 1.1 Record the shipped migration count and newest name, with a check that they match the directory

## 2. Readiness (Fewer applied migrations is behind; All applied is ready; More applied is ahead, not blocking)

- [x] 2.1 Compare the applied count in readiness, with schema_behind and schema_ahead

## 3. Required objects (Newer objects are required without a history)

- [x] 3.1 Extend the required relations and columns through migration 49

## 4. Operations and coverage

- [x] 4.1 Show applied against shipped in Operations, and cover the scenarios on a disposable stack
