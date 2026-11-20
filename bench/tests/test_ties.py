"""Unit tests of the tie margins: A/A control, between-job spread and the pooled floor."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggregate  # noqa: E402
import rankings  # noqa: E402
import report  # noqa: E402
from test_bench import fake_job, rank_row  # noqa: E402

LN10 = math.log(1.10)  # a half-range of ±10%


def jobs_of(slug: str, scores: list[float], cpus: list[str], **extra) -> list[dict]:
    """Per-job rows whose Hello world score is the given one, each on the given CPU model."""
    return [rank_row(slug, hello=(score,) * 3, cpu_model=cpu, **extra) for score, cpu in zip(scores, cpus)]


def spread_of(half_range: float) -> list[float]:
    """Three per-job scores around 1.0 whose log half-range is `half_range`."""
    return [math.exp(-half_range), 1.0, math.exp(half_range)]


class TieMarginTests(unittest.TestCase):
    def rank(self, pooled: dict[str, float], per_job: dict[str, list[dict]], controls=None):
        """Rank pooled Hello world scores with the given per-job rows; returns the hello category."""
        base = rank_row("axum", is_baseline=True, ratios={})
        rows = [base, *(rank_row(slug, hello=(score,) * 3) for slug, score in pooled.items())]
        result = rankings.compute(rows, "axum", control_rows=controls or [], job_rows=per_job)
        hello = next(c for c in result["categories"] if c["key"] == "hello")
        return hello, {e["slug"]: e for e in hello["entries"]}, result

    def test_spread_is_the_half_range_of_the_log_scores(self):
        spread = rankings.job_spread([0.45, 0.31, 0.40], ["Xeon", "EPYC 7763", "EPYC 9V74"])
        self.assertAlmostEqual(spread["own"], math.log(0.45 / 0.31) / 2, places=6)
        self.assertFalse(spread["same_cpu"])
        self.assertEqual(spread["jobs"], 3)
        # Jobs without a score do not count; a missing CPU model counts as one CPU model.
        partial = rankings.job_spread([0.5, None, 0.6], ["A", "B", None])
        self.assertEqual(partial["jobs"], 2)
        self.assertTrue(partial["same_cpu"])
        self.assertIsNone(rankings.job_spread([0.5], ["A"])["own"])
        self.assertEqual(rankings.pooled_floor([{"own": 0.3}, {"own": 0.1}, {"own": None}, {"own": 0.2}]), 0.2)
        self.assertEqual(rankings.pooled_floor([{"own": 0.1}, {"own": 0.3}]), 0.2)
        self.assertIsNone(rankings.pooled_floor([{"own": None}]))

    def test_the_margin_is_the_largest_of_the_three_terms(self):
        self.assertAlmostEqual(rankings.pair_margin(0.01, 0.02, 0.03, 0.04), 0.05)  # (b) root of squares
        self.assertAlmostEqual(rankings.pair_margin(0.01, 0.08, 0.03, 0.04), 0.08)  # (c) pooled floor
        self.assertAlmostEqual(rankings.pair_margin(0.09, 0.08, 0.03, 0.04), 0.09)  # (a) A/A
        self.assertAlmostEqual(rankings.pair_margin(None, None, 0.03), 0.03)  # against Axum: one spread
        self.assertIsNone(rankings.pair_margin(None, None, None, None))

    def test_gap_just_inside_and_just_outside_the_margin(self):
        cpus = ["CPU A", "CPU B", "CPU C"]
        margin = math.sqrt(2) * LN10  # two implementations with a ±10% spread each, above the floor (±10%)
        for offset, tied in ((-0.002, True), (0.002, False)):
            with self.subTest(offset=offset):
                lower = math.exp(-(margin + offset))
                per_job = {"a": jobs_of("a", spread_of(LN10), cpus), "b": jobs_of("b", spread_of(LN10), cpus)}
                hello, cats, _ = self.rank({"a": 1.0, "b": lower}, per_job)
                self.assertAlmostEqual(hello["tie_rule"]["floor"], LN10, places=4)  # scores are rounded to 4 digits
                self.assertEqual(cats["b"]["tie"], tied)
                self.assertEqual(cats["b"]["position"], 1 if tied else 2)
                check = cats["b"]["tie_check"]
                self.assertEqual(check["against"], "a")
                self.assertAlmostEqual(check["margin"], margin, places=4)
                self.assertEqual(check["tied"], tied)
                self.assertNotIn("tie_check", cats["a"])  # the first position has no check
                self.assertEqual(cats["a"]["spread"]["basis"], "own")

    def test_the_aa_margin_alone_was_too_small(self):
        # The same gap that ties under the spread rule did not tie under the A/A margin alone.
        controls = [rank_row("axum-control", hello=(1.003,) * 3, role="control", role_note="c")]
        cpus = ["CPU A", "CPU B", "CPU C"]
        per_job = {"a": jobs_of("a", spread_of(LN10), cpus), "b": jobs_of("b", spread_of(LN10), cpus)}
        _, cats, _ = self.rank({"a": 1.0, "b": 0.88}, per_job, controls=controls)
        self.assertTrue(cats["b"]["tie"])
        _, cats, _ = self.rank({"a": 1.0, "b": 0.88}, {}, controls=controls)
        self.assertFalse(cats["b"]["tie"])

    def test_the_floor_applies_when_every_job_ran_on_one_cpu_model(self):
        cpus = ["CPU A", "CPU B", "CPU C"]
        per_job = {"a": jobs_of("a", spread_of(LN10), cpus), "b": jobs_of("b", spread_of(LN10), cpus),
                   "same": jobs_of("same", spread_of(0.01), ["CPU A"] * 3)}
        floor_pair = math.sqrt(2) * LN10  # "same" counts with the floor (±10%), not its own ±1%
        own_pair = math.sqrt(LN10 ** 2 + 0.01 ** 2)
        score = math.exp(-(own_pair + floor_pair) / 2)  # between the two possible margins
        hello, cats, _ = self.rank({"a": 1.0, "same": score, "b": 0.5}, per_job)  # floor: median of three
        spread = cats["same"]["spread"]
        self.assertTrue(spread["same_cpu"])
        self.assertEqual(spread["basis"], "floor (one CPU model)")
        self.assertAlmostEqual(spread["effective"], hello["tie_rule"]["floor"], places=6)
        self.assertAlmostEqual(spread["own"], 0.01, places=3)
        self.assertTrue(cats["same"]["tie"])
        # On three CPU models the same small spread would be its own, and the gap would separate them.
        per_job["same"] = jobs_of("same", spread_of(0.01), cpus)
        _, cats, _ = self.rank({"a": 1.0, "same": score, "b": 0.5}, per_job)
        self.assertEqual(cats["same"]["spread"]["basis"], "own")
        self.assertFalse(cats["same"]["tie"])

    def test_a_single_job_counts_with_the_pooled_floor(self):
        cpus = ["CPU A", "CPU B", "CPU C"]
        per_job = {"a": jobs_of("a", spread_of(LN10), cpus), "b": jobs_of("b", spread_of(LN10), cpus),
                   "one": jobs_of("one", [0.9], ["CPU A"])}
        margin = math.sqrt(2) * LN10
        _, cats, _ = self.rank({"a": 1.0, "one": math.exp(-(margin - 0.002))}, per_job)
        spread = cats["one"]["spread"]
        self.assertEqual(spread["basis"], "floor (one job)")
        self.assertIsNone(spread["own"])
        self.assertAlmostEqual(spread["effective"], LN10, places=4)
        self.assertEqual(cats["one"]["position"], 1)  # ranked, with the floor as its spread
        self.assertTrue(cats["one"]["tie"])
        _, cats, _ = self.rank({"a": 1.0, "one": math.exp(-(margin + 0.002))}, per_job)
        self.assertEqual(cats["one"]["position"], 2)

    def test_without_two_jobs_anywhere_only_the_aa_margin_counts(self):
        controls = [rank_row("axum-control", hello=(1.02,) * 3, role="control", role_note="c")]
        per_job = {"a": jobs_of("a", [1.0], ["CPU A"]), "b": jobs_of("b", [0.97], ["CPU B"])}
        hello, cats, _ = self.rank({"a": 1.0, "b": 0.985, "c": 0.95}, per_job, controls=controls)
        self.assertIsNone(hello["tie_rule"]["floor"])
        self.assertEqual(cats["b"]["spread"]["basis"], "none (one job, no floor)")
        self.assertEqual([cats[s]["position"] for s in "abc"], [1, 1, 3])
        self.assertAlmostEqual(cats["b"]["tie_check"]["margin"], math.log(1.02), places=6)

    def test_equal_scores_share_a_position_whatever_their_spread(self):
        # "noisy" ties with "a" through its own spread; "precise" has the same score but almost no spread,
        # and alone would be separated from "a". The group's widest spread keeps it with "noisy".
        cpus = ["CPU A", "CPU B", "CPU C"]
        per_job = {"a": jobs_of("a", [1.0, 1.0, 1.0], cpus), "noisy": jobs_of("noisy", spread_of(0.25), cpus),
                   "precise": jobs_of("precise", spread_of(0.001), cpus)}
        hello, cats, _ = self.rank({"a": 1.0, "noisy": 0.9, "precise": 0.9}, per_job)
        self.assertEqual([cats[s]["position"] for s in ("a", "noisy", "precise")], [1, 1, 1])
        self.assertEqual(cats["precise"]["tie_check"]["group_spread_of"], "noisy")
        self.assertIsNone(cats["noisy"]["tie_check"]["group_spread_of"])
        # Pairwise, "precise" would be separated from "a": the gap is above both spreads and the floor.
        self.assertGreater(abs(math.log(0.9)), rankings.pair_margin(None, hello["tie_rule"]["floor"],
                                                                    cats["a"]["spread"]["effective"],
                                                                    cats["precise"]["spread"]["effective"]))

    def test_reference_margin_uses_the_spread(self):
        cpus = ["CPU A", "CPU B", "CPU C"]
        per_job = {"a": jobs_of("a", spread_of(LN10), cpus)}
        _, cats, _ = self.rank({"a": 1.08}, per_job)
        self.assertTrue(cats["a"]["within_reference_margin"])
        self.assertAlmostEqual(cats["a"]["reference_margin"]["percent"], 10.0, places=1)
        _, cats, _ = self.rank({"a": 1.12}, per_job)
        self.assertFalse(cats["a"]["within_reference_margin"])

    def test_every_category_and_the_overall_score_use_the_rule(self):
        cpus = ["CPU A", "CPU B", "CPU C"]
        base = rank_row("axum", is_baseline=True, ratios={})
        rows = [base, rank_row("a", hello=(1.0,) * 3, database=(1.0,) * 4),
                rank_row("b", hello=(0.88,) * 3, database=(0.88,) * 4)]
        per_job = {slug: [rank_row(slug, hello=(s,) * 3, database=(s,) * 4, cpu_model=c)
                          for s, c in zip(spread_of(LN10), cpus)] for slug in "ab"}
        result = rankings.compute(rows, "axum", control_rows=[], job_rows=per_job)
        cats = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in result["categories"]}
        self.assertTrue(cats["hello"]["b"]["tie"])
        self.assertTrue(cats["database"]["b"]["tie"])
        for category in result["categories"]:
            self.assertIn("tie_rule", category)
        overall = {e["slug"]: e for e in result["overall"]["entries"]}
        self.assertIsNotNone(result["overall"]["tie_rule"]["floor"])
        self.assertEqual(len(overall["a"]["spread"]["scores"]), 3)
        self.assertTrue(overall["b"]["tie"])
        for weighting in result["sensitivity"]:
            self.assertIn("tie_rule", weighting)

    def test_aggregate_uses_every_job_and_the_report_shows_margins_and_cpus(self):
        jobs = []
        for slug, scales in (("actix", (1.0, 1.1, 1.21)), ("gin", (0.9, 0.99, 1.09))):
            for number, (scale, cpu) in enumerate(zip(scales, ("CPU A", "CPU B", "CPU C")), start=1):
                job = fake_job(slug, scale)
                job["job"] = number
                job["environment"] = dict(job["environment"], cpu_model=cpu)
                jobs.append(job)
        combined = aggregate.combine(jobs, ["actix", "gin"])
        hello = {e["slug"]: e for e in combined["rankings"]["categories"][0]["entries"]}
        self.assertEqual(hello["actix"]["spread"]["cpu_models"], ["CPU A", "CPU B", "CPU C"])
        self.assertEqual(hello["actix"]["spread"]["jobs"], 3)
        self.assertGreater(hello["actix"]["spread"]["own"], 0.05)
        self.assertTrue(hello["gin"]["tie"])  # a 10% gap within the spread of runners
        readme = report.render_readme_table(combined)
        self.assertIn("A/A margin and pooled floor per category", readme)
        self.assertIn("1 (tie): ", readme)
        self.assertIn(f"±{hello['gin']['tie_check']['percent']:.1f}%", readme)
        self.assertIn("CPU A, CPU B, CPU C", readme)
        results = report.render_results(combined)
        self.assertIn("| Job scores | Spread | Position check |", results)
        self.assertIn("(CPU A); ", results)
        self.assertIn("vs Actix", results)

    def test_the_pool_note_reads_the_no_ping_diagnostic(self):
        jobs = [fake_job("actix", 1.0), fake_job("axum-no-ping", 1.2)]
        jobs[1]["implementations"]["axum-no-ping"]["manifest"].update(role="diagnostic", role_note="no ping")
        combined = aggregate.combine(jobs, ["actix", "axum-no-ping"])
        readme = report.render_readme_table(combined)
        self.assertIn("**Connection-pool defaults.**", readme)
        self.assertIn("`test_before_acquire`, on by default", readme)
        self.assertIn("in these results Axum scored 1.20 in Database and 1.20 in Application", readme)
        self.assertIn("Every implementation runs its framework's documented defaults.", readme)
        self.assertNotIn("Experimental", readme)
        without = report.render_readme_table(aggregate.combine(jobs[:1], ["actix"]))
        self.assertIn("it has no Database and Application scores in these results", without)


if __name__ == "__main__":
    unittest.main()
