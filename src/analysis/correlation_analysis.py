"""Analise de correlacao Spearman por RQ."""

import pandas as pd
from scipy.stats import spearmanr
from data_utils import prepare_data, METRIC_COLS


RQS = {
    "RQ01": ("total_changes", "merged"),
    "RQ02": ("analysis_time_hours", "merged"),
    "RQ03": ("description_chars", "merged"),
    "RQ04": ("participants", "merged"),
    "RQ05": ("total_changes", "review_count"),
    "RQ06": ("analysis_time_hours", "review_count"),
    "RQ07": ("description_chars", "review_count"),
}


def interpret_rho(rho: float) -> str:
    if abs(rho) < 0.1:
        return "desprezivel"
    if abs(rho) < 0.3:
        return "fraca"
    if abs(rho) < 0.5:
        return "moderada"
    if abs(rho) < 0.7:
        return "forte"
    return "muito forte"


def run_correlations(df: pd.DataFrame) -> pd.DataFrame:
    results = []
    for rq, (x, y) in RQS.items():
        rho, pval = spearmanr(df[x], df[y])
        results.append({
            "RQ": rq,
            "var_x": x,
            "var_y": y,
            "rho": round(rho, 4),
            "p_value": round(pval, 4),
            "significant": pval < 0.05,
            "effect_size": interpret_rho(rho),
        })
    return pd.DataFrame(results)


def save_correlation_table(df: pd.DataFrame, out: str = "report/tables/correlation_results.csv"):
    res = run_correlations(df)
    res.to_csv(out, index=False)
    print(f"Correlacoes salvas em {out}")
    print(res.to_string(index=False))


if __name__ == "__main__":
    df = prepare_data()
    save_correlation_table(df)
