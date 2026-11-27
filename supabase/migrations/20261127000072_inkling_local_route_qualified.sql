-- US-23.8, Decision 0041 A7, A11 and A18: Inkling 2 Mini's local route was qualified on 2026-11-27 with US-3.4's runner and suite,
-- 39 calls in three trials at US$0.00, against the owner's llama-server on this Mac, each call at the route's own 8,192-token output
-- cap. Plain text, automatic and required tool calls, flat structured output and streamed text passed in all three trials, so the
-- route is qualified with limits, and the Local source offers the profile beside Bonsai 2.5 ("store it and offer it on local as we
-- are offering bonsai as well").
-- Locks: ROW EXCLUSIVE on agent_runtime.route_qualifications while one row is inserted; four rows in all, so milliseconds.
-- Data: none rewritten. One row is inserted where the profile has none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
insert into agent_runtime.route_qualifications (profile, canonical_id, status, qualified_on, configuration, limits, evidence) values
  ('local_inkling_2_mini',
   'unsloth/Inkling-2-Mini-GGUF@8078d149286eec7193795413b9e0643da6d11fa1/Inkling-2-Mini-UD-Q3_K_XL.gguf',
   'qualified_with_limits', '2026-11-27',
   'Served as inkling-2-mini-ud-q3_k_xl by llama-server 1.1.0 (b12774-171527522) on this Mac''s loopback, 64K context, one slot, '
   'UD-Q3_K_XL weights with SHA-256 e2d03e8c92ac21cff0e3309b95f40dfd27d1825184f0d2bc09db249797273639, temperature 1.0. Reasoning '
   'effort none, though it still reasons, and its reasoning is kept out of the reply. No key, no retries, 8,192 output tokens, '
   '1,800 seconds a call. A required or named tool call is held to a JSON schema for one call by the route (Decision 0041 A18). '
   'Measured by hand for Decision 0041 A15: reading 143, 90 and 53 and writing 19.7, 13.6 and 10.1 tokens a second at 8K, 32K '
   'and 62K, and a peak footprint of 6.7 GB beside 13.6 GB of weights.',
   'Not passed in every trial, so disabled: schema_nested passed 2 of 3. Its one failure dropped the quoted word from the place '
   'it was asked to copy. It reasons before every reply, so each reply needs room: at a 512-token cap the named-tool '
   'counterexample failed in all three trials, and at the route''s 8,192 it passed in all three. Required and named tool calls '
   'pass because the route holds them to a JSON schema, not because llama.cpp enforces them. Three trials per fixture, which '
   'says nothing about task quality. Concurrent admission on a live route wasn''t tested.',
   'US-23.8')
on conflict (profile) do nothing;
