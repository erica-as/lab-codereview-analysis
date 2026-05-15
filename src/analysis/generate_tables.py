"""Gera tabelas formatadas para inclusao no LaTeX."""

import pandas as pd


def write_descriptive_table(csv_path: str, out_path: str):
    """Escreve tabela descritiva formatada para LaTeX."""
    df = pd.read_csv(csv_path)
    # Remove coluna 'Unnamed: 0' se existir
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    with open(out_path, "w") as f:
        f.write("\\begin{tabular}{lrrrrrrrr}\n")
        f.write("\\toprule\n")
        # Header
        f.write("Metrica & Count & Mean & Std & Min & 25\\% & Median & 75\\% & Max \\\\\n")
        f.write("\\midrule\n")
        # Data rows
        for _, row in df.iterrows():
            metrica = str(row.iloc[0]).replace("_", "\\_")
            vals = [f"{v:.1f}" if pd.notna(v) else "--" for v in row.iloc[1:]]
            f.write(f"{metrica} & {' & '.join(vals)} \\\\\n")
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
    print(f"Tabela descritiva LaTeX salva: {out_path}")


def write_correlation_table(csv_path: str, out_path: str):
    """Escreve tabela de correlacoes formatada para LaTeX."""
    df = pd.read_csv(csv_path)

    with open(out_path, "w") as f:
        f.write("\\begin{tabular}{lccrrl}\n")
        f.write("\\toprule\n")
        f.write("RQ & Variavel X & Variavel Y & $\\rho$ & p-valor & Efeito \\\\\n")
        f.write("\\midrule\n")
        for _, row in df.iterrows():
            rq = row["RQ"]
            var_x = str(row["var_x"]).replace("_", "\\_")
            var_y = str(row["var_y"]).replace("_", "\\_")
            rho = f"{row['rho']:.4f}"
            pval = f"{row['p_value']:.4f}"
            effect = str(row["effect_size"])
            f.write(f"{rq} & {var_x} & {var_y} & {rho} & {pval} & {effect} \\\\\n")
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
    print(f"Tabela correlacao LaTeX salva: {out_path}")


if __name__ == "__main__":
    write_descriptive_table("report/tables/descriptive_stats.csv",
                            "report/tables/descriptive_stats.tex")
    write_correlation_table("report/tables/correlation_results.csv",
                            "report/tables/correlation_results.tex")
