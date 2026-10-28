#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Statistical Rigour and Verification Suite for GFF+ CCSE.
Verifies Welch's unequal variances t-test, Welch-Satterthwaite degrees of freedom,
two-tailed p-values, Benjamini-Hochberg (BH) step-up FDR q-values,
and all numerical/cohort boundary conditions.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vx.gff.Settings import Settings
from vx.gff.XAI import ContrastiveSubspaceExplainer


class TestXAIStatisticalRigour(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_data_path = Settings.DATA_PATH
        Settings.DATA_PATH = os.path.join(self.tmpdir.name, "")
        self.dataset_id = "test_stat_rigour_ds"
        self.ds_dir = Path(Settings.DATA_PATH) / self.dataset_id
        self.ds_dir.mkdir(parents=True, exist_ok=True)

        rng = np.random.default_rng(12345)
        n = 150
        # Create features with distinct distributions
        # Feature 0: Huge effect size, highly significant (Cluster A vs Rest)
        f0 = np.concatenate([rng.normal(6.0, 0.5, 50), rng.normal(-2.0, 1.2, 100)])
        # Feature 1: Moderate effect size
        f1 = np.concatenate([rng.normal(1.5, 0.8, 50), rng.normal(0.0, 0.8, 100)])
        # Feature 2: Pure noise (null hypothesis H0: mu_A = mu_B)
        f2 = rng.normal(0.0, 1.0, n)
        # Feature 3: Constant feature (zero variance)
        f3 = np.ones(n, dtype=np.float64) * 3.14159
        # Feature 4: High variance in A, low variance in B (heteroscedastic)
        f4 = np.concatenate([rng.normal(0.0, 5.0, 50), rng.normal(0.0, 0.2, 100)])
        # Target: 3-class target
        target = np.array([0] * 50 + [1] * 50 + [2] * 50, dtype=int)

        df = pd.DataFrame({
            "feat_sig_strong": f0,
            "feat_sig_moderate": f1,
            "feat_null_noise": f2,
            "feat_zero_variance": f3,
            "feat_heteroscedastic": f4,
            "class_target": target,
        })
        for fname in ("original.csv", "working.csv", "transform.csv"):
            df.to_csv(self.ds_dir / fname, index=False)

    def tearDown(self):
        Settings.DATA_PATH = self.orig_data_path
        self.tmpdir.cleanup()

    def test_welch_ttest_against_scipy_exact_parity(self):
        """Verify Welch's t-statistic, p-value, and degrees of freedom match scipy.stats.ttest_ind."""
        rng = np.random.default_rng(42)
        # Heteroscedastic cohorts of unequal sizes
        n_a, n_b = 35, 65
        m_features = 8
        X_a = rng.normal(loc=1.2, scale=2.5, size=(n_a, m_features))
        X_b = rng.normal(loc=0.3, scale=0.8, size=(n_b, m_features))

        t_stat, p_val, welch_df = ContrastiveSubspaceExplainer.welch_t_test(X_a, X_b)

        # Scipy reference
        scipy_res = stats.ttest_ind(X_a, X_b, equal_var=False)

        np.testing.assert_allclose(t_stat, scipy_res.statistic, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(p_val, scipy_res.pvalue, rtol=1e-10, atol=1e-12)

        # Verify Welch-Satterthwaite degrees of freedom formula
        s_a = np.var(X_a, axis=0, ddof=1) / n_a
        s_b = np.var(X_b, axis=0, ddof=1) / n_b
        expected_df = ((s_a + s_b) ** 2) / ((s_a ** 2 / (n_a - 1)) + (s_b ** 2 / (n_b - 1)))
        np.testing.assert_allclose(welch_df, expected_df, rtol=1e-10, atol=1e-12)

    def test_welch_ttest_one_group_zero_variance(self):
        """Verify Welch's t-test handles one group having zero variance (s_A=0, s_B>0)."""
        import warnings
        rng = np.random.default_rng(101)
        # Group A has constant values, Group B has varying values
        n_a, n_b = 20, 30
        X_a = np.ones((n_a, 4)) * 4.0
        X_b = rng.normal(loc=2.0, scale=1.5, size=(n_b, 4))

        t_stat, p_val, welch_df = ContrastiveSubspaceExplainer.welch_t_test(X_a, X_b)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scipy_res = stats.ttest_ind(X_a, X_b, equal_var=False)

        np.testing.assert_allclose(t_stat, scipy_res.statistic, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(p_val, scipy_res.pvalue, rtol=1e-8, atol=1e-10)
        # When s_A=0, degrees of freedom reduces to n_B - 1
        np.testing.assert_allclose(welch_df, np.full(4, n_b - 1, dtype=np.float64))

        # Test reverse: Group A has varying values, Group B has constant values
        t_rev, p_rev, df_rev = ContrastiveSubspaceExplainer.welch_t_test(X_b, X_a)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scipy_rev = stats.ttest_ind(X_b, X_a, equal_var=False)
        np.testing.assert_allclose(t_rev, scipy_rev.statistic, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(p_rev, scipy_rev.pvalue, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(df_rev, np.full(4, n_b - 1, dtype=np.float64))

    def test_benjamini_hochberg_step_up_and_monotonicity(self):
        """Verify Benjamini-Hochberg adjustment enforces monotonicity and matches standard FDR."""
        # Raw p-values: some highly significant, some moderate, some non-significant
        raw_p = [0.0001, 0.008, 0.015, 0.045, 0.25, 0.70]
        q_vals = ContrastiveSubspaceExplainer.benjamini_hochberg(raw_p)

        # Sorted p-values are already ascending in this test case
        # Ranks: 1..6, M = 6
        # q1 = min(1.0, 6/1 * 0.0001) = 0.0006
        # q2 = min(1.0, 6/2 * 0.008)  = 0.024
        # q3 = min(1.0, 6/3 * 0.015)  = 0.030
        # q4 = min(1.0, 6/4 * 0.045)  = 0.0675
        # q5 = min(1.0, 6/5 * 0.25)   = 0.30
        # q6 = min(1.0, 6/6 * 0.70)   = 0.70
        expected_q = [0.0006, 0.024, 0.030, 0.0675, 0.30, 0.70]
        np.testing.assert_allclose(q_vals, expected_q, rtol=1e-5)

        # Verify monotonicity enforcement: test case where unconstrained q violates monotonicity
        # p = [0.01, 0.011, 0.08]:
        # ranks 1, 2, 3 -> q' = [0.01 * 3/1 = 0.03, 0.011 * 3/2 = 0.0165, 0.08 * 3/3 = 0.08]
        # Notice q'[0]=0.03 > q'[1]=0.0165!
        # Step-up monotonicity must enforce q[0] <= q[1] -> q[0] = min(0.03, 0.0165) = 0.0165!
        raw_p_non_mono = [0.01, 0.011, 0.08]
        q_mono = ContrastiveSubspaceExplainer.benjamini_hochberg(raw_p_non_mono)
        self.assertLessEqual(q_mono[0], q_mono[1])
        self.assertLessEqual(q_mono[1], q_mono[2])
        self.assertAlmostEqual(q_mono[0], 0.0165, places=5)
        self.assertAlmostEqual(q_mono[1], 0.0165, places=5)
        self.assertAlmostEqual(q_mono[2], 0.08, places=5)

    def test_benjamini_hochberg_unsorted_preserves_mapping(self):
        """Verify that BH adjustment correctly maps q-values back to original unsorted p-value indices."""
        p_original = np.array([0.50, 0.001, 0.04, 0.005, 0.90, 0.02])
        q_vals = ContrastiveSubspaceExplainer.benjamini_hochberg(p_original)

        # Every q-value must majorize its p-value: q_i >= p_i
        self.assertTrue(np.all(q_vals >= p_original - 1e-12))
        # Bounded in [0, 1]
        self.assertTrue(np.all(q_vals >= 0.0))
        self.assertTrue(np.all(q_vals <= 1.0))

        # Check ranking preservation: if p[i] < p[j], then q[i] <= q[j]
        for i in range(len(p_original)):
            for j in range(len(p_original)):
                if p_original[i] < p_original[j]:
                    self.assertLessEqual(q_vals[i], q_vals[j] + 1e-12)

    def test_benjamini_hochberg_controls_fdr_under_null(self):
        """Under the null hypothesis (uniform p-values), BH FDR should not inflate significance."""
        rng = np.random.default_rng(2026)
        # 100 features generated strictly under null hypothesis
        p_null = rng.uniform(0.0, 1.0, size=100)
        q_null = ContrastiveSubspaceExplainer.benjamini_hochberg(p_null)

        significant_count = np.sum(q_null < 0.05)
        # Expected number of false discoveries with FDR control at alpha=0.05 is <= 5
        self.assertLessEqual(significant_count, 5)

    def test_welch_edge_cases(self):
        """Test boundary conditions: zero variance, identical cohorts, single sample, constant features."""
        # 1. Zero variance in both cohorts
        X_zero_a = np.ones((10, 3)) * 5.0
        X_zero_b = np.ones((10, 3)) * 5.0
        t, p, df = ContrastiveSubspaceExplainer.welch_t_test(X_zero_a, X_zero_b)
        np.testing.assert_array_equal(t, np.zeros(3))
        np.testing.assert_array_equal(p, np.ones(3))
        self.assertTrue(np.all(df >= 1.0))

        # 2. Identical non-zero cohorts (null hypothesis exactly holds)
        rng = np.random.default_rng(99)
        X_ident = rng.normal(size=(20, 4))
        t_id, p_id, df_id = ContrastiveSubspaceExplainer.welch_t_test(X_ident, X_ident)
        np.testing.assert_allclose(t_id, np.zeros(4), atol=1e-12)
        np.testing.assert_allclose(p_id, np.ones(4), atol=1e-12)

        # 3. Single-sample cohort fallback
        X_single = np.array([[1.0, 2.0]])
        X_multi = np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]])
        t_s1, p_s1, _ = ContrastiveSubspaceExplainer.welch_t_test(X_single, X_multi)
        t_s2, p_s2, _ = ContrastiveSubspaceExplainer.welch_t_test(X_multi, X_single)
        np.testing.assert_array_equal(t_s1, [0.0, 0.0])
        np.testing.assert_array_equal(p_s1, [1.0, 1.0])
        np.testing.assert_array_equal(t_s2, [0.0, 0.0])
        np.testing.assert_array_equal(p_s2, [1.0, 1.0])

        # 4. Degrees of freedom lower bound
        # When sample variance is extremely small or zero, df must be >= 1.0
        self.assertTrue(np.all(df >= 1.0))

    def test_benjamini_hochberg_edge_cases(self):
        """Test BH FDR on empty, single, and boundary inputs."""
        # Empty array
        q_empty = ContrastiveSubspaceExplainer.benjamini_hochberg([])
        self.assertEqual(len(q_empty), 0)

        # Single p-value
        q_single = ContrastiveSubspaceExplainer.benjamini_hochberg([0.03])
        self.assertEqual(len(q_single), 1)
        self.assertAlmostEqual(q_single[0], 0.03)

        # Extreme p-values
        q_extreme = ContrastiveSubspaceExplainer.benjamini_hochberg([0.0, 1.0, 2.0, -0.5])
        self.assertTrue(np.all(q_extreme >= 0.0))
        self.assertTrue(np.all(q_extreme <= 1.0))

    def test_welch_extreme_numerical_stability(self):
        """Verify Welch's t-test does not overflow or produce NaN on extreme values."""
        # Extreme magnitude values
        X_huge_a = np.array([[1e12, 1e-12], [1.0001e12, 1.0001e-12], [0.9999e12, 0.9999e-12]])
        X_huge_b = np.array([[2e12, 2e-12], [2.0001e12, 2.0001e-12], [1.9999e12, 1.9999e-12]])
        t_huge, p_huge, df_huge = ContrastiveSubspaceExplainer.welch_t_test(X_huge_a, X_huge_b)
        self.assertTrue(np.all(np.isfinite(t_huge)))
        self.assertTrue(np.all(np.isfinite(p_huge)))
        self.assertTrue(np.all(np.isfinite(df_huge)))
        self.assertTrue(np.all(p_huge >= 0.0))
        self.assertTrue(np.all(p_huge <= 1.0))

    def test_ccse_execute_payload_contract_and_significance(self):
        """Verify full CCSE execute integration with payload contracts, significance flags, and backwards compatibility."""
        explainer = ContrastiveSubspaceExplainer()
        res = explainer.execute(Settings.DATA_PATH, {
            "file": self.dataset_id,
            "target": 5,
            "featureselected": [0, 1],
            "group_a_ids": list(range(0, 50)),
        })
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["comparison_mode"], "a_vs_rest")
        self.assertEqual(res["group_a_count"], 50)
        self.assertEqual(res["group_b_count"], 100)

        # Verify root payload structure contains both standard and contract keys
        self.assertIn("features", res)
        self.assertIn("contrastive_features", res)
        self.assertIn("by_feature_id", res)
        self.assertIn("top_contrastive", res)
        self.assertIn("top_counterfactual", res)
        self.assertIn("counterfactual_candidates", res)

        features = res["contrastive_features"]
        self.assertEqual(len(features), 5)  # 5 non-target features

        by_name = {f["name"]: f for f in features}
        strong_f = by_name["feat_sig_strong"]
        noise_f = by_name["feat_null_noise"]
        const_f = by_name["feat_zero_variance"]

        # Required fields check
        required_keys = [
            "feid", "id", "name", "cohens_d", "effect_size",
            "delta_normalized", "contrast_norm",
            "t_statistic", "p_value", "welch_df", "fdr_q_value", "is_significant",
            "mean_group_a", "mean_group_b", "std_group_a", "std_group_b",
            "mean_a", "mean_b", "counterfactual_gain", "redundancy"
        ]
        for key in required_keys:
            self.assertIn(key, strong_f, f"Missing key '{key}' in feature payload")

        # Statistical correctness assertions:
        # feat_sig_strong has mu_A=6.0, mu_B=-2.0, so t-stat should be large, p < 1e-10, significant
        self.assertGreater(strong_f["t_statistic"], 10.0)
        self.assertLess(strong_f["p_value"], 1e-10)
        self.assertLess(strong_f["fdr_q_value"], 0.05)
        self.assertTrue(strong_f["is_significant"])

        # feat_zero_variance has constant values: t=0, p=1, not significant
        self.assertEqual(const_f["t_statistic"], 0.0)
        self.assertEqual(const_f["p_value"], 1.0)
        self.assertFalse(const_f["is_significant"])

        # feat_null_noise is pure noise: p-value should not be tiny
        self.assertGreater(noise_f["p_value"], 0.01)

    def test_ccse_execute_two_group_mode_a_vs_b(self):
        """Verify CCSE execute in explicit two-group comparison mode (Group A vs Group B)."""
        explainer = ContrastiveSubspaceExplainer()
        res = explainer.execute(Settings.DATA_PATH, {
            "file": self.dataset_id,
            "target": 5,
            "featureselected": [0, 1],
            "group_a_ids": list(range(0, 50)),
            "group_b_ids": list(range(50, 100)),
        })
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["comparison_mode"], "a_vs_b")
        self.assertEqual(res["group_a_count"], 50)
        self.assertEqual(res["group_b_count"], 50)

        by_name = {f["name"]: f for f in res["contrastive_features"]}
        strong_f = by_name["feat_sig_strong"]
        self.assertGreater(strong_f["t_statistic"], 5.0)
        self.assertLess(strong_f["p_value"], 1e-5)
        self.assertTrue(strong_f["is_significant"])

    def test_ccse_execute_single_instance_fallback(self):
        """Verify CCSE execute gracefully handles single-instance selection without crashing."""
        explainer = ContrastiveSubspaceExplainer()
        res = explainer.execute(Settings.DATA_PATH, {
            "file": self.dataset_id,
            "target": 5,
            "featureselected": [0, 1],
            "group_a_ids": [0],  # Single instance
        })
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["group_a_count"], 1)
        for f in res["contrastive_features"]:
            self.assertEqual(f["t_statistic"], 0.0)
            self.assertEqual(f["p_value"], 1.0)
            self.assertEqual(f["fdr_q_value"], 1.0)
            self.assertFalse(f["is_significant"])

    def test_ccse_execute_empty_and_error_paths(self):
        """Verify empty selections return empty payload without exceptions."""
        explainer = ContrastiveSubspaceExplainer()
        res_empty = explainer.execute(Settings.DATA_PATH, {
            "file": self.dataset_id,
            "target": 5,
            "group_a_ids": [],
        })
        self.assertEqual(res_empty["status"], "empty")
        self.assertIn("contrastive_features", res_empty)
        self.assertEqual(len(res_empty["contrastive_features"]), 0)


if __name__ == "__main__":
    unittest.main()
