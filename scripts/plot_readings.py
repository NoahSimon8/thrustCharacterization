"""
Plot averaged load-cell data using Plotly.

Usage:
    python scripts/plot_readings.py --input logs/readings.csv --out logs/readings_plot.html

Defaults:
    input: logs/readings.csv
    out:   logs/readings_plot.html

Notes:
    - Load cell 3 is highlighted (treated as the important average channel).
    - Requires: pandas, plotly
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    df = pd.read_csv(path)
    if "time_ms" not in df or "loadcell" not in df or "grams" not in df:
        raise ValueError("CSV missing required columns: time_ms, loadcell, grams")
    # Normalize time to start at zero seconds for nicer axes
    df["time_s"] = (df["time_ms"] - df["time_ms"].min()) / 1000.0
    # Convert grams to lbf (1 lbf = 453.59237 g)
    df["lbf"] = df["grams"] / 453.59237
    return df


def plot_grams(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = {1: "royalblue", 2: "darkorange", 3: "magenta"}

    for cell in sorted(df["loadcell"].unique()):
        sub = df[df["loadcell"] == cell]
        fig.add_trace(
            go.Scatter(
                x=sub["time_s"],
                y=sub["lbf"],
                mode="lines",
                name=f"lbf L{cell}",
                line=dict(color=colors.get(cell, None), width=4 if cell == 3 else 2),
            ),
            secondary_y=False,
        )

    if "throttle" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["time_s"],
                y=df["throttle"],
                mode="lines",
                name="throttle",
                line=dict(color="seagreen", dash="dot"),
            ),
            secondary_y=True,
        )

    fig.update_layout(
        title="Load Cells (lbf) with Throttle",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=60, b=60),
    )
    fig.update_xaxes(title_text="Time (s)")
    fig.update_yaxes(title_text="lbf", secondary_y=False)
    fig.update_yaxes(title_text="Throttle", secondary_y=True)
    return fig


def plot_raw(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    colors = {1: "royalblue", 2: "darkorange", 3: "magenta"}

    for cell in sorted(df["loadcell"].unique()):
        sub = df[df["loadcell"] == cell]
        fig.add_trace(
            go.Scatter(
                x=sub["time_s"],
                y=sub["raw"],
                mode="lines",
                name=f"raw L{cell}",
                line=dict(color=colors.get(cell, None), width=4 if cell == 3 else 2),
            )
        )

    fig.update_layout(
        title="Load Cells (raw counts)",
        xaxis_title="Time (s)",
        yaxis_title="Raw",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig


def plot_grams_vs_throttle(df: pd.DataFrame) -> go.Figure:
    if "throttle" not in df.columns:
        raise ValueError("throttle column missing in CSV; rerun firmware to log throttle.")
    fig = go.Figure()
    colors = {1: "royalblue", 2: "darkorange", 3: "magenta"}
    for cell in sorted(df["loadcell"].unique()):
        sub = df[df["loadcell"] == cell]
        fig.add_trace(
            go.Scatter(
                x=sub["throttle"],
                y=sub["lbf"],
                mode="markers",
                name=f"lbf vs throttle L{cell}",
                marker=dict(color=colors.get(cell, None), size=6 if cell == 3 else 5, opacity=0.7),
            )
        )
    fig.update_layout(
        title="lbf vs Throttle",
        xaxis_title="Throttle",
        yaxis_title="lbf",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Plot load-cell readings.")
    parser.add_argument("--input", "-i", type=Path, default=Path("logs/readings.csv"))
    parser.add_argument("--out", "-o", type=Path, default=Path("logs/readings_plot.html"))
    args = parser.parse_args(argv)

    df = load_data(args.input)

    figs = [plot_grams(df), plot_raw(df), plot_grams_vs_throttle(df)]

    # Combine figures into one HTML
    html_parts = [f.to_html(full_html=False, include_plotlyjs=False) for f in figs]
    out_html = (
        "<html><head>"
        '<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>'
        "</head><body>"
        + "<hr>".join(html_parts)
        + "</body></html>"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_html, encoding="utf-8")
    print(f"Wrote plots to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
