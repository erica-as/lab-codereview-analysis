"""Gera estatisticas descritivas e tabela LaTeX."""

import pandas as pd
from data_utils import prepare_data, METRIC_COLS


def describe(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna estatisticas descritivas formatadas."""
    desc = df[METRIC_COLS].describe().T
    desc["median"] = df[METRIC_COLS].median()
    desc = desc[["count", "mean", "std", "min", "25%", "median", "75%", "max"]]
    desc = desc.reset_index()
    desc = desc.rename(columns={"index": "metrica"})
    return desc.round(2)


def save_descriptive_table(df: pd.DataFrame, out: str = "report/tables/descriptive_stats.csv"):
    desc = describe(df)
    desc.to_csv(out)
    print(f"Tabela descritiva salva em {out}")


if __name__ == "__main__":
    df = prepare_data()
    save_descriptive_table(df)
