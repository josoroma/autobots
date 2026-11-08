-- US-15.8, PRD-Studio MD-02: a workspace policy may name no default, so each role without an
-- override takes its built-in default (Sol for researcher once offered, Terra otherwise).
alter table app_private.model_policies alter column default_profile drop not null;
