"""Opt-in experiment admission for the runtime's actual compilation groups.

This consumes the existing island builder's result, never diagnostics or an
expected answer. It does not install itself in application defaults or grant
paid execution authority. The enclosing caller still owns question, phase,
transport, whole-run funding and single-use authorization.
"""

from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
from functools import wraps
import hashlib
from unittest.mock import patch

from src.ops.provider_admission import json_bytes


def _amount(value):
    if isinstance(value, bool):
        raise ValueError("invalid compilation budget amount")
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError("invalid compilation budget amount")
    return value


def response_batch_ceiling(policy, model, calls):
    """Full input/output ceilings plus count contingencies; no token measurement."""
    if type(calls) is not int or calls < 0:
        raise ValueError("invalid response count")
    settings = policy["request_settings_by_model"][model]
    inputs, outputs = policy["max_openai_input_tokens"], settings["max_output_tokens"]
    if (type(inputs) is not int or not 0 < inputs <= 200000
            or type(outputs) is not int or outputs <= 0
            or settings.get("model") != model
            or policy.get("openai_input_counting") != "responses_input_tokens_v1"):
        raise ValueError("explicit counted short-context settings required")
    rates = policy["rates"][model]
    allowance = _amount(policy["openai_count_allowance_usd_per_call"])
    if not allowance:
        raise ValueError("positive count contingency required")
    return calls * ((inputs * _amount(rates["input"]) + outputs * _amount(rates["output"]))
                    / Decimal(1000000) + allowance)


class CompilationPlanAdmission:
    """Bound first responses to disjoint runtime groups within an existing budget."""

    def __init__(self, budget, *, compiler_model, max_first_responses):
        if type(max_first_responses) is not int or max_first_responses <= 0:
            raise ValueError("positive first-response limit required")
        self.budget = budget
        self.compiler_model = compiler_model
        self.max_first_responses = max_first_responses
        response_batch_ceiling(budget.policy, compiler_model, max_first_responses)
        for key in ("max_openai_response_calls", "max_openai_count_calls"):
            if type(budget.policy[key]) is not int or budget.policy[key] < 0:
                raise ValueError("nonnegative provider call limits required")
        self._policy_hash = hashlib.sha256(json_bytes(budget.policy)).hexdigest()
        self._groups = None
        self._used = set()
        self._quotes = []

    def _check_open(self):
        if self.budget.closed:
            raise self.budget.stop_reason
        if hashlib.sha256(json_bytes(self.budget.policy)).hexdigest() != self._policy_hash:
            raise self.budget._close("compilation_policy_changed", "Compilation admission policy changed")

    def _check_capacity(self, groups):
        count = len(groups)
        budget = self.budget
        response_slots = budget.policy["max_openai_response_calls"] - sum(
            row["kind"] == "openai_response" for row in budget.records)
        count_slots = budget.policy["max_openai_count_calls"] - sum(
            row.get("kind") == "openai_response" for row in budget.count_records)
        envelope = response_batch_ceiling(budget.policy, self.compiler_model, count)
        total = sum((_amount(value) for value in (budget.charged, budget.pending, budget.count_allowance)), Decimal(0)) + envelope
        code = ("compilation_first_response_limit" if len(self._groups) > self.max_first_responses else
                "compilation_response_slots_exceeded" if count > response_slots else
                "compilation_count_slots_exceeded" if count > count_slots else
                "compilation_pending_request" if budget.pending or budget.active_request_kind is not None else
                "compilation_batch_not_funded" if total > _amount(budget.policy["cap_usd"]) else "")
        self._quotes.append(dict(remaining_groups=[list(group) for group in groups], required_first_responses=count,
            response_slots=response_slots, count_slots=count_slots, remaining_ceiling_usd=str(envelope),
            total_with_existing_accounting_usd=str(total), allowed=not code, blocked_code=code))
        if code:
            raise budget._close(code, "Compilation plan exceeds admitted capacity before provider dispatch")

    def bind(self, plan):
        """Inspect the real builder result once, preserving it byte-for-byte."""
        with self.budget.lock:
            self._check_open()
            if self._groups is not None:
                raise self.budget._close("compilation_plan_rebound", "Compilation plan is already bound")
            if (not isinstance(plan, dict) or plan.get("schema") != "semantic_compilation_islands_v2"
                    or plan.get("status") not in ("ok", "invalid") or not isinstance(plan.get("islands"), list)):
                raise self.budget._close("invalid_compilation_schedule", "Missing compilation schedule")
            groups, seen, island_ids = [], set(), set()
            for island in plan["islands"]:
                owners = island.get("obligation_ids") if isinstance(island, dict) else None
                island_id = island.get("island_id") if isinstance(island, dict) else None
                if (not isinstance(owners, list) or not owners
                        or any(not isinstance(owner, str) or not owner.strip() for owner in owners)
                        or len(set(owners)) != len(owners) or seen.intersection(owners)
                        or not isinstance(island_id, str) or not island_id or island_id in island_ids
                        or not isinstance(island.get("errors"), list)):
                    raise self.budget._close("invalid_compilation_schedule", "Invalid compilation group identity")
                seen.update(owners)
                island_ids.add(island_id)
                # Invalid islands are already handled without a model call by runtime.
                if not island["errors"]:
                    groups.append(tuple(owners))
            self._groups = tuple(groups)
            self._check_capacity(self._groups)

    def authorize(self, owner_ids):
        """One first request for each exact group; no subset repair or regrouping."""
        with self.budget.lock:
            self._check_open()
            if self._groups is None:
                raise self.budget._close("compilation_plan_missing", "Compilation plan was not inspected")
            if (not isinstance(owner_ids, list) or any(not isinstance(owner, str) for owner in owner_ids)
                    or tuple(owner_ids) not in self._groups or tuple(owner_ids) in self._used):
                raise self.budget._close("unapproved_compilation_group", "Request is not a new admitted compilation group")
            self._check_capacity(tuple(group for group in self._groups if group not in self._used))
            self._used.add(tuple(owner_ids))
            return True

    def snapshot(self):
        return deepcopy(dict(compiler_model=self.compiler_model, max_first_responses=self.max_first_responses,
            bound=self._groups is not None, groups=[list(g) for g in self._groups or ()],
            admitted_groups=[list(g) for g in self._groups or () if g in self._used], quotes=self._quotes,
            estimate_only=True, policy_sha256=self._policy_hash))


@contextmanager
def guarded_compilation_plan(budget, *, compiler_model, max_first_responses):
    """Install only inside an explicitly serialized experimental compilation phase.

    The wrapper observes the builder's actual result, including inferred physical
    bundles. It neither reconstructs that result from debug events nor merges
    outputs to fit the cap. Per-request admission remains required separately.
    """
    from src.agent import financial_graph_calculation as compilation

    admission = CompilationPlanAdmission(budget, compiler_model=compiler_model,
        max_first_responses=max_first_responses)
    original = compilation.build_semantic_compilation_islands

    @wraps(original)
    def checked(*args, **kwargs):
        plan = original(*args, **kwargs)
        admission.bind(plan)
        return plan

    with patch.object(compilation, "build_semantic_compilation_islands", checked):
        yield admission
