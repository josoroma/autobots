-- US-23.7, Decision 0041 A7 and A18: Bonsai 2.5's local route was qualified again on 2026-11-27 with US-3.4's runner and suite,
-- 39 calls in three trials at US$0.00, against the owner's llama-server on this Mac, once the route held each required or named
-- tool call to a JSON schema itself (A18). Plain text, automatic and required tool calls, flat structured output and streamed text
-- passed in all three trials, so the route is qualified with limits, and the Local source offers the profile. Migration 69's row is
-- updated in place, as migration 50 updated Sol's.
-- Locks: ROW EXCLUSIVE on agent_runtime.route_qualifications while one row is updated; four rows in all, so milliseconds.
-- Data: rewrites Bonsai 2.5's one row, only for its own canonical ID.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
update agent_runtime.route_qualifications
set status = 'qualified_with_limits',
    qualified_on = '2026-11-27',
    configuration = 'Served as bonsai-2.5-27b-q2_0 by llama-server 1.1.0 (b12774-171527522) on this Mac''s loopback, 64K context, one slot, '
                    'Q2_0 weights with SHA-256 84496171ca79d4d33fb45612a2afd8303ec494baf916281023b7dc9cb3b3b9fa. Thinking off by '
                    'enable_thinking false, no key, no retries, 512 output tokens, 1,800 seconds a call. A required or named tool call is '
                    'held to a JSON schema for one call by the route (Decision 0041 A18). Measured on an M3 Pro for US-23.2 with the same '
                    'server, weights and flags: reading 71, 55 and 40 and writing 11.4, 7.3 and 4.4 tokens a second at 8K, 32K and 64K, '
                    'and a peak footprint of 10.2 GB.',
    limits = 'Not passed in every trial, so disabled: schema_nested passed 0 of 3. Its plan parsed in each trial, but the place it was '
             'asked to copy lost its quoted word. Required and named tool calls pass because the route holds them to a JSON schema, '
             'not because llama.cpp enforces them. Three trials per fixture, which says nothing about task quality. Concurrent '
             'admission on a live route wasn''t tested.',
    evidence = 'US-23.2, US-23.7'
where profile = 'local_bonsai_2_5_27b'
  and canonical_id = 'prism-ml/Ternary-Bonsai-2.5-27B-GGUF@28a7093cc25bc151cc2b284c5570f12ce343fdcf/Ternary-Bonsai-2.5-27B-Q2_0.gguf';
