from src.engine import (
    RecipeInput,
    generate_recipe,
    dial_in_assistant,
    GRINDER_064S,
)


def test_generate_recipe_v60_runs():
    inp = RecipeInput(
        roast_level="light",
        method="V60",
        grinder=GRINDER_064S,
        coffee_g=18.0,
        water_g=300.0,
        taste_goal="balanced",
        baseline_grind=12.5,
    )

    recipe = generate_recipe(inp)

    assert recipe["method"] == "V60"
    assert "grind_setting" in recipe
    assert 8.0 <= recipe["grind_setting"]["recommended"] <= 13.0


def test_dial_in_assistant_espresso_returns_suggestion():
    advice = dial_in_assistant(
        method="ESPRESSO",
        roast_level="light",
        current_grind=2.2,
        shot_or_brew_time_s=18,
        taste_result="too_sour",
        current_ratio=2.0,
    )

    assert advice["method"] == "ESPRESSO"
    assert "suggested_grind" in advice
