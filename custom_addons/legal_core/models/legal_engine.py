# -*- coding: utf-8 -*-
"""A trusted-caller marker the engine can set and a client cannot forge.

Several models in the suite own fields no client may write directly: the case's
``step_id`` (moving a file must go through the logged engine), a registered
correspondence entry's number, an escalation's frozen facts. The original design
signalled "this write is the engine, stand the guard down" with a **context
key** (``legal_workflow`` / ``legal_allocating_number``). That is unsafe: Odoo
applies a client-supplied ``context`` verbatim on every RPC call
(``service/model.py``), so a caller who knows the key sends
``context={'legal_workflow': True}`` and walks straight through the guard.

The fix is a process-local marker that is never serialised and therefore never
reachable from an RPC payload. Engine methods wrap their privileged mutation in
``engine_guard()``; the model guards ask ``in_engine()``. Because the marker is
thread-local and depth-counted, nested engine calls and concurrent workers stay
correct.
"""

import threading
from contextlib import contextmanager

_state = threading.local()


def in_engine():
    """True only while a call is running inside :func:`engine_guard`."""
    return getattr(_state, "depth", 0) > 0


@contextmanager
def engine_guard():
    """Mark the current call as a trusted engine mutation for its duration."""
    _state.depth = getattr(_state, "depth", 0) + 1
    try:
        yield
    finally:
        _state.depth = max(0, getattr(_state, "depth", 1) - 1)
