"""BitNet and Phi-2 stage commands must not be handed a JSON sample to copy."""

from app.services.llm.chat_commands import (
    build_command_prompt,
    collapse_repeated_reply,
    match_stage_command,
    parse_plain_stage_reply,
    select_stage_ids,
)


def test_bitnet_and_phi_prompts_have_no_json_sample():
    command = match_stage_command("List the table titles")
    lines = ["table | T1 | Births | review=no | description=yes"]
    bitnet, _ = build_command_prompt(command, lines, model="bitnet-b1.58-2b")
    phi, max_tokens = build_command_prompt(command, lines, model="phi-2")
    for prompt in (bitnet, phi):
        assert "1-2 short sentences" not in prompt
        assert "table_ids" not in prompt
        assert "List the table titles" in prompt
    assert bitnet.rstrip().endswith("Repeat the titles:")
    assert "T1 title is Births" in bitnet
    assert phi.rstrip().endswith("Answer:")
    assert max_tokens == 80


def test_gemma_prompt_still_asks_for_json():
    command = match_stage_command("List the table titles")
    prompt, max_tokens = build_command_prompt(command, ["table | T1 | Births"], model="gemma-2-2b-it")
    assert "reply" in prompt
    assert "1-2 short sentences" not in prompt
    assert max_tokens == 256


def test_repeated_line_keeps_one_copy():
    line = "Yes, description yes."
    collapsed = collapse_repeated_reply("\n".join([line] * 8))
    assert collapsed == line


def test_repeated_schema_echo_collapses():
    chunk = '"1-2 short sentences","action":"none","table_ids":[]}'
    collapsed = collapse_repeated_reply(" ".join([chunk] * 12))
    assert collapsed.count("table_ids") == 1


def test_plain_reply_keeps_the_sentence_and_ids():
    command = match_stage_command("Which tables need review?")
    parsed = parse_plain_stage_reply(
        'Deaths needs review.\nIds: T2',
        command,
    )
    assert parsed["reply"] == "Deaths needs review."
    assert parsed["action"] == "find"
    assert parsed["table_ids"] == ["T2"]


def test_title_list_keeps_titles_the_model_actually_said():
    command = match_stage_command("List the table titles")
    lines = [
        "table | T1 | Births | review=no | description=yes",
        "table | T2 | Deaths | review=yes | description=no",
        "table | T3 | Infant | review=no | description=yes",
    ]
    parsed = parse_plain_stage_reply(
        '"Births" "Deaths" "Infant" "Repeat" "List" "Table" "Table"',
        command,
        lines,
    )
    assert parsed["reply"] == "Births, Deaths, Infant"
    assert parsed["table_ids"] == []


def test_phi_number_run_is_not_a_table_list():
    command = match_stage_command("Which tables have no title?")
    lines = [
        "table | 12-0 | Births | review=no | description=yes",
        "table | 12-1 | Untitled | review=no | description=no",
    ]
    raw = "Ids: " + ", ".join(str(n) for n in range(2, 40))
    parsed = select_stage_ids(parse_plain_stage_reply(raw, command, lines), command, lines)
    assert parsed["action"] == "none"
    assert parsed["table_ids"] == []
    assert "2, 3, 4" not in parsed["reply"]
    assert "None of those ids" in parsed["reply"]


def test_no_title_keeps_only_untitled_ids_the_model_named():
    command = match_stage_command("Which tables have no title?")
    lines = [
        "table | T1 | Births | review=no | description=yes",
        "table | T2 | Untitled | review=no | description=no",
        "table | T3 | Deaths | review=yes | description=yes",
    ]
    parsed = select_stage_ids(
        parse_plain_stage_reply("Ids: T1, T2, T3", command, lines),
        command,
        lines,
    )
    assert parsed["action"] == "find"
    assert parsed["table_ids"] == ["T2"]
    assert parsed["reply"] == "1 table has no title."


def test_no_untitled_lines_answers_none():
    command = match_stage_command("Which tables have no title?")
    lines = ["table | T1 | Births | review=no | description=yes"]
    parsed = select_stage_ids(
        parse_plain_stage_reply("Ids: 2, 3, 4", command, lines),
        command,
        lines,
    )
    assert parsed["action"] == "none"
    assert parsed["table_ids"] == []
    assert parsed["reply"] == "No tables are missing a title."


def test_title_list_drops_a_copied_command_and_output_label():
    command = match_stage_command("List the table titles")
    parsed = parse_plain_stage_reply(
        'Output: List the table titles Births, Deaths, Infant',
        command,
    )
    assert parsed["action"] == "none"
    assert parsed["table_ids"] == []
    assert "Births" in parsed["reply"]
    assert "1-2 short sentences" not in parsed["reply"]
