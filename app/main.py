import os
import sys

# Ensure repo root is on PYTHONPATH (needed for Streamlit Cloud)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from src.engine import GRINDER_064S, RecipeInput, generate_recipe


st.set_page_config(page_title="Coffee Recipe Generator", page_icon="☕", layout="centered")
st.title("Coffee Recipe Generator ☕")


# ----------------------------
# Default session state values
# ----------------------------
defaults = {
    "roast_level": "light",
    "method": "V60",
    "coffee_g": 18.0,
    "water_g": 300.0,
    "taste_goal": "balanced",
    "use_baseline": True,
    "baseline_v60": 12.5,
    "baseline_espresso": 2.2,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ----------------------------
# Quick Presets
# ----------------------------
st.subheader("Quick presets")

c1, c2 = st.columns(2)

if c1.button("Preset: V60 Light (18g / 300g)"):
    st.session_state["roast_level"] = "light"
    st.session_state["method"] = "V60"
    st.session_state["coffee_g"] = 18.0
    st.session_state["water_g"] = 300.0
    st.session_state["taste_goal"] = "balanced"
    st.session_state["use_baseline"] = True
    st.rerun()

if c2.button("Preset: Espresso Light (18g in / 36g out)"):
    st.session_state["roast_level"] = "light"
    st.session_state["method"] = "ESPRESSO"
    st.session_state["coffee_g"] = 18.0
    st.session_state["water_g"] = 36.0
    st.session_state["taste_goal"] = "balanced"
    st.session_state["use_baseline"] = True
    st.rerun()


# ----------------------------
# Inputs
# ----------------------------
st.subheader("Inputs")

grinder = st.selectbox("Grinder", [GRINDER_064S])

roast_level = st.selectbox(
    "Roast level",
    ["light", "medium", "dark"],
    key="roast_level",
)

method = st.selectbox(
    "Brew method",
    ["V60", "ESPRESSO"],
    key="method",
)

taste_goal = st.selectbox(
    "Taste goal",
    ["balanced", "sweeter", "brighter", "less_bitter"],
    key="taste_goal",
)

# Baseline (per method)
st.markdown("### Grinder calibration (optional)")
use_baseline = st.checkbox("Use my baseline", key="use_baseline")

if st.session_state["method"] == "V60":
    baseline = st.number_input(
        "My baseline grind (064S dial) for V60",
        min_value=8.0,
        max_value=13.0,
        value=float(st.session_state["baseline_v60"]),
        step=0.1,
        key="baseline_v60",
    )
    baseline_grind = float(baseline) if use_baseline else None

    coffee_g = st.number_input(
        "Coffee (g)",
        min_value=5.0,
        max_value=60.0,
        value=float(st.session_state["coffee_g"]),
        step=1.0,
        key="coffee_g",
    )
    water_g = st.number_input(
        "Water (g)",
        min_value=50.0,
        max_value=1500.0,
        value=float(st.session_state["water_g"]),
        step=10.0,
        key="water_g",
    )
    st.caption(f"Current ratio: 1:{round(water_g / coffee_g, 1)}")

else:
    baseline = st.number_input(
        "My baseline grind (064S dial) for Espresso",
        min_value=1.0,
        max_value=4.0,
        value=float(st.session_state["baseline_espresso"]),
        step=0.1,
        key="baseline_espresso",
    )
    baseline_grind = float(baseline) if use_baseline else None

    st.caption("Typical espresso: 18g in → ~36g out in ~25–30s")
    coffee_g = st.number_input(
        "Dose (g)",
        min_value=10.0,
        max_value=25.0,
        value=float(st.session_state["coffee_g"]),
        step=0.5,
        key="coffee_g",
    )
    water_g = st.number_input(
        "Target yield (g out)",
        min_value=15.0,
        max_value=80.0,
        value=float(st.session_state["water_g"]),
        step=1.0,
        key="water_g",
    )
    st.caption(f"Current yield ratio: 1:{round(water_g / coffee_g, 2)}")


# ----------------------------
# Generate
# ----------------------------
st.markdown("---")
if st.button("Generate recipe", type="primary"):
    inp = RecipeInput(
        roast_level=roast_level,
        method=method,
        grinder=grinder,
        coffee_g=float(coffee_g),
        water_g=float(water_g),
        taste_goal=taste_goal,
        baseline_grind=baseline_grind,
    )

    recipe = generate_recipe(inp)

    st.subheader("Recipe")

    if method == "V60":
        st.write(f"**Ratio:** 1:{recipe['ratio']}")
        st.write(f"**Water temp:** {recipe['water_temp_c']} °C")
        st.write(f"**Target time:** ~{recipe['target_time_s']//60}:{recipe['target_time_s']%60:02d}")
    else:
        st.write(f"**Yield ratio:** 1:{recipe['ratio']}")
        st.write(f"**Water temp:** {recipe['water_temp_c']} °C")
        st.write(f"**Target time:** ~{recipe['target_time_s']} s")

    gs = recipe["grind_setting"]
    st.write(
        f"**Grind setting ({gs['unit']}):** {gs['recommended']} "
        f"_(range {gs['range']}, baseline used {gs['baseline_used']})_"
    )

    st.subheader("Steps")
    for s in recipe["steps"]:
        st.write(f"- {s}")

    st.subheader("Adjustments")
    for a in recipe["adjustments"]:
        st.write(f"- {a}")

    # Copy-friendly output
    st.subheader("Copy-friendly recipe")
    recipe_text = "\n".join(recipe["steps"])
    st.text_area("Copy this", recipe_text, height=220)
