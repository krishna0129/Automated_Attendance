"""
Chart rendering.

Charts are rendered in memory and returned as ``data:`` URIs that templates
embed directly, so nothing is written into the static directory and
concurrent requests never overwrite each other's images.
"""

from __future__ import annotations

import base64
import io
from collections.abc import Sequence

import numpy as np
from matplotlib.figure import Figure

BRAND = "#8c1d2f"
PALETTE = ["#8c1d2f", "#1d4ed8", "#15803d", "#b45309", "#7c3aed", "#0e7490", "#be185d", "#4d7c0f"]


def _new_figure(width: float = 8, height: float = 4.5) -> tuple[Figure, object]:
    fig = Figure(figsize=(width, height), dpi=110, layout="tight")
    ax = fig.add_subplot()
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    return fig, ax


def _to_data_uri(fig: Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def bar_chart(labels: Sequence[str], values: Sequence[float], *, xlabel: str, ylabel: str) -> str:
    fig, ax = _new_figure()
    ax.bar(labels, values, color=BRAND)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=45 if len(labels) > 6 else 0)
    return _to_data_uri(fig)


def line_chart(labels: Sequence[str], values: Sequence[float], *, xlabel: str, ylabel: str) -> str:
    fig, ax = _new_figure()
    ax.plot(labels, values, color=BRAND, marker="o", linewidth=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0, top=max([*values, 1]) * 1.15)
    ax.yaxis.get_major_locator().set_params(integer=True)
    return _to_data_uri(fig)


def scatter_by_label(points: np.ndarray, labels: Sequence[str]) -> str:
    """2-D scatter plot coloured by label (used for the training visualisation)."""
    fig, ax = _new_figure(8, 6)
    ax.grid(alpha=0.3)
    labels = np.asarray(labels)
    for i, name in enumerate(sorted(set(labels))):
        mask = labels == name
        ax.scatter(points[mask, 0], points[mask, 1], s=14, label=name, color=PALETTE[i % len(PALETTE)])
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    return _to_data_uri(fig)
