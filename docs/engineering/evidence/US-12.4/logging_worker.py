#!/usr/bin/env python3
"""The product worker, unchanged, logging what an uncertain call's exception was. Kept with the evidence.

The product records only the class, `uncertain_acceptance`, so this names the cause for a diagnosis. It adds
no behavior. The key is in no exception here, and the runner's leak check reads these logs too.
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback

from autobots.adapters import loop_middleware
from autobots.operations.worker import main

original = loop_middleware._failure_without_status


def logged(error: Exception):
    cause = error.__cause__ or error.__context__
    print(json.dumps({'event': 'diagnosis.uncertain_cause', 'type': f'{type(error).__module__}.{type(error).__name__}', 'message': str(error)[:400],
                      'cause': type(cause).__name__ if cause else None, 'cause_message': str(cause)[:300] if cause else None,
                      'trace': ''.join(traceback.format_exception(error))[-1800:]}), file=sys.stderr, flush=True)
    return original(error)


loop_middleware._failure_without_status = logged

if __name__ == '__main__':
    asyncio.run(main())
