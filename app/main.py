import streamlit as st
from src.engine import (
    GRINDER_064S,
    RecipeInput,
    generate_recipe,
    dial_in_assistant,
    save_history_record,
    load_history_records,
)
from datetime import datetime


st.title("Coffee Recipe Generator ☕")

roast_level = st.selectbox("Roast level", ["light", "medium", "dark"])
method = st.selectbox("Brew method", ["V60", "ESPRESSO"])
grinder = st.selectbox("Grinder", [GRINDER_064S])
taste_goal = st.selectbox("Taste goal", ["balanced", "sweeter", "brighter", "less_bitter"])

st.subheader("Inputs")

# Baseline calibration (optional)
if method == "V60":
    baseline = st.number_input(
        "My baseline grind (064S dial) for V60 (optional)",
        min_value=8.0, max_value=13.0, value=12.5, step=0.1
    )
else:
    baseline = st.number_input(
        "My baseline grind (064S dial) for Espresso (optional)",
        min_value=1.0, max_value=4.0, value=2.2, step=0.1
    )

use_baseline = st.checkbox("Use my baseline", value=True)
baseline_grind = float(baseline) if use_baseline else None

if method == "V60":
    coffee_g = st.number_input("Coffee (g)", min_value=5.0, max_value=60.0, value=18.0, step=1.0)
    water_g = st.number_input("Water (g)", min_value=50.0, max_value=1500.0, value=300.0, step=10.0)
    ratio_now = round(water_g / coffee_g, 1)
    st.caption(f"Current ratio: 1:{ratio_now}")
else:
    st.caption("Typical espresso: 18g in → ~36g out in ~25–30s")
    coffee_g = st.number_input("Dose (g)", min_value=10.0, max_value=25.0, value=18.0, step=0.5)
    water_g = st.number_input("Target yield (g out)", min_value=15.0, max_value=80.0, value=36.0, step=1.0)
    ratio_now = round(water_g / coffee_g, 2)
    st.caption(f"Current yield ratio: 1:{ratio_now}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Recipe")

    if st.button("Generate recipe"):
        inp = RecipeInput(
            roast_level=roast_level,
            method=method,
            grinder=grinder,
            coffee_g=coffee_g,
            water_g=water_g,
            taste_goal=taste_goal,
            baseline_grind=baseline_grind,
        )

        recipe = generate_recipe(inp)

        # store in session state so we can save later
        st.session_state["last_recipe"] = recipe
        st.session_state["last_input"] = inp

    if "last_recipe" in st.session_state:
        recipe = st.session_state["last_recipe"]
        inp = st.session_state["last_input"]

        if method == "V60":
            st.write(f"**Ratio:** 1:{recipe['ratio']}")
        else:
            st.write(f"**Yield ratio:** 1:{recipe['ratio']}")

        st.write(f"**Water temp:** {recipe['water_temp_c']} °C")

        if method == "V60":
            st.write(f"**Target time:** ~{recipe['target_time_s']//60}:{recipe['target_time_s']%60:02d}")
        else:
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

        st.divider()

        if st.button("Save this session"):
            record = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "method": recipe["method"],
                "roast_level": inp.roast_level,
                "taste_goal": inp.taste_goal,
                "coffee_g": inp.coffee_g,
                "water_g": inp.water_g,
                "ratio": recipe["ratio"],
                "water_temp_c": recipe["water_temp_c"],
                "target_time_s": recipe["target_time_s"],
                "grind_setting": recipe["grind_setting"],
            }
            save_history_record(record)
            st.success("Saved to data/history.json ✅")

with col2:
    st.subheader("Dial-in Assistant 🔧")

    if method == "ESPRESSO":
        time_s = st.number_input("Actual shot time (s)", min_value=10, max_value=60, value=28, step=1)
    else:
        time_s = st.number_input("Actual brew time (s)", min_value=60, max_value=400, value=180, step=5)

    current_grind = st.number_input(
        "Grind setting you used (064S dial)",
        min_value=1.0 if method == "ESPRESSO" else 8.0,
        max_value=4.0 if method == "ESPRESSO" else 13.0,
        value=2.2 if method == "ESPRESSO" else 12.5,
        step=0.1
    )

    taste_result = st.selectbox(
        "How did it taste?",
        ["balanced", "too_sour", "too_bitter", "too_weak", "too_strong"]
    )

    if st.button("Get dial-in advice"):
        advice = dial_in_assistant(
            method=method,
            roast_level=roast_level,
            current_grind=float(current_grind),
            shot_or_brew_time_s=int(time_s),
            taste_result=taste_result,
            current_ratio=float(ratio_now),
        )

        st.write(f"**Suggested grind:** {advice['suggested_grind']} ({advice['direction']})")
        st.caption(f"Target time: ~{advice['target_time_s']}s  |  Your time: {advice['time_s']}s")

        st.write("**Notes:**")
        for n in advice["notes"]:
            st.write(f"- {n}")

    st.divider()
    st.subheader("History 🗂️")

    if st.button("Show last 10 records"):
        rows = load_history_records(limit=10)
        if not rows:
            st.info("No history yet. Save a session first.")
        else:
            st.table([
                {
                    "time": r.get("timestamp", ""),
                    "method": r.get("method", ""),
                    "roast": r.get("roast_level", ""),
                    "ratio": r.get("ratio", ""),
                    "grind": r.get("grind_setting", {}).get("recommended", ""),
                }
                for r in rows
            ])


