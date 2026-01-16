from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import json


# --- Grinder profiles (MVP: only Timemore Sculptor 064S) ---
GRINDER_064S = "TIMEMORE Sculptor 064S"

GRINDER_RANGES = {
    GRINDER_064S: {
        "V60": {"min": 8.0, "max": 13.0, "unit": "dial"},
        "ESPRESSO": {"min": 1.0, "max": 4.0, "unit": "dial"},
    }
}


# --- Storage (local JSON) ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_PATH = DATA_DIR / "history.json"


@dataclass(frozen=True)
class RecipeInput:
    roast_level: str          # "light" | "medium" | "dark"
    method: str               # "V60" | "ESPRESSO"
    grinder: str              # "TIMEMORE Sculptor 064S"
    coffee_g: float
    water_g: float            # V60: total water; Espresso: target yield (g out)
    taste_goal: str           # "balanced" | "sweeter" | "brighter" | "less_bitter"
    baseline_grind: Optional[float] = None  # user calibration, dial number


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def save_history_record(record: Dict[str, Any]) -> None:
    """
    Append a record to data/history.json (creates file if missing).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing: List[Dict[str, Any]] = []
    if HISTORY_PATH.exists():
        try:
            existing = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

    existing.append(record)
    HISTORY_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def load_history_records(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Load last N records from history.
    """
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return data[-limit:][::-1]  # newest first
    except Exception:
        return []


def recommend_grind_setting_064s(
    method: str,
    taste_goal: str,
    roast_level: str,
    baseline_grind: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Returns a recommended dial setting + range for Timemore Sculptor 064S.
    If baseline_grind is provided, we start from it (personal calibration).
    """

    if method not in ("V60", "ESPRESSO"):
        raise ValueError("Method must be V60 or ESPRESSO")

    r = GRINDER_RANGES[GRINDER_064S][method]
    gmin, gmax = float(r["min"]), float(r["max"])

    roast = roast_level.lower().strip()

    # Default baseline (if user didn't provide calibration)
    if method == "V60":
        if roast == "light":
            default_base = 12.5
        elif roast == "medium":
            default_base = 11.0
        elif roast == "dark":
            default_base = 10.0
        else:
            default_base = (gmin + gmax) / 2.0
    else:  # ESPRESSO
        if roast == "light":
            default_base = 2.5
        elif roast == "medium":
            default_base = 2.0
        elif roast == "dark":
            default_base = 1.6
        else:
            default_base = (gmin + gmax) / 2.0

    base = _clamp(float(baseline_grind), gmin, gmax) if baseline_grind is not None else default_base

    # Taste goal shifts (for "generate recipe" suggestions)
    t = taste_goal.lower().strip()
    shift = 0.0

    if method == "V60":
        if t == "brighter":
            shift = -0.4
        elif t == "sweeter":
            shift = -0.2
        elif t == "less_bitter":
            shift = +0.4
        elif t == "balanced":
            shift = 0.0
        else:
            raise ValueError("taste_goal must be: balanced, sweeter, brighter, or less_bitter")
    else:  # ESPRESSO
        if t == "brighter":
            shift = -0.2
        elif t == "sweeter":
            shift = -0.1
        elif t == "less_bitter":
            shift = +0.2
        elif t == "balanced":
            shift = 0.0
        else:
            raise ValueError("taste_goal must be: balanced, sweeter, brighter, or less_bitter")

    rec = _clamp(base + shift, gmin, gmax)

    return {
        "grinder": GRINDER_064S,
        "method": method,
        "unit": r["unit"],
        "baseline_used": round(_clamp(base, gmin, gmax), 1),
        "recommended": round(rec, 1),
        "range": f"{gmin:.1f}–{gmax:.1f}",
    }


def dial_in_assistant(
    method: str,
    roast_level: str,
    current_grind: float,
    shot_or_brew_time_s: int,
    taste_result: str,
    current_ratio: float,
) -> Dict[str, Any]:
    """
    Given what actually happened (time + taste), return action steps.
    - method: "V60" or "ESPRESSO"
    - current_grind: current dial setting used
    - shot_or_brew_time_s: espresso shot time (seconds) or V60 total brew time (seconds)
    - taste_result: "too_sour", "too_bitter", "too_weak", "too_strong", "balanced"
    - current_ratio: V60 water/coffee OR espresso yield/dose
    """

    method = method.upper().strip()
    roast = roast_level.lower().strip()

    if method not in ("V60", "ESPRESSO"):
        raise ValueError("method must be V60 or ESPRESSO")

    if method == "ESPRESSO":
        target_time = 28
        time_tol = 3
        gmin, gmax = 1.0, 4.0
        base_step = 0.1
    else:
        target_time = 180
        time_tol = 15
        gmin, gmax = 8.0, 13.0
        base_step = 0.2

    current_grind = _clamp(float(current_grind), gmin, gmax)

    taste = taste_result.lower().strip()
    suggestions: List[str] = []
    grind_delta = 0.0

    too_fast = shot_or_brew_time_s < (target_time - time_tol)
    too_slow = shot_or_brew_time_s > (target_time + time_tol)

    if taste in ("too_sour", "too_weak"):
        grind_delta -= base_step
        if too_fast:
            grind_delta -= base_step
        suggestions.append("Likely under-extracted: go a bit finer.")
        if method == "ESPRESSO":
            suggestions.append("If still sour: consider slightly increasing yield (e.g., +2g out).")
        else:
            suggestions.append("If still sour: pour slightly slower or increase brew time a bit.")
    elif taste in ("too_bitter", "too_strong"):
        grind_delta += base_step
        if too_slow:
            grind_delta += base_step
        suggestions.append("Likely over-extracted: go a bit coarser.")
        if method == "ESPRESSO":
            suggestions.append("If still bitter: consider slightly reducing yield (e.g., -2g out).")
        else:
            suggestions.append("If still bitter: shorten brew time slightly or reduce agitation.")
    elif taste == "balanced":
        suggestions.append("Taste is balanced. Only adjust if you want a different style (brighter/sweeter).")
        if too_fast:
            suggestions.append("Time was fast. If you want more body, go a tiny bit finer.")
            grind_delta -= base_step
        elif too_slow:
            suggestions.append("Time was slow. If you want cleaner cup, go a tiny bit coarser.")
            grind_delta += base_step
    else:
        raise ValueError("taste_result must be: too_sour, too_bitter, too_weak, too_strong, balanced")

    if taste != "balanced":
        if too_fast:
            suggestions.append("Time is fast vs target. A finer grind should slow it down.")
        elif too_slow:
            suggestions.append("Time is slow vs target. A coarser grind should speed it up.")

    if roast == "light" and taste in ("too_sour", "too_weak"):
        suggestions.append("Light roasts often need a bit more extraction than you expect.")
    if roast == "dark" and taste in ("too_bitter", "too_strong"):
        suggestions.append("Dark roasts can get bitter quickly—small changes only.")

    new_grind = _clamp(current_grind + grind_delta, gmin, gmax)

    direction = "no change"
    if new_grind > current_grind:
        direction = f"coarser (+{round(new_grind - current_grind, 1)})"
    elif new_grind < current_grind:
        direction = f"finer (-{round(current_grind - new_grind, 1)})"

    return {
        "method": method,
        "target_time_s": target_time,
        "time_s": int(shot_or_brew_time_s),
        "current_grind": round(current_grind, 1),
        "suggested_grind": round(new_grind, 1),
        "direction": direction,
        "notes": suggestions,
        "ratio_used": current_ratio,
    }


def generate_recipe(inp: RecipeInput) -> Dict[str, Any]:
    roast = inp.roast_level.lower().strip()
    method = inp.method

    if method == "V60":
        if roast == "light":
            temp_c = 94
            target_time_s = 180
        elif roast == "medium":
            temp_c = 92
            target_time_s = 170
        elif roast == "dark":
            temp_c = 90
            target_time_s = 155
        else:
            raise ValueError("roast_level must be: light, medium, or dark")
    elif method == "ESPRESSO":
        if roast == "light":
            temp_c = 94
        elif roast == "medium":
            temp_c = 93
        elif roast == "dark":
            temp_c = 92
        else:
            raise ValueError("roast_level must be: light, medium, or dark")
        target_time_s = 28
    else:
        raise ValueError("method must be: V60 or ESPRESSO")

    if inp.coffee_g <= 0:
        raise ValueError("coffee_g must be > 0")

    if method == "V60":
        ratio = round(inp.water_g / inp.coffee_g, 1)
    else:
        ratio = round(inp.water_g / inp.coffee_g, 2)

    adjustments: List[str] = []
    taste = inp.taste_goal.lower().strip()

    if method == "V60":
        if taste == "brighter":
            temp_c += 1
            adjustments.append("Sour/under-extracted? Go slightly finer or pour slower.")
        elif taste == "sweeter":
            target_time_s += 10
            adjustments.append("Try +10s total time with an even pour.")
        elif taste == "less_bitter":
            temp_c -= 1
            target_time_s -= 10
            adjustments.append("Bitter/over-extracted? Go slightly coarser or shorten time.")
        elif taste == "balanced":
            adjustments.append("Baseline recipe. Adjust one variable at a time.")
        else:
            raise ValueError("taste_goal must be: balanced, sweeter, brighter, or less_bitter")
    else:
        if taste == "brighter":
            adjustments.append("If sour/fast: grind finer OR increase yield slightly.")
        elif taste == "sweeter":
            adjustments.append("Keep dose consistent; adjust grind in tiny steps; aim 25–30s.")
        elif taste == "less_bitter":
            adjustments.append("If bitter/slow: grind coarser OR reduce yield slightly.")
        elif taste == "balanced":
            adjustments.append("Adjust grind first, then yield, then temperature.")
        else:
            raise ValueError("taste_goal must be: balanced, sweeter, brighter, or less_bitter")

    grind_info = recommend_grind_setting_064s(
        method=method,
        taste_goal=inp.taste_goal,
        roast_level=inp.roast_level,
        baseline_grind=inp.baseline_grind,
    )

    if method == "V60":
        steps = [
            f"Heat water to {temp_c}°C.",
            "Rinse filter and preheat dripper/server.",
            f"Set grinder to {grind_info['recommended']} on {grind_info['grinder']} "
            f"(range {grind_info['range']}, baseline used {grind_info['baseline_used']}).",
            f"Add {inp.coffee_g:.0f}g coffee.",
            "Bloom with ~2x coffee weight water for 30–45s.",
            "Continue pouring in slow circles to reach total water.",
            f"Target total brew time: ~{target_time_s//60}:{target_time_s%60:02d}.",
        ]
    else:
        steps = [
            f"Heat machine/water to ~{temp_c}°C (approx).",
            f"Set grinder to {grind_info['recommended']} on {grind_info['grinder']} "
            f"(range {grind_info['range']}, baseline used {grind_info['baseline_used']}).",
            f"Dose {inp.coffee_g:.0f}g into portafilter.",
            "Distribute evenly and tamp level.",
            f"Target yield: {inp.water_g:.0f}g out (ratio ~1:{ratio}).",
            f"Target shot time: ~{target_time_s}s.",
        ]

    return {
        "method": method,
        "coffee_g": inp.coffee_g,
        "water_g": inp.water_g,
        "ratio": ratio,
        "water_temp_c": temp_c,
        "target_time_s": target_time_s,
        "grind_setting": grind_info,
        "steps": steps,
        "adjustments": adjustments,
    }



