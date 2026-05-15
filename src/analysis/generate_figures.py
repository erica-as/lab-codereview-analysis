"""Gera todos os graficos para o relatorio.

Escolhas baseadas em:
- Claus O. Wilke, "Fundamentals of Data Visualization" (O'Reilly, 2019)
- Thorsoe et al., VMV 2024 (axis breaks para dados enviesados)
- Cavus, arXiv 2025 (ggskewboxplots - boxplots tradicionais falham com skew)
- Feifke, Towards Data Science 2022 (ECDF como substituicao robusta de histogramas)
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from data_utils import prepare_data, METRIC_COLS

sns.set_theme(style="whitegrid", font_scale=1.05)
plt.rcParams["figure.dpi"] = 300
plt.rcParams["font.family"] = "sans-serif"

# Cores acessiveis (daltonismo-friendly)
COLOR_CLOSED = "#D55E00"   # vermelho-alaranjado
COLOR_MERGED = "#0072B2"   # azul
COLOR_NEUTRAL = "#56B4E9"  # azul claro


def save(fig, name: str):
    path = f"report/figures/{name}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"Figura salva: {path}")
    plt.close(fig)


def plot_rq_ecdf(df: pd.DataFrame, metric: str, rq: str, log_x: bool = True):
    """ECDF (Empirical Cumulative Distribution Function) para RQs de dimensao A.

    ECDF e superior a histogramas e violin plots para dados enviesados:
    - Sem parametros arbitrarios (bins, bandwidth)
    - Mostra todos os pontos de dados
    - Robusto a outliers
    - Comparacao direta entre grupos

    Referencia: Claus O. Wilke, "Fundamentals of Data Visualization", Cap. 8
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    for status, label, color in [(False, "Closed", COLOR_CLOSED), (True, "Merged", COLOR_MERGED)]:
        vals = df[df["merged"] == status][metric].dropna().sort_values()
        n = len(vals)
        y = np.arange(1, n + 1) / n
        ax.plot(vals, y, color=color, linewidth=2, label=label)
        # Marca mediana
        med = np.median(vals)
        ax.axvline(med, color=color, linestyle="--", alpha=0.5)
        ax.text(med * 1.05 if log_x else med + 1, 0.5,
                f"med={med:.0f}", color=color, fontsize=9, fontweight="bold",
                verticalalignment="center")

    if log_x:
        ax.set_xscale("log")
        ax.set_xlabel(f"{metric.replace('_', ' ').title()} (escala log)")
    else:
        ax.set_xlabel(metric.replace("_", " ").title())

    ax.set_ylabel("Proporcao acumulada")
    ax.set_title(f"{rq}: Distribuicao de {metric.replace('_', ' ').title()} por Status")
    ax.legend(loc="lower right")
    ax.set_ylim(0, 1.02)

    save(fig, rq.lower())


def _cap_review_count(df: pd.DataFrame, col: str, max_val: int = 10) -> pd.DataFrame:
    """Agrupa review_count > max_val em uma unica categoria 'max_val+'."""
    df = df.copy()
    df[col] = df[col].apply(lambda x: int(x) if x <= max_val else max_val + 1)
    return df


def plot_rq_contour(df: pd.DataFrame, x: str, y: str, rq: str):
    """Violin plot com boxplot interno para RQs de dimensao B.

    Violin + boxplot e ideal para relacao entre variavel continua
    enviesada e variavel discreta (review_count):
    - Mostra distribuicao completa (violino)
    - Mostra mediana, quartis e outliers (boxplot)
    - Funciona com dados enviesados via escala log

    review_count e agrupado em 1-10 + '11+' para legibilidade.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Agrupa review_count alto
    df_plot = _cap_review_count(df, x, max_val=10)

    # Renomeia categoria 11 para legibilidade
    cat_labels = [str(i) for i in range(1, 11)] + ["11+"]
    df_plot[x] = df_plot[x].astype(int)
    df_plot[x] = df_plot[x].map(lambda v: cat_labels[v - 1] if v <= 11 else cat_labels[-1])

    # Mantem ordem correta
    df_plot[x] = pd.Categorical(df_plot[x], categories=cat_labels, ordered=True)

    # Violin com boxplot interno, cores com contraste
    sns.violinplot(
        data=df_plot, x=x, y=y, hue=x, ax=ax,
        inner="box", palette="Set2",
        cut=0, linewidth=1,
        fill=True, alpha=0.7,
        legend=False
    )

    # Escala log no eixo Y para dados enviesados
    ax.set_yscale("log")
    ax.set_xlabel(x.replace("_", " ").title())
    ax.set_ylabel(f"{y.replace('_', ' ').title()} (escala log)")
    ax.set_title(f"{rq}: {y.replace('_', ' ').title()} por {x.replace('_', ' ').title()}")

    save(fig, rq.lower())


def plot_correlation_matrix(df: pd.DataFrame):
    """Matriz de correlacao limpa (sem colunas zeradas)."""
    cols = [c for c in METRIC_COLS if df[c].std() > 0]
    df_clean = df[cols]

    fig, ax = plt.subplots(figsize=(8, 7))
    corr = df_clean.corr(method="spearman")

    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                ax=ax, mask=mask, linewidths=0.5,
                cbar_kws={"label": "Spearman rho"},
                vmin=-1, vmax=1)

    ax.set_title("Matriz de Correlacao de Spearman")
    save(fig, "correlation_matrix")


def plot_ecdf_all(df: pd.DataFrame):
    """ECDF de todas as metricas principais em um unico grafico.

    Substitui os histogramas individuais. ECDF e a escolha recomendada
    por Claus Wilke para distribuicoes enviesadas.
    """
    cols_plot = ["total_changes", "analysis_time_hours", "description_chars",
                 "participants", "review_count"]

    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    axes = axes.flatten()

    for i, col in enumerate(cols_plot):
        ax = axes[i]
        for status, label, color in [(False, "Closed", COLOR_CLOSED), (True, "Merged", COLOR_MERGED)]:
            vals = df[df["merged"] == status][col].dropna().sort_values()
            n = len(vals)
            y = np.arange(1, n + 1) / n
            ax.plot(vals, y, color=color, linewidth=1.5, alpha=0.8, label=label if i == 0 else "")

        ax.set_title(col.replace("_", " ").title())
        if df[col].max() / df[col].quantile(0.75) > 50:
            ax.set_xscale("log")
        ax.set_ylim(0, 1.02)
        if i == 0:
            ax.legend(fontsize=8)

    axes[5].set_visible(False)
    fig.supylabel("Proporcao acumulada", fontsize=12)
    save(fig, "distribution_ecdf")


def plot_rq_contour_binary(df: pd.DataFrame, x: str, y: str, rq: str):
    """Boxplot lado a lado para variavel binaria (has_description) vs review_count.

    Para RQ08: PRs com descricao recebem mais revisoes?
    Mostra distribuicao de review_count agrupada por has_description.
    """
    fig, ax = plt.subplots(figsize=(7, 5))

    df_plot = df.copy()
    df_plot[x] = df_plot[x].map({0: "Sem descricao", 1: "Com descricao"})
    df_plot[x] = pd.Categorical(df_plot[x], categories=["Sem descricao", "Com descricao"], ordered=True)

    # Cap review_count para legibilidade
    df_plot[y] = df_plot[y].clip(upper=10)

    sns.boxplot(
        data=df_plot, x=x, y=y, ax=ax,
        palette=[COLOR_CLOSED, COLOR_MERGED],
        linewidth=1.2, fliersize=3,
        showfliers=False  # outliers poluem; boxplot ja mostra whiskers
    )

    # Overlay de swarm plot para mostrar distribuicao real
    from matplotlib.colors import to_rgba
    sample = df_plot.sample(n=min(1000, len(df_plot)), random_state=42)
    sns.stripplot(
        data=sample, x=x, y=y, ax=ax,
        palette=[to_rgba(COLOR_CLOSED, 0.3), to_rgba(COLOR_MERGED, 0.3)],
        size=2, alpha=0.4, jitter=0.2
    )

    ax.set_xlabel("")
    ax.set_ylabel("Numero de Revisoes")
    ax.set_title(f"{rq}: Revisoes por Presenca de Descricao")

    # Anotar medianas
    for i, label in enumerate(["Sem descricao", "Com descricao"]):
        med = df_plot[df_plot[x] == label][y].median()
        ax.text(i, med + 0.3, f"med={med:.0f}", ha="center",
                fontsize=10, fontweight="bold")

    save(fig, rq.lower())


def plot_merged_vs_reviews(df: pd.DataFrame):
    """ECDF: numero de revisoes por status de merge.

    ECDF e preferivel a boxplot para dados com poucos valores discretos
    (review_count e inteiro pequeno).
    """
    fig, ax = plt.subplots(figsize=(7, 5))

    for status, label, color in [(False, "Closed", COLOR_CLOSED), (True, "Merged", COLOR_MERGED)]:
        vals = df[df["merged"] == status]["review_count"].dropna().sort_values()
        n = len(vals)
        y = np.arange(1, n + 1) / n
        ax.plot(vals, y, color=color, linewidth=2, label=label)
        med = np.median(vals)
        ax.axvline(med, color=color, linestyle="--", alpha=0.5)
        ax.text(med + 0.3, 0.5, f"med={med:.0f}", color=color,
                fontsize=10, fontweight="bold", verticalalignment="center")

    ax.set_xlabel("Numero de Revisoes")
    ax.set_ylabel("Proporcao acumulada")
    ax.set_title("Distribuicao de Revisoes por Status de Merge")
    ax.legend(loc="lower right")
    ax.set_ylim(0, 1.02)

    save(fig, "merged_vs_reviews")


def generate_all():
    df = prepare_data()
    print(f"Dataset: {len(df)} PRs")

    # Dimensao A: ECDF (substitui violin/boxplot)
    plot_rq_ecdf(df, "total_changes", "RQ01")
    plot_rq_ecdf(df, "analysis_time_hours", "RQ02")
    plot_rq_ecdf(df, "description_chars", "RQ03")
    plot_rq_ecdf(df, "participants", "RQ04")

    # Dimensao B: Violin + boxplot (substitui scatter+jitter)
    plot_rq_contour(df, "review_count", "total_changes", "RQ05")
    plot_rq_contour(df, "review_count", "analysis_time_hours", "RQ06")
    plot_rq_contour(df, "review_count", "description_chars", "RQ07")

    # Complementares
    plot_correlation_matrix(df)
    plot_ecdf_all(df)
    plot_merged_vs_reviews(df)

    print("Todas as figuras geradas.")


if __name__ == "__main__":
    generate_all()
