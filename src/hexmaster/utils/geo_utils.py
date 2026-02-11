# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import math


def calculate_distance(ref_town: dict, target_town: dict) -> float:
    """Calculates distance between two towns using Cartesian-Staggered formula."""
    if not all(k in ref_town for k in ("q", "r", "x", "y")) or not all(k in target_town for k in ("q", "r", "x", "y")):
        return 0.0

    # SQRT3 ~= 1.73205
    SQRT3 = 1.73205
    x1 = ref_town["q"] * 1.5 + (ref_town["x"] - 0.5) * 2.0
    y1 = ref_town["r"] * SQRT3 + (ref_town["y"] - 0.5) * SQRT3

    x2 = target_town["q"] * 1.5 + (target_town["x"] - 0.5) * 2.0
    y2 = target_town["r"] * SQRT3 + (target_town["y"] - 0.5) * SQRT3

    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
