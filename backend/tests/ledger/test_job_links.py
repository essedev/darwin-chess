"""Reading which jobs a tool call touches from its arguments."""

import pytest

from darwin.ledger.job_links import jobs_in_call

NOTE = """cd /memory && python3 - <<'EOF'
open('NOTES.md', 'a').write('Job 2 writes /jobs/2/out/games.txt')
EOF
ls /jobs/1/out"""


@pytest.mark.parametrize(
    ("payload", "jobs"),
    [({"tool": "bash", "args": {"command": "tail -c 600 /jobs/1/out/games.txt"}}, {1}),
     ({"tool": "read", "args": {"path": "/jobs/12/out/log.txt"}}, {12}),
     ({"tool": "bash", "args": {"command": NOTE}}, {1}),
     ({"tool": "run_job", "args": {"action": "start",
                                   "command": "python3 tune.py /jobs/3/out/games.txt"}}, {3}),
     ({"tool": "bash", "args": "{'command': 'ls /jobs/4/out'}"}, {4}),
     ({"tool": "bash", "args": {"command": "ls /job/out /jobs"}}, set()),
     ({"tool": "run_job", "args": {"action": "status"}}, set())],
)  # fmt: skip
def test_a_call_touches_the_jobs_whose_folder_it_names(
    payload: dict[str, object], jobs: set[int]
) -> None:
    assert jobs_in_call(payload) == jobs
