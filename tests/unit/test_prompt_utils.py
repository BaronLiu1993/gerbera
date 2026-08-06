from gerbera_harness.prompts import PromptTypeEnum, load_prompt


def test_load_prompt_reads_main_prompt() -> None:
    prompt = load_prompt(PromptTypeEnum.MAIN, "INITIALISATION.md")

    assert prompt.startswith("# Initialisation")


def test_load_prompt_reads_sub_prompt() -> None:
    prompt = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")

    assert prompt.startswith("# Planning")


def test_initialisation_prompt_requires_continuous_time_series() -> None:
    prompt = load_prompt(PromptTypeEnum.MAIN, "INITIALISATION.md")

    assert "You MUST use `continuous`" in prompt
    assert "repeated timestamped readings" in prompt
    assert "IR sensor output remains stable over 30 seconds" in prompt
    assert "Do not represent a time-series experiment" in prompt


def test_initialisation_prompt_requires_parameter_lists() -> None:
    prompt = load_prompt(PromptTypeEnum.MAIN, "INITIALISATION.md")

    assert "Parameter-list fields are mandatory" in prompt
    assert "Every `discrete` action must include `params`" in prompt
    assert "both `forward_tool_call_params` and" in prompt
    assert "`reverse_tool_call_params`" in prompt
    assert "Never omit a parameter-list field" in prompt
