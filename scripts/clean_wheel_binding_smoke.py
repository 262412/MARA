"""Exercise installed candidate policy and legacy binding exports outside source."""

import subprocess
from pathlib import Path


def run_binding_smoke(python: Path, cwd: Path, env: dict[str, str]) -> None:
    validation = """
import os
import sys
from pathlib import Path

assert 'PYTHONPATH' not in os.environ
from ktem.docqa import evidence_binding_policy, query_evidence_binding, query_planning
from ktem.docqa import query_plan_schema
from ktem.docqa.query_evidence_binding_support import score_evidence_for_slot
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan, with_plan_id

prefix = Path(sys.prefix).resolve()
for module in (evidence_binding_policy, query_evidence_binding, query_planning,
               query_plan_schema):
    assert Path(module.__file__).resolve().is_relative_to(prefix), module.__file__
slot = EvidenceSlot('topic', 'support', metric='topic')
plan = with_plan_id(QueryPlan('extractive', 'lookup', evidence_slots=(slot,)))
record = {'evidence_id': 'a', 'source_id': 'paper', 'text': 'topic'}
selected = evidence_binding_policy.candidate_ids_for_slot(
    plan, slot, [(1.0, 0, record)], [], set(), set(), set())
assert selected == ['evidence:paper:a']
bound = query_planning.bind_evidence_slots(plan, [record])
assert type(bound) is QueryPlan and bound.plan_id == plan.plan_id
assert bound.evidence_slots[0].evidence_ids == ('evidence:paper:a',)
assert bound.evidence_slots[0].status == 'filled'
continued, trace = query_planning.bind_evidence_slots_monotonic(bound, [record])
assert continued.as_dict() == bound.as_dict()
assert continued.evidence_slots[0] is bound.evidence_slots[0]
assert trace[0]['slot_id'] == 'topic'
assert query_evidence_binding.score_evidence_for_slot is score_evidence_for_slot
assert query_planning.score_evidence_for_slot(slot, record) == score_evidence_for_slot(slot, record)
print('[wheel-smoke] installed evidence policy, legacy binding and score exports passed')
"""
    subprocess.run([str(python), "-B", "-c", validation], cwd=cwd, env=env, check=True)
