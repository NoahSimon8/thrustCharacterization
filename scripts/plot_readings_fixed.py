"""
Plot averaged load-cell data using Plotly.

Usage:
    python plot_readings_fixed.py --input readings.csv --out readings_plot.html

Notes:
    - Converts pandas Series to plain Python lists before plotting. This avoids
      Plotly's binary-array HTML encoding, which can produce blank graphs in
      some browser/JS combinations.
    - Load cell 3 is highlighted.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


REQUIRED_COLUMNS = {"time_ms", "loadcell", "grams"}
OPTIONAL_NUMERIC_COLUMNS = {"raw", "throttle", "battery_voltage", "scale", "tare"}


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

    # Coerce expected numeric columns defensively.
    for col in (REQUIRED_COLUMNS | OPTIONAL_NUMERIC_COLUMNS) & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows that cannot be plotted.
    df = df.dropna(subset=["time_ms", "loadcell", "grams"]).copy()

    # Normalize time to start at zero seconds for nicer axes.
    df["time_s"] = (df["time_ms"] - df["time_ms"].min()) / 1000.0

    # Convert grams to lbf (1 lbf = 453.59237 g)
    df["lbf"] = df["grams"] / 453.59237

    return df.sort_values(["time_s", "loadcell"]).reset_index(drop=True)


def _series_as_lists(df: pd.DataFrame, x_col: str, y_col: str) -> tuple[list[float], list[float]]:
    sub = df[[x_col, y_col]].dropna()
    return sub[x_col].tolist(), sub[y_col].tolist()


def _throttle_by_time(df: pd.DataFrame) -> pd.DataFrame:
    if "throttle" not in df.columns:
        return pd.DataFrame(columns=["time_s", "throttle"])

    throttle_df = df[["time_s", "throttle"]].dropna()
    # Each timestamp appears once per load cell; keep one throttle value per time.
    return throttle_df.drop_duplicates(subset=["time_s"]).sort_values("time_s")


def plot_grams(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = {1: "royalblue", 2: "darkorange", 3: "magenta"}

    for cell in sorted(df["loadcell"].dropna().unique()):
        sub = df[df["loadcell"] == cell]
        x, y = _series_as_lists(sub, "time_s", "lbf")
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=f"lbf L{int(cell)}",
                line=dict(color=colors.get(int(cell), None), width=4 if int(cell) == 3 else 2),
            ),
            secondary_y=False,
        )

    throttle_df = _throttle_by_time(df)
    if not throttle_df.empty:
        x, y = _series_as_lists(throttle_df, "time_s", "throttle")
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
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
    if "raw" not in df.columns:
        raise ValueError("raw column missing in CSV.")

    fig = go.Figure()
    colors = {1: "royalblue", 2: "darkorange", 3: "magenta"}

    for cell in sorted(df["loadcell"].dropna().unique()):
        sub = df[df["loadcell"] == cell]
        x, y = _series_as_lists(sub, "time_s", "raw")
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=f"raw L{int(cell)}",
                line=dict(color=colors.get(int(cell), None), width=4 if int(cell) == 3 else 2),
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

    for cell in sorted(df["loadcell"].dropna().unique()):
        sub = df[df["loadcell"] == cell]
        x, y = _series_as_lists(sub, "throttle", "lbf")
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                name=f"lbf vs throttle L{int(cell)}",
                marker=dict(color=colors.get(int(cell), None), size=6 if int(cell) == 3 else 5, opacity=0.7),
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


def plot_grams_vs_voltage(df: pd.DataFrame) -> go.Figure:
    if "battery_voltage" not in df.columns:
        raise ValueError("battery_voltage column missing in CSV; rerun firmware to log battery voltage.")

    fig = go.Figure()
    colors = {1: "royalblue", 2: "darkorange", 3: "magenta"}

    for cell in sorted(df["loadcell"].dropna().unique()):
        sub = df[df["loadcell"] == cell]
        x, y = _series_as_lists(sub, "battery_voltage", "lbf")
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                name=f"lbf vs voltage L{int(cell)}",
                marker=dict(color=colors.get(int(cell), None), size=6 if int(cell) == 3 else 5, opacity=0.7),
            )
        )

    fig.update_layout(
        title="lbf vs Battery Voltage",
        xaxis_title="Battery Voltage (V)",
        yaxis_title="lbf",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig


def write_combined_html(figs: list[go.Figure], out_path: Path) -> None:
    html_parts: list[str] = []
    for i, fig in enumerate(figs):
        html_parts.append(
            pio.to_html(
                fig,
                full_html=False,
                include_plotlyjs="cdn" if i == 0 else False,
            )
        )

    out_html = (
        "<html><head><meta charset='utf-8'></head><body>"
        + "<hr>".join(html_parts)
        + "</body></html>"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_html, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Plot load-cell readings.")
    parser.add_argument("--input", "-i", type=Path, default=Path("logs/readings.csv"))
    parser.add_argument("--out", "-o", type=Path, default=Path("logs/readings_plot.html"))
    args = parser.parse_args(argv)

    df = load_data(args.input)
    figs = [plot_grams(df), plot_raw(df), plot_grams_vs_throttle(df), plot_grams_vs_voltage(df)]
    write_combined_html(figs, args.out)

    print(f"Wrote plots to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
