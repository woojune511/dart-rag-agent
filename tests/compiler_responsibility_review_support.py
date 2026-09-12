"""Test-only proposal for planning context. Not connected to production prompts.

Assumes the existing planner/requirement gate has accepted the plan. No source,
candidate, accepted answer or execution state is an input to the projection.
"""
from copy import deepcopy
import json

from src.agent.financial_request_units import build_request_units, project_request_units
from tests.semantic_program_test_support import _StructuredQueueLLM


MARKER = 'Output responsibility context (review-only):'
INSTRUCTIONS = (
    'This is planned output responsibility, not source evidence or proof that another output succeeded. '
    'Use it to distinguish the active explanation from separately requested topics. '
    'Retain conditions and relationships needed to make an active answer accurate, even when shared. '
    'Emit only active obligation IDs; select evidence only from their existing visible cohorts. '
    'Do not merge or delete outputs because they share a subject, request, source or wording.'
)
SCOPE_FIELDS = ('company', 'period', 'consolidation_scope', 'segment', 'basis')


def proposed_responsibility_context(query, obligations):
    """Owned, explicit allowlist; preserve plan/query order and exact request text."""
    return {
        'schema': 'output_responsibility_context_proposal_v1',
        'role': 'planning_context_only',
        'outputs': [{
            'obligation_id': row['obligation_id'], 'kind': row['kind'], 'label': row['label'],
            'request_unit_ids': deepcopy(row['request_unit_ids']),
            'local_subjects': deepcopy((row.get('semantic_target') or {}).get('local_subjects') or []),
            'scope': {key: deepcopy(value) for key, value in (row.get('scope') or {}).items()
                      if key in SCOPE_FIELDS},
            'source_sections': deepcopy(row.get('source_sections') or []),
        } for row in obligations],
        'request_units_by_id': project_request_units(build_request_units(query), obligations),
    }


def context_suffix(context):
    if len(context['outputs']) < 2:
        return ''  # No sibling responsibility to explain for a single-output plan.
    return '\n\n' + MARKER + '\n' + json.dumps(context, ensure_ascii=False, separators=(',', ':')) + '\n' + INSTRUCTIONS


class ResponsibilityReviewQueue(_StructuredQueueLLM):
    """Decorate only test-queue input; return the exact supplied authored responses.

    This cannot measure model quality or runtime prompt diagnostics: the production
    prompt builder is deliberately unchanged and sees the undecorated prompt.
    """
    def __init__(self, context, *responses):
        super().__init__(*responses)
        self.context = deepcopy(context)
        self.original_prompts = []

    def invoke(self, prompt):
        self.original_prompts.append(deepcopy(prompt))
        decorated = deepcopy(prompt)
        decorated.messages[-1].content += context_suffix(self.context)
        return super().invoke(decorated)
