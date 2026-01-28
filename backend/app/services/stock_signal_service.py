"""
Stock Signal Service
==================

Consolidated service for identifying significant events and anomaly zones in stock time series.
Combines logic from dynamic clustering and significant points detection.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class StockSignalService:
    """
    Unified stock signal service.

    Capabilities:
    1. Adaptive Clustering: Identify periods of abnormal activity (zones).
    2. Significant Points: Identify specific dates with key events (points).
    """

    def __init__(self, window: int = 20, lookback: int = 60, max_zone_days: int = 10):
        """
        Args:
            window: Rolling window size for statistics (default: 20)
            lookback: Lookback period for quantile calculation in clustering (default: 60)
            max_zone_days: Maximum duration for a single anomaly zone (default: 10)
        """
        self.window = window
        self.lookback = lookback
        self.max_zone_days = max_zone_days

    # ==========================================
    # Part 1: Dynamic Clustering (Zone Detection)
    # ==========================================

    def calculate_daily_scores(
        self, df: pd.DataFrame, news_counts: Dict[str, int]
    ) -> pd.DataFrame:
        """Calculate daily composite scores for clustering."""
        if df.empty or len(df) < 2:
            df["daily_score"] = 0
            return df

        df = df.copy()

        # 1. Returns (absolute)
        df["returns"] = df["close"].pct_change().fillna(0)
        df["abs_return"] = df["returns"].abs()

        # 2. Volume Ratio (relative to rolling mean)
        rolling_vol_mean = df["volume"].rolling(window=min(self.window, len(df))).mean()
        rolling_vol_mean = rolling_vol_mean.replace(
            0, df["volume"].mean() if df["volume"].mean() > 0 else 1
        )
        df["vol_ratio"] = df["volume"] / rolling_vol_mean

        # 3. News Density (log1p smoothed)
        df["news_density"] = df["date"].apply(
            lambda x: np.log1p(news_counts.get(str(x)[:10], 0))
        )

        # 4. Normalize to 0-1
        for col in ["abs_return", "vol_ratio", "news_density"]:
            col_max = df[col].max()
            if col_max > 0:
                df[f"{col}_norm"] = df[col] / col_max
            else:
                df[f"{col}_norm"] = 0

        # 5. Composite Score S = Return×0.4 + VolRatio×0.3 + NewsDensity×0.3
        df["daily_score"] = (
            df["abs_return_norm"].fillna(0) * 0.4
            + df["vol_ratio_norm"].fillna(0) * 0.3
            + df["news_density_norm"].fillna(0) * 0.3
        )

        return df

    def adaptive_clustering(self, df: pd.DataFrame) -> List[Dict]:
        """Adaptive threshold clustering to find zones."""
        if df.empty or "daily_score" not in df.columns:
            return []

        scores = df["daily_score"].values
        dates = df["date"].astype(str).str[:10].tolist()
        returns = df["returns"].fillna(0).values

        # Adaptive thresholds
        valid_scores = scores[~np.isnan(scores)]
        if len(valid_scores) < 10:
            t_high = 0.8
            t_low = 0.6
        else:
            recent_scores = (
                valid_scores[-self.lookback :]
                if len(valid_scores) > self.lookback
                else valid_scores
            )
            t_high = np.percentile(recent_scores, 95)
            t_low = np.percentile(recent_scores, 85)
            t_high = max(t_high, 0.3)
            t_low = max(t_low, 0.2)

        zones = []
        i = 0
        while i < len(scores):
            if scores[i] > t_high:
                zone_start = i
                zone_end = i

                # Expand forward
                j = i + 1
                while (
                    j < len(scores)
                    and scores[j] > t_low
                    and (j - zone_start) < self.max_zone_days
                ):
                    zone_end = j
                    j += 1

                # Expand backward
                j = i - 1
                while (
                    j >= 0 and scores[j] > t_low and (zone_end - j) < self.max_zone_days
                ):
                    zone_start = j
                    j -= 1

                zone_returns = returns[zone_start : zone_end + 1]
                avg_return = float(np.mean(zone_returns))

                zones.append(
                    {
                        "start_idx": zone_start,
                        "end_idx": zone_end,
                        "startDate": dates[zone_start],
                        "endDate": dates[zone_end],
                        "avg_score": float(np.mean(scores[zone_start : zone_end + 1])),
                        "avg_return": avg_return,
                        "zone_type": "cluster",
                    }
                )

                i = zone_end + 1
            else:
                i += 1

        return zones

    def fallback_top_points(self, df: pd.DataFrame, k: int = 2) -> List[Dict]:
        """Fallback: identify top K score points as zones."""
        if df.empty or len(df) < k:
            return []

        df_sorted = df.nlargest(k, "daily_score")
        zones = []

        for _, row in df_sorted.iterrows():
            idx = df.index.get_loc(row.name)
            zones.append(
                {
                    "start_idx": idx,
                    "end_idx": idx,
                    "startDate": str(row["date"])[:10],
                    "endDate": str(row["date"])[:10],
                    "avg_score": float(row["daily_score"]),
                    "avg_return": float(row["returns"]) if "returns" in row else 0.0,
                    "zone_type": "fallback",
                }
            )
        return zones

    def calculate_impact(self, zone: Dict, max_score: float) -> float:
        if max_score <= 0:
            return 0.5
        impact = min(zone["avg_score"] / max_score, 1.0)
        return max(impact, 0.3)

    def generate_zones(
        self, df: pd.DataFrame, news_counts: Dict[str, int]
    ) -> List[Dict]:
        """Generate final anomaly zones."""
        # Step 1: Calculate scores
        df_with_scores = self.calculate_daily_scores(df, news_counts)

        # Step 2: Clustering
        zones = self.adaptive_clustering(df_with_scores)

        # Step 3: Fallback··
        if len(zones) == 0:
            zones = self.fallback_top_points(df_with_scores, k=2)
            is_calm = True
        else:
            is_calm = False

        # Step 4: Enrich
        max_score = (
            df_with_scores["daily_score"].max() if not df_with_scores.empty else 1.0
        )
        enriched_zones = []
        for zone in zones:
            zone["impact"] = self.calculate_impact(zone, max_score)
            zone["sentiment"] = "positive" if zone["avg_return"] >= 0 else "negative"
            if is_calm:
                zone["zone_type"] = "calm"
            enriched_zones.append(zone)

        # Step 5: Sort and clean
        enriched_zones.sort(key=lambda x: x["impact"], reverse=True)
        top_zones = enriched_zones[:10]

        for zone in top_zones:
            zone.pop("start_idx", None)
            zone.pop("end_idx", None)

        return top_zones

    # ==========================================
    # Part 2: Significant Points Detection
    # ==========================================

    def calculate_points(
        self, df: pd.DataFrame, news_counts: Dict[str, int], top_k: int = 5
    ) -> List[Dict]:
        """Calculate significant points (pivot analysis, volatility)."""
        if df.empty or len(df) < self.window:
            return []

        df = df.copy()

        # 1. Returns and Rolling Stats
        df["returns"] = df["close"].pct_change()
        df["rolling_mu"] = df["returns"].rolling(window=self.window).mean()
        df["rolling_std"] = df["returns"].rolling(window=self.window).std()

        # 2. Z-Score
        df["rolling_std"] = df["rolling_std"].replace(
            0, df["rolling_std"].mean() if df["rolling_std"].mean() > 0 else 0.01
        )
        df["z_score"] = (df["returns"] - df["rolling_mu"]) / df["rolling_std"]
        df["s_vol"] = df["z_score"].abs()

        # 3. Volume Boost
        rolling_vol_mean = df["volume"].rolling(window=self.window).mean()
        rolling_vol_mean = rolling_vol_mean.replace(
            0, df["volume"].mean() if df["volume"].mean() > 0 else 1
        )
        df["s_vlm"] = df["volume"] / rolling_vol_mean

        # 4. Pivots
        df["is_min"] = df["close"] == df["close"].rolling(window=7, center=True).min()
        df["is_max"] = df["close"] == df["close"].rolling(window=7, center=True).max()
        df["s_pivot"] = (df["is_min"] | df["is_max"]).astype(int) * 2.0

        # 5. News Density
        df["s_news"] = df["date"].apply(
            lambda x: np.log1p(news_counts.get(str(x)[:10], 0))
        )

        # 6. Final Score
        df["final_score"] = (
            df["s_vol"].fillna(0) * 0.4
            + df["s_pivot"].fillna(0) * 0.3
            + df["s_vlm"].fillna(0) * 0.2
            + df["s_news"].fillna(0) * 0.1
        )

        df = df.dropna(subset=["final_score", "returns"])

        # 7. Select Top K
        max_score = df["final_score"].max()
        if max_score < 1.0 and news_counts:
            # Low volatility, prioritize news
            top_news_dates = sorted(
                news_counts.items(), key=lambda x: x[1], reverse=True
            )[:top_k]
            df_filtered = df[
                df["date"].astype(str).str[:10].isin([d[0] for d in top_news_dates])
            ]
        else:
            df_filtered = df.nlargest(top_k, "final_score")

        # 8. Generate Results
        results = []
        for _, row in df_filtered.iterrows():
            reason = self._generate_reason(row, news_counts)
            results.append(
                {
                    "date": str(row["date"])[:10],
                    "score": round(float(row["final_score"]), 2),
                    "type": "positive" if row["returns"] > 0 else "negative",
                    "reason": reason,
                    "is_pivot": bool(row["s_pivot"] > 0),
                }
            )

        return sorted(results, key=lambda x: x["date"])

    def _generate_reason(self, row, news_counts: Dict[str, int]) -> str:
        """Generate human-readable reason for significant point."""
        reasons = []
        if row["s_vol"] > 2:
            reasons.append("供电量异常波动")
        if row["is_max"]:
            reasons.append("阶段性见顶")
        if row["is_min"]:
            reasons.append("阶段性筑底")
        if row["s_vlm"] > 2:
            reasons.append("成交量激增")

        date_str = str(row["date"])[:10]
        if news_counts.get(date_str, 0) > 5:
            reasons.append("舆情热度爆发")

        return "、".join(reasons) if reasons else "趋势关键节点"

    # ==========================================
    # Part 3: Change Point Detection (Power Domain)
    # ==========================================

    def detect_change_points(
        self, df: pd.DataFrame, window_size: int = 5, threshold: float = 1.5
    ) -> List[Dict]:
        """
        Detect significant change points (sudden mean shifts) in the time series.
        Using a sliding window Difference of Means (DoM) approach.

        Args:
            df: DataFrame with 'date' and 'y' (value) columns.
            window_size: Size of the window before and after to compare.
            threshold: Z-score threshold for significance.

        Returns:
            List of dictionaries with change point details.
        """
        if df.empty or len(df) < window_size * 2:
            return []

        df = df.copy()
        # Ensure we have the target column 'y' (prophet format) or 'close' (stock format)
        target_col = "y" if "y" in df.columns else "close"

        values = df[target_col].values
        dates = df["date"].astype(str).str[:10].tolist()
        n = len(values)

        change_points = []

        # Calculate rolling statistics for global context
        global_std = np.std(values)
        if global_std == 0:
            return []

        # Sliding window DoM
        for i in range(window_size, n - window_size):
            # Window before: [i-window_size : i]
            # Window after:  [i : i+window_size]
            before = values[i - window_size : i]
            after = values[i : i + window_size]

            mean_before = np.mean(before)
            mean_after = np.mean(after)

            diff = mean_after - mean_before

            # Key metric: Difference normalized by global std dev
            # This represents "how many standard deviations did the level shift?"
            score = abs(diff) / global_std

            if score > threshold:
                # Local check: is this a local maximum of change?
                # This prevents consecutive points triggering for the same step
                neighbor_scores = []
                for j in range(max(window_size, i - 2), min(n - window_size, i + 3)):
                    if j == i:
                        continue

                    b = values[j - window_size : j]
                    a = values[j : j + window_size]
                    neighbor_scores.append(abs(np.mean(a) - np.mean(b)) / global_std)

                if not neighbor_scores or score >= max(neighbor_scores):
                    change_points.append(
                        {
                            "date": dates[i],
                            "index": i,
                            "type": "rise" if diff > 0 else "drop",
                            "magnitude": float(score),  # Z-score of the shift
                            "diff_val": float(diff),  # Absolute value difference
                            "confidence": min(
                                float(score / threshold) * 0.5 + 0.5, 0.99
                            ),
                        }
                    )

        # Sort by magnitude descent
        change_points.sort(key=lambda x: x["magnitude"], reverse=True)

        # Fallback: if no points found with high threshold, try lower threshold
        if not change_points and threshold > 0.5:
            # Just do a quick scan here to guarantee at least 1 point
            # Find the max single-step change
            max_score = 0
            best_idx = -1
            best_diff = 0

            for i in range(window_size, n - window_size):
                before = values[i - window_size : i]
                after = values[i : i + window_size]
                diff = np.mean(after) - np.mean(before)
                score = abs(diff) / (global_std if global_std > 0 else 1)

                if score > max_score:
                    max_score = score
                    best_idx = i
                    best_diff = diff

            if best_idx != -1:
                change_points.append(
                    {
                        "date": dates[best_idx],
                        "index": best_idx,
                        "type": "rise" if best_diff > 0 else "drop",
                        "magnitude": float(max_score),
                        "diff_val": float(best_diff),
                        "confidence": 0.5,  # Lower confidence for fallback
                        "is_fallback": True,
                    }
                )

        return change_points[:5]  # Return top 5 most significant changes
