"""The migrations this release ships, Decision 0023 E2. Readiness compares the database's applied
count with this, and a harness check fails unless both values match `supabase/migrations`. Add a
migration, then change both lines.
"""

SHIPPED_MIGRATIONS = 62
NEWEST_MIGRATION = "20261115000062_sol_concurrent_admission_limit.sql"
