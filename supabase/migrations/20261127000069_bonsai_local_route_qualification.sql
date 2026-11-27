-- US-23.2, Decision 0041 A7: Bonsai 2.5's local route was qualified live on 2026-11-27 with US-3.4's runner and suite, 39 calls in
-- three trials at US$0.00, against the owner's llama-server on this Mac. A required tool call failed in all three trials, so the route
-- is not qualified and the profile isn't offered on the Local source. What it found, for Settings to show beside the others.
-- Locks: ROW EXCLUSIVE on agent_runtime.route_qualifications while one row is inserted; four rows in all, so milliseconds.
-- Data: none rewritten. One row is inserted where the profile has none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
insert into agent_runtime.route_qualifications (profile, canonical_id, status, qualified_on, configuration, limits, evidence) values
  ('local_bonsai_2_5_27b',
   'prism-ml/Ternary-Bonsai-2.5-27B-GGUF@28a7093cc25bc151cc2b284c5570f12ce343fdcf/Ternary-Bonsai-2.5-27B-Q2_0.gguf',
   'not_qualified', '2026-11-27',
   'Served as bonsai-2.5-27b-q2_0 by llama-server 1.1.0 (b12774-171527522) on this Mac''s loopback, 64K context, one slot, Q2_0 weights '
   'with SHA-256 84496171ca79d4d33fb45612a2afd8303ec494baf916281023b7dc9cb3b3b9fa. Thinking off by enable_thinking false, no key, '
   'no retries, 512 output tokens, 1,800 seconds a call. Measured on an M3 Pro: reading 71, 55 and 40 and writing 11.4, 7.3 and 4.4 '
   'tokens a second at 8K, 32K and 64K, and a peak footprint of 10.2 GB.',
   'Not passed in every trial, so disabled: schema_nested passed 0 of 3; tool_named_conflict passed 2 of 3; tool_required passed 0 '
   'of 3. llama.cpp 1.1.0 does not enforce a required tool call for this model''s template: it answered in text until its 512 '
   'output tokens ran out. Plain text, automatic tool calls, flat structured output and streamed text passed in all three trials.',
   'US-23.2')
on conflict (profile) do nothing;
