"""Utilidades de carregamento e preprocessamento de dados."""

import pandas as pd


DATA_PATH = "src/data/pull_requests_data.csv"

METRIC_COLS = [
    "files_changed",
    "lines_added",
    "lines_deleted",
    "total_changes",
    "analysis_time_hours",
    "description_chars",
    "participants",
    "comments_count",
    "review_comments_count",
    "total_interactions",
    "review_count",
]


def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    """Carrega o CSV de PRs e converte tipos."""
    df = pd.read_csv(path)
    df["merged"] = df["merged"].astype(bool)
    return df


def winsorize(df: pd.DataFrame, cols: list[str], percentile: float = 0.99) -> pd.DataFrame:
    """Aplica winsorizacao simetrica no percentil especificado."""
    df = df.copy()
    for col in cols:
        upper = df[col].quantile(percentile)
        lower = df[col].quantile(1 - percentile)
        df[col] = df[col].clip(lower=lower, upper=upper)
    return df


def prepare_data(path: str = DATA_PATH, winsorize_pct: float = 0.99) -> pd.DataFrame:
    """Pipeline completo: carrega + winsoriza."""
    df = load_data(path)
    df = winsorize(df, METRIC_COLS, winsorize_pct)
    return df
