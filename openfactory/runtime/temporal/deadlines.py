"""How long this deployment waits for its durable engine — read without the engine's client.

ITS OWN MODULE, AND A SMALL ONE (#681, review of #818 on f48b79fd): the healthcheck a container runs
every fifteen seconds asks `health.deadline()`, which follows `OPENFACTORY_ENGINE_DEADLINE`, and
read through `view` it imported the engine's client, the workflows and the activities to read one
variable — measured, 158 ms of the probe's start and most of its 62 MB, in each of two containers.
`view` names the same two functions from here, so the probe and the reads it waits for never
disagree about them.
"""

from __future__ import annotations

import logging
import os

#: The logger `view` says a malformed number through, as it did when these lived there.
log = logging.getLogger("openfactory.panel.temporal")


#: What a READ somebody is waiting for may spend on an engine that is not answering (#159).
#:
#: MEASURED, ON THE REAL STACK. With the engine killed under a running panel — `main` at `98dc177`,
#: so with the pooled client — `/api/floor` took **38.8 s**, `/api/inbox` 8.9 s (and then a 500),
#: `/api/temporal/jobs` 6.3 s: the client retries an unreachable engine (`gRPC call
#: describe_schedule retried 7 times`) before anything gives up. The board's own route stayed at
#: 8 ms and the board still crawled — a tab gets six connections to a host, the page asks for the
#: floor on every engine frame and holds the stream open, so those six fill with requests waiting
#: on retries and every other read queues behind them.
#:
#: WHAT A HEALTHY READ COSTS, so the headroom is a measurement and not a hope (review of #161).
#: On a dev server with the worker running, timed through these functions:
#:
#:     list_jobs, 8 jobs      51 ms median, 80 ms max
#:     list_jobs, 50 jobs     317 ms median, 352 ms max   ← 50 is the panel's own limit
#:     job_detail             8 ms
#:     intake                 5 ms
#:
#: So three seconds is roughly ten times what the panel's largest list costs. The cost grows with
#: the number of RUNNING jobs, because each one is queried for its state — which is also why this
#: bound catches a second real case: a workflow whose worker is gone cannot answer a query at all,
#: and `list_jobs` did not return in 120 s against eight such jobs. It now degrades in three.
#:
#: A NUMBER A DEPLOYMENT CAN CHANGE, because "slow" is a property of somebody's network: a Temporal
#: Cloud namespace across a region answers in tenths of a second, and this must not call that
#: unreachable. Read per call, so an operator changes it without a rebuild.
def read_deadline() -> float:
    return _seconds("OPENFACTORY_ENGINE_DEADLINE", 3.0)


#: How long an engine that did not answer is remembered as unreachable, so the NEXT read does not
#: pay the same wait again. Short on purpose: an engine that came back must be picked up without a
#: restart, which is the rule `connect()` already holds for a failed connect.
def unreachable_window() -> float:
    return _seconds("OPENFACTORY_ENGINE_UNREACHABLE_FOR", 3.0)


def _seconds(name: str, fallback: float) -> float:
    try:
        wanted = float(os.environ.get(name, "") or fallback)
    except ValueError:
        log.warning("%s is not a number (%r) — using %ss", name, os.environ.get(name), fallback)
        return fallback
    return wanted if wanted > 0 else fallback
