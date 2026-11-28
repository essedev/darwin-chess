"""Which sessions read the files of which long jobs, derived from the agent's tool calls.

Nothing records that a later session used a job's output: the agent just reads
`/jobs/<id>/...`. The link is read back from the paths in its commands, so it holds as long
as the agent works on the job's own folder. Text inside a heredoc is data the agent writes
(its notes mention the paths too), so it does not count as reading the job.
"""

import json
import re
from collections.abc import Iterable
from typing import Any

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from darwin.ledger import models as m

JOB_PATH = re.compile(r"/jobs/(\d+)\b")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b", re.DOTALL)


def jobs_in_call(payload: dict[str, Any]) -> set[int]:
    """The job ids whose folder a tool call touches, heredoc bodies left out."""
    args = payload.get("args")
    text = args if isinstance(args, str) else json.dumps(args)
    if isinstance(args, dict) and isinstance(args.get("command"), str):
        text = json.dumps({**args, "command": HEREDOC.sub("", args["command"])})
    return {int(n) for n in JOB_PATH.findall(text)}


async def readers(
    s: AsyncSession, experiment_ids: Iterable[int] | None = None
) -> dict[int, set[int]]:
    """Experiment id -> the jobs it read, for `experiment_ids` or every experiment. A job's
    own session does not count as reading it, and only jobs that exist do."""
    query = select(m.AgentEvent.experiment_id, m.AgentEvent.payload).where(
        m.AgentEvent.kind == "tool_call", cast(m.AgentEvent.payload, String).contains("/jobs/")
    )
    if experiment_ids is not None:
        query = query.where(m.AgentEvent.experiment_id.in_(list(experiment_ids)))
    found: dict[int, set[int]] = {}
    for experiment_id, payload in await s.execute(query):
        if isinstance(payload, dict):
            found.setdefault(int(experiment_id), set()).update(jobs_in_call(payload))
    ids = {j for jobs in found.values() for j in jobs}
    started_by = {
        int(job_id): int(exp)
        for job_id, exp in await s.execute(
            select(m.Job.id, m.Job.experiment_id).where(m.Job.id.in_(ids))
        )
    }
    return {
        exp: valid
        for exp, jobs in found.items()
        if (valid := {j for j in jobs if j in started_by and started_by[j] != exp})
    }
