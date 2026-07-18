import subprocess
import sys
import unittest

from app_test_scripts.workflow_acceptance_plans import CANONICAL_WORKFLOW_ACCEPTANCE_PLANS
from src.domain.workflow_acceptance import WorkflowAcceptancePlan
from src.services.workflow_acceptance_runner import assert_workflow_acceptance_plan


class TestWorkflowAcceptancePlanContracts(unittest.TestCase):
    def test_all_canonical_plans_validate_as_pydantic_models(self) -> None:
        for plan in CANONICAL_WORKFLOW_ACCEPTANCE_PLANS:
            with self.subTest(plan_id=plan.plan_id):
                revalidated = WorkflowAcceptancePlan.model_validate(plan.model_dump())
                self.assertEqual(revalidated.plan_id, plan.plan_id)

    def test_canonical_plan_ids_are_unique(self) -> None:
        plan_ids = [plan.plan_id for plan in CANONICAL_WORKFLOW_ACCEPTANCE_PLANS]
        self.assertEqual(len(plan_ids), len(set(plan_ids)))


class TestWorkflowAcceptancePlans(unittest.TestCase):
    def test_non_comparison_latest_available(self) -> None:
        plan = _plan_by_id("non_comparison_latest_available")
        result = assert_workflow_acceptance_plan(plan)
        self.assertFalse(result.requires_clarification)
        self.assertIsNone(result.comparison_plan)

    def test_temporal_conflict_clarification(self) -> None:
        plan = _plan_by_id("temporal_conflict_clarification")
        result = assert_workflow_acceptance_plan(plan)
        self.assertTrue(result.requires_clarification)
        self.assertTrue(result.final_answer_present)

    def test_benchmark_missing_metric_clarification(self) -> None:
        plan = _plan_by_id("benchmark_missing_metric_clarification")
        result = assert_workflow_acceptance_plan(plan)
        self.assertTrue(result.requires_clarification)

    def test_benchmark_conflict_clarification(self) -> None:
        plan = _plan_by_id("benchmark_conflict_clarification")
        result = assert_workflow_acceptance_plan(plan)
        self.assertTrue(result.requires_clarification)

    def test_resolved_peer_group_comparison(self) -> None:
        plan = _plan_by_id("resolved_peer_group_comparison")
        result = assert_workflow_acceptance_plan(plan)
        self.assertIsNotNone(result.comparison_plan)
        self.assertEqual(result.comparison_plan.metric, "population")

    def test_named_state_custom_set_comparison(self) -> None:
        plan = _plan_by_id("named_state_custom_set_comparison")
        result = assert_workflow_acceptance_plan(plan)
        self.assertIsNotNone(result.comparison_plan)
        self.assertIn("state:06", result.comparison_plan.subject_geos)

    def test_national_benchmark_comparison(self) -> None:
        plan = _plan_by_id("national_benchmark_comparison")
        result = assert_workflow_acceptance_plan(plan)
        self.assertIsNotNone(result.comparison_plan)
        self.assertEqual(result.comparison_plan.benchmark_geo_level, "nation")

    def test_comparison_metrics_end_to_end(self) -> None:
        plan = _plan_by_id("comparison_metrics_end_to_end")
        result = assert_workflow_acceptance_plan(plan)
        self.assertEqual(result.comparison_metrics_count, 2)


class TestWorkflowAcceptanceRuff(unittest.TestCase):
    RUFF_PATHS = [
        "src/domain/workflow_acceptance.py",
        "src/services/workflow_acceptance_runner.py",
        "app_test_scripts/workflow_acceptance_plans.py",
        "app_test_scripts/test_workflow_acceptance_plans.py",
    ]

    def test_workflow_acceptance_files_pass_ruff(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "ruff", "check", *self.RUFF_PATHS],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stdout + completed.stderr,
        )


def _plan_by_id(plan_id: str) -> WorkflowAcceptancePlan:
    for plan in CANONICAL_WORKFLOW_ACCEPTANCE_PLANS:
        if plan.plan_id == plan_id:
            return plan
    raise ValueError(f"unknown workflow acceptance plan_id: {plan_id}")


if __name__ == "__main__":
    unittest.main()
