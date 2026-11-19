## ADDED Requirements

### Requirement: The plan is pinned through compaction

A compacted call's state block (Decision 0034 C1) SHALL hold the run's current plan, read fresh from its records: the plan's version and each task's ID, title and criteria, marked done or open. It SHALL tell the model to continue that plan, completing open tasks with `complete_task`, and to revise it only with a reason that keeps completed tasks unchanged. A run without a plan SHALL be told it has none.

#### Scenario: A compacted call sees the run's plan
- **GIVEN** a run with plan version 1 of search, collect and write, whose search task is complete
- **WHEN** its state block is built for a compacted call
- **THEN** it lists plan version 1 with search done and collect and write open, each with its title and criteria, and says to continue the plan with complete_task and to revise it only with a reason that keeps completed tasks

#### Scenario: A run without a plan says so
- **GIVEN** a run that hasn't proposed a plan
- **WHEN** its state block is built
- **THEN** it says there is no plan yet, and lists the goal, criteria, tools and paths as before
