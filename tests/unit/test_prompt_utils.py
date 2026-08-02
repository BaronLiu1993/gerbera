from gerbera_harness.prompts import PromptTypeEnum, load_prompt


def test_load_prompt_reads_main_prompt() -> None:
    prompt = load_prompt(PromptTypeEnum.MAIN, "INITIALISATION.md")

    assert prompt.startswith("# Initialisation")


def test_load_prompt_reads_sub_prompt() -> None:
    prompt = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")

    assert prompt.startswith("# Planning")
