"""Plotting helpers (matplotlib, headless ``Agg`` backend). Every function writes a PNG and returns
its path so scripts can log where artifacts landed."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .backtest import BacktestResult  # noqa: E402


def plot_table(df: pd.DataFrame, path: str, title: str = "", float_fmt: str = "{:.3f}",
               index_label: str = "") -> str:
    """Render a DataFrame as a clean PNG table (the index becomes the first column)."""
    show = df.copy()
    for c in show.columns:
        if pd.api.types.is_numeric_dtype(show[c]):
            show[c] = show[c].map(lambda v: float_fmt.format(v) if pd.notna(v) else "")
    cells = show.reset_index().values.tolist()
    col_labels = [index_label or (df.index.name or "")] + list(show.columns)
    ncols = len(col_labels)

    # First column holds the (possibly long) row labels — give it width proportional to its text.
    label_len = max([len(str(c)) for c in col_labels[:1]]
                    + [len(str(r[0])) for r in cells])
    w0 = 0.10 * label_len + 0.6          # inches for the label column
    other_w = 1.6                        # inches per numeric column
    fig_w = w0 + other_w * (ncols - 1) + 0.6
    fig, ax = plt.subplots(figsize=(fig_w, 0.5 * (len(cells) + 1) + 1.0))
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=12, pad=12, loc="left")
    tbl = ax.table(cellText=cells, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    w0_frac = w0 / (w0 + other_w * (ncols - 1))
    other_frac = (1 - w0_frac) / (ncols - 1)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_width(w0_frac if c == 0 else other_frac)
        if r == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
        elif c == 0:
            cell.set_text_props(fontweight="bold", horizontalalignment="left")
            cell.set_facecolor("#f2f4f5")
            cell.PAD = 0.03
        cell.set_edgecolor("#d0d3d4")
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_price_signals(df: pd.DataFrame, frame: pd.DataFrame, path: str, title: str = "") -> str:
    """Price with the EMA ribbon and green/red long/short state shading (the chart's bar colors)."""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df.index, df["close"], color="black", lw=0.8, label="close")
    ax.plot(frame.index, frame["ema_fast"], color="tab:blue", lw=0.7, label="EMA fast")
    ax.plot(frame.index, frame["ema_mid"], color="tab:orange", lw=0.7, label="EMA mid")
    ax.plot(frame.index, frame["ema_slow"], color="tab:red", lw=0.7, label="EMA slow")
    ax.fill_between(df.index, df["close"].min(), df["close"].max(),
                    where=frame["buysignal"] == 1, color="green", alpha=0.08)
    ax.fill_between(df.index, df["close"].min(), df["close"].max(),
                    where=frame["sellsignal"] == 1, color="red", alpha=0.08)
    ax.set_title(title or "Trend Reversal — price, EMA ribbon & signal state")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_equity(results: dict[str, BacktestResult], path: str, title: str = "Equity curves",
                benchmark: pd.Series | None = None) -> str:
    fig, ax = plt.subplots(figsize=(14, 6))
    for name, res in results.items():
        ax.plot(res.equity.index, res.equity.values, lw=1.0, label=name)
    if benchmark is not None:
        ax.plot(benchmark.index, benchmark.values, lw=1.2, ls="--", color="black", label="buy & hold")
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_ylabel("growth of $1 (log)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_drawdown(equity: pd.Series, path: str, title: str = "Drawdown") -> str:
    dd = equity / equity.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(14, 3.5))
    ax.fill_between(dd.index, dd.values, 0, color="tab:red", alpha=0.4)
    ax.set_title(title)
    ax.set_ylabel("drawdown")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_heatmap(metrics_df: pd.DataFrame, x: str, y: str, value: str, path: str,
                 title: str = "") -> str:
    """Heatmap of a metric across two parameters — read for stable plateaus, not lone peaks."""
    pivot = metrics_df.pivot_table(index=y, columns=x, values=value, aggfunc="mean")
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, aspect="auto", origin="lower", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title(title or f"{value} across ({x}, {y})")
    fig.colorbar(im, ax=ax, label=value)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _draw_panel(ax, df: pd.DataFrame, frame: pd.DataFrame, lookback: int, title: str = "",
                legend: bool = False, n_ticks: int = 8, arrow_size: int = 160,
                label_every_bar: bool = False, body_width: float = 0.6) -> None:
    """Paint one Trend Reversal candle panel onto ``ax``: candles coloured by signal state
    (green=buy, red=sell, gray=neutral), the EMA 9/14/21 ribbon, and BUY ▲ / SELL ▼ arrows.

    ``label_every_bar`` puts a date tick under *every* candle (for short, read-the-paints windows);
    ``body_width`` widens the candle bodies for sparse windows."""
    from matplotlib.patches import Rectangle

    d = df.iloc[-lookback:]
    f = frame.iloc[-lookback:]
    x = np.arange(len(d))
    buysig = f["buysignal"].values
    sellsig = f["sellsignal"].values
    o, h, l, c = d["open"].values, d["high"].values, d["low"].values, d["close"].values

    hw = body_width / 2
    for i in x:
        col = "green" if buysig[i] == 1 else "red" if sellsig[i] == 1 else "0.6"
        ax.vlines(i, l[i], h[i], color=col, linewidth=1.0, zorder=2)
        body = abs(c[i] - o[i]) or (h[i] - l[i]) * 0.001
        ax.add_patch(Rectangle((i - hw, min(o[i], c[i])), body_width, body, color=col, zorder=3))

    ax.plot(x, f["ema_fast"], color="tab:blue", lw=0.9, label="EMA 9")
    ax.plot(x, f["ema_mid"], color="tab:orange", lw=0.9, label="EMA 14")
    ax.plot(x, f["ema_slow"], color="tab:purple", lw=0.9, label="EMA 21")

    prev = np.roll(buysig, 1)
    prev[0] = buysig[0]
    buy_x = x[(buysig == 1) & (prev == 0)]
    sell_x = x[(buysig == 0) & (prev == 1)]
    ax.scatter(buy_x, l[buy_x] * 0.985, marker="^", s=arrow_size, color="green",
               edgecolor="black", linewidth=0.5, zorder=6, label="BUY")
    ax.scatter(sell_x, h[sell_x] * 1.015, marker="v", s=arrow_size, color="red",
               edgecolor="black", linewidth=0.5, zorder=6, label="SELL")

    if label_every_bar:
        tick_pos = x
        rotation = 90
    else:
        nt = min(n_ticks, len(d))
        tick_pos = np.linspace(0, len(d) - 1, nt, dtype=int)
        rotation = 0
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([d.index[p].strftime("%m-%d") for p in tick_pos], rotation=rotation,
                       fontsize=7)
    ax.set_xlim(-0.6, len(d) - 0.4)
    ax.grid(axis="x", color="0.9", lw=0.5, zorder=0)
    ax.set_title(title or "Trend Reversal — trade signals", fontsize=10, loc="left")
    ax.tick_params(axis="y", labelsize=7)
    if legend:
        ax.legend(loc="upper left", fontsize=8)


def plot_trade_chart(df: pd.DataFrame, frame: pd.DataFrame, path: str, title: str = "",
                     lookback: int = 180) -> str:
    """Tradeable chart: candles colored by signal state, the EMA ribbon, and BUY ▲ / SELL ▼ arrows."""
    fig, ax = plt.subplots(figsize=(16, 8))
    _draw_panel(ax, df, frame, lookback, title, legend=True, n_ticks=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_multi_painted(panels: list[dict], path: str, lookback: int = 14,
                       title: str = "", footer_text: str = "") -> str:
    """One tall, scrollable PNG stacking a painted candle panel per ticker.

    ``panels`` is a list of ``{"df", "frame", "title"}`` dicts; each is drawn as its own row showing
    the last ``lookback`` bars with full candles and a date under *every* bar, so you can read exactly
    where the buy/sell paints land. ``footer_text`` (if given) is rendered verbatim in a monospace
    block beneath all panels — used to embed the scanner's top-N shortlist. Viewed by scrolling."""
    n = len(panels)
    panel_in = 2.7
    if footer_text:
        text_lines = footer_text.count("\n") + 1
        footer_in = text_lines * 0.135 + 0.4
        fig, axes = plt.subplots(n + 1, 1, figsize=(13, panel_in * n + footer_in + 0.6),
                                 squeeze=False,
                                 gridspec_kw={"height_ratios": [panel_in] * n + [footer_in]})
        panel_axes, footer_ax = axes[:n, 0], axes[n, 0]
    else:
        fig, axes = plt.subplots(n, 1, figsize=(13, panel_in * n + 0.6), squeeze=False)
        panel_axes, footer_ax = axes[:, 0], None

    for ax, p in zip(panel_axes, panels):
        _draw_panel(ax, p["df"], p["frame"], lookback, p.get("title", ""),
                    legend=False, arrow_size=150, label_every_bar=True, body_width=0.7)
    panel_axes[0].legend(loc="upper left", fontsize=7, ncol=5)

    if footer_ax is not None:
        footer_ax.axis("off")
        footer_ax.text(0.0, 1.0, footer_text, family="monospace", fontsize=8.5,
                       va="top", ha="left", transform=footer_ax.transAxes)

    fig.suptitle(title or f"Trend Reversal — last {lookback} bars (scroll to view all)",
                 fontsize=13, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.997))
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_pbo(logits: np.ndarray, pbo: float, path: str) -> str:
    """Histogram of CSCV rank-logits; mass at/below zero is the probability of backtest overfitting."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(logits, bins=30, color="tab:purple", alpha=0.7)
    ax.axvline(0, color="black", ls="--")
    ax.set_title(f"Probability of Backtest Overfitting = {pbo:.2%}")
    ax.set_xlabel("rank logit (OOS performance of IS-best config)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
