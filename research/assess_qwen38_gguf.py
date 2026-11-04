"""Offline interpretation of completed Qwen GGUF probe and server-log evidence.

This never changes raw evidence, performs inference, or controls a process.
The source-backed named-tool correction applies to the reviewed llama.cpp 0.8.0
revision below. Correct output with one available tool does not prove that a
named-tool selection directive was enforced.
"""

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path


REVISION = "8642541b255bfb5dc39cd351a178be09013a55d6"
NAMED_CASE = "native_named_strict_tool_roundtrip"
FALLBACK = re.compile(
    r"Wrong type supplied for parameter ['\"]tool_choice['\"], using default value:"
    r".*type must be string, but is object",
    re.IGNORECASE,
)
SOURCE = {
    "reviewed_runtime": "llama.cpp 0.8.0",
    "revision": REVISION,
    "string_default": "auto",
    "supported_string_choices": ["auto", "none", "required"],
    "request_parsing_url": f"https://github.com/ggml-org/llama.cpp/blob/{REVISION}/tools/server/server-common.cpp#L1360",
    "accepted_choices_url": f"https://github.com/ggml-org/llama.cpp/blob/{REVISION}/common/chat.cpp#L322",
    "applicability": "Source review supplied for this run; this offline script does not inspect the executable.",
}


def assess(probe, log_text):
    if not probe.get("finished_at_utc"):
        raise ValueError("Probe is incomplete: finished_at_utc is required; no assessment written")
    diagnostics = [{"line": n, "text": line} for n, line in enumerate(log_text.splitlines(), 1)
                   if FALLBACK.search(line)]
    object_requests = [r for r in probe.get("requests", [])
                       if isinstance((r.get("payload") or {}).get("tool_choice"), dict)]
    cases = []
    for index, raw in enumerate(probe.get("tests", []), 1):
        raw_pass = raw.get("status") == "pass" and raw.get("ok") is True
        row = {
            "case_number": index, "name": raw.get("name"), "seed": raw.get("seed"),
            "request_ids": raw.get("request_ids", []),
            "raw_status": raw.get("status"), "raw_output_pass": raw_pass,
            "raw_protocol_ok": raw.get("protocol_ok"), "raw_semantic_ok": raw.get("semantic_ok"),
            "raw_failed_checks": [c for c in raw.get("checks", []) if not c.get("ok")],
            "contract_qualified": raw_pass,
            "assessment_status": "qualified" if raw_pass else "skipped" if raw.get("status") == "skipped" else "failed",
            "interpretation": "Raw bounded-case verdict retained; no claim beyond its specified checks.",
        }
        if raw.get("error"):
            row["raw_error"] = raw["error"]
        if raw.get("name") == NAMED_CASE:
            named_requests = [r for r in object_requests if r.get("id") in row["request_ids"]]
            correlated = len(object_requests) == len(named_requests) == len(diagnostics) == 1
            row.update(
                contract_qualified=False,
                correct_response_observed=raw_pass and raw.get("semantic_ok") is True,
                requested_tool_choice=[r["payload"]["tool_choice"] for r in named_requests],
                source_review=SOURCE,
                fallback_diagnostics=diagnostics,
                unique_object_request_and_diagnostic=correlated,
                native_named_enforcement_demonstrated=False,
            )
            if correlated:
                row.update(
                    assessment_status="unsupported",
                    effective_tool_choice="auto",
                    interpretation=("The only object-form tool_choice request corresponds to this case, and the server "
                                    "logged a type error and default fallback. The reviewed source defaults to auto. "
                                    "The correct calculator output is retained, but native named-tool enforcement "
                                    "is unsupported and unqualified. A single available tool plus an explicit prompt "
                                    "cannot distinguish automatic selection from enforced named selection."),
                )
            else:
                row.update(
                    assessment_status="inconclusive" if raw_pass else row["assessment_status"],
                    effective_tool_choice=None,
                    interpretation=("No unique request/diagnostic correlation was established. A matching answer with "
                                    "one available tool does not establish native named-tool enforcement. Raw output "
                                    "results are retained; capability qualification is withheld."),
                )
        cases.append(row)
    if not cases:
        raise ValueError("Completed probe contains no test cases")
    summary = {
        "total_cases": len(cases),
        "raw_output_passed": sum(c["raw_output_pass"] for c in cases),
        "raw_output_failed": sum(c["raw_status"] == "fail" for c in cases),
        **{name: sum(c["assessment_status"] == name for c in cases)
           for name in ("qualified", "unsupported", "failed", "skipped", "inconclusive")},
        "all_cases_qualified": all(c["contract_qualified"] for c in cases),
    }
    return {
        "assessment_created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "probe_finished_at_utc": probe["finished_at_utc"],
        "served_model": probe.get("served_model"),
        "scope": "Offline interpretation of bounded output checks and reviewed runtime behavior; not a general agent benchmark.",
        "raw_evidence_modified": False,
        "raw_report_totals": probe.get("totals"),
        "summary": summary,
        "cases": cases,
        "limitations": [
            "Qualified means the specific bounded case passed; it is not a universal API or model guarantee.",
            "Correct output from a single-tool prompt cannot establish native named-choice enforcement.",
            "Required mode with one allowed tool remains a distinct adapter alternative, not native named-choice support.",
            "A logfile prefix snapshot may precede later benchmark or shutdown log appends.",
            "Existing semantic failures remain failures; this assessment performs no repair or rerun.",
        ],
    }


def self_test():
    probe = {
        "finished_at_utc": "2026-11-04T00:00:00+00:00",
        "requests": [{"id": 3, "payload": {"tool_choice": {"type": "function", "function": {"name": "add_integers"}}}}],
        "tests": [
            {"name": NAMED_CASE, "request_ids": [3, 4], "status": "pass", "ok": True, "semantic_ok": True},
            {"name": "nested_strict_json_schema", "status": "pass", "ok": True},
            {"name": "bounded_two_hop_invoice_audit", "status": "fail", "ok": False, "semantic_ok": False},
        ],
    }
    diagnostic = "W Wrong type supplied for parameter 'tool_choice', using default value: type must be string, but is object"
    result = assess(probe, diagnostic)
    assert result["summary"]["qualified"] == 1
    assert result["summary"]["unsupported"] == 1
    assert result["summary"]["failed"] == 1
    assert result["summary"]["all_cases_qualified"] is False
    named = result["cases"][0]
    assert named["raw_output_pass"] and named["correct_response_observed"]
    assert named["effective_tool_choice"] == "auto" and not named["contract_qualified"]
    assert assess(probe, "")["cases"][0]["assessment_status"] == "inconclusive"
    try:
        assess({"tests": []}, diagnostic)
    except ValueError:
        pass
    else:
        raise AssertionError("Incomplete probe was accepted")
    print("Offline assessment checks passed; no inference or report writes.")


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, default=here / "qwen38-gguf-probe.json")
    parser.add_argument("--server-log", type=Path, default=here / "qwen38-gguf-server.log")
    parser.add_argument("--out", type=Path, default=here / "qwen38-gguf-assessment.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.out.resolve() in (args.probe.resolve(), args.server_log.resolve()):
        parser.error("Output must differ from both raw evidence paths")
    probe_bytes = args.probe.read_bytes()
    probe = json.loads(probe_bytes)
    if not probe.get("finished_at_utc"):
        parser.error("Probe is incomplete: finished_at_utc is required; no assessment written")
    log_bytes = args.server_log.read_bytes()
    result = assess(probe, log_bytes.decode("utf-8", errors="replace"))
    result["inputs"] = {
        "probe": {"path": str(args.probe), "bytes": len(probe_bytes),
                  "original_sha256": hashlib.sha256(probe_bytes).hexdigest()},
        "server_log": {"path": str(args.server_log), "snapshot_bytes": len(log_bytes),
                       "snapshot_sha256": hashlib.sha256(log_bytes).hexdigest(),
                       "hash_scope": "Exact first snapshot_bytes read at assessment time; later appends are outside this hash."},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.out), "summary": result["summary"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
