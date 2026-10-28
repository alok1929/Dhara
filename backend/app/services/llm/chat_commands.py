"""Fixed chat commands for small on-prem models.

Each command is sent in full. Only whole fact lines are dropped when the
list would overflow Gemma 2B's context. The command text is never sliced.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from app.services.extraction.pdf.llm_json import loads_llm_json
from app.services.llm.profiles import (
    BITNET_B158_2B_MODEL,
    SMALL_CPU_CONTEXT,
    gemma_2b_json_response_format,
    uses_plain_stage_reply,
)

logger = logging.getLogger(__name__)

# Short replies. Reserving this many tokens keeps the command inside 8192.
COMMAND_MAX_TOKENS = 256
# BitNet and Phi-2 loop if this is large. One sentence fits in 80 tokens.
PLAIN_MAX_TOKENS = 80
_MARGIN = 64
_SCHEMA_ECHO = "1-2 short sentences"


@dataclass(frozen=True)
class StageCommand:
    label: str
    instruction: str


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().rstrip("?.!").split())


COMMANDS: tuple[StageCommand, ...] = (
    StageCommand(
        "How many tables?",
        "Count the table lines. Reply with one sentence that states the count. action is none and table_ids is empty.",
    ),
    StageCommand(
        "List the table titles",
        "Name the titles you can see, in one short list. If lines were omitted, say how many were omitted. action is none and table_ids is empty.",
    ),
    StageCommand(
        "Which tables need review?",
        "Select every table line with review=yes. action is find and table_ids lists those ids. If none, action is none and say so.",
    ),
    StageCommand(
        "Which tables have no title?",
        "Select every table line whose title is empty or Untitled. action is find and table_ids lists those ids. If none, action is none and say so.",
    ),
    StageCommand(
        "How many groups?",
        "Count the group lines. Reply with one sentence that states the count. action is none and table_ids is empty.",
    ),
    StageCommand(
        "List the group names",
        "Name each group in one short list. action is none and table_ids is empty.",
    ),
    StageCommand(
        "Which groups have one table?",
        "Say which group lines have tables=1. action is none and table_ids is empty.",
    ),
    StageCommand(
        "Which tables are not grouped?",
        "Select every ungrouped table line. action is find and table_ids lists those ids. If none, action is none and say so.",
    ),
    StageCommand(
        "Which tables are missing a description?",
        "Select every table line with description=no. action is find and table_ids lists those ids. If none, action is none and say so.",
    ),
    StageCommand(
        "How many tables have a description?",
        "Count table lines with description=yes. One sentence. action is none and table_ids is empty.",
    ),
    StageCommand(
        "How many tables are in this release?",
        "Read the release line and answer with that table count in one sentence. action is none and table_ids is empty.",
    ),
    StageCommand(
        "Is classification complete?",
        "Read classification_complete and answer yes or no in one sentence. action is none and table_ids is empty.",
    ),
    StageCommand(
        "What should I check before harmonising?",
        "Using only the lines, say in one sentence whether classification is complete and how many groups there are. action is none and table_ids is empty.",
    ),
    StageCommand(
        "How many tables will be published?",
        "Read the release line and answer with that table count in one sentence. action is none and table_ids is empty.",
    ),
    StageCommand(
        "What is still required before publish?",
        "Using only the lines, say in one sentence what is still open. action is none and table_ids is empty.",
    ),
    StageCommand(
        "What should I upload?",
        "There is no table list yet. One sentence: upload a CSV, Excel, or PDF to extract tables. action is none and table_ids is empty.",
    ),
    StageCommand(
        "What happens after upload?",
        "One sentence: extraction runs, then you review tables in Preview. action is none and table_ids is empty.",
    ),
)

_BY_NORM = {_norm(cmd.label): cmd for cmd in COMMANDS}


def match_stage_command(text: str) -> StageCommand | None:
    return _BY_NORM.get(_norm(text))


def _title_of(table: Dict[str, Any]) -> str:
    title = str(
        table.get("title")
        or table.get("name")
        or table.get("banner_table_id")
        or ""
    ).strip()
    return title or "Untitled"


def _review_yes(table: Dict[str, Any]) -> bool:
    if table.get("human_review_needed"):
        return True
    status = str(table.get("review_status") or table.get("status") or "").strip().lower()
    return status in {"needs_review", "uncertain", "uncertain_title", "fix"}


def _has_description(table: Dict[str, Any]) -> bool:
    text = str(
        table.get("short_description")
        or table.get("description")
        or table.get("summary")
        or ""
    ).strip()
    return bool(text)


def lines_from_tables(
    tables: Sequence[Dict[str, Any]] | None,
    groups: Sequence[Dict[str, Any]] | None = None,
) -> List[str]:
    """One fact per line. Ids stay intact so the model can copy them."""
    lines: List[str] = []
    grouped_ids: set[str] = set()
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        number = group.get("group_number") or ""
        name = str(group.get("name") or group.get("file_name") or "Group").strip() or "Group"
        ids = [str(tid).strip() for tid in (group.get("table_ids") or []) if str(tid).strip()]
        count = group.get("table_count")
        if count is None:
            count = len(ids)
        grouped_ids.update(ids)
        lines.append(f"group {number} | {name} | tables={count}")
    for table in tables or []:
        if not isinstance(table, dict):
            continue
        tid = str(table.get("table_id") or table.get("_uid") or table.get("id") or "").strip()
        if not tid:
            continue
        if tid in grouped_ids:
            continue
        kind = "ungrouped" if groups else "table"
        lines.append(
            f"{kind} | {tid} | {_title_of(table)}"
            f" | review={'yes' if _review_yes(table) else 'no'}"
            f" | description={'yes' if _has_description(table) else 'no'}"
        )
    return lines


def _task_sentence(command: StageCommand) -> str:
    """Drop the JSON action clause. The command label stays in the prompt."""
    task = command.instruction.split("action is", 1)[0].strip().rstrip(".")
    return task or command.instruction


def _titles_from_line(line: str) -> str | None:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 3 or not parts[0].lower().startswith("table"):
        return None
    title = parts[2]
    if not title or title.lower() == "untitled":
        return None
    return title


def _spoken_line(line: str) -> str:
    """BitNet extends a pipe row. A sentence does not invite that."""
    parts = [part.strip() for part in line.split("|")]
    if len(parts) >= 3 and parts[0].lower().startswith("table"):
        sentence = f"{parts[1]} title is {parts[2]}"
        extras = []
        for extra in parts[3:]:
            if "=" in extra:
                key, value = extra.split("=", 1)
                extras.append(f"{key.strip()} {value.strip()}")
        if extras:
            sentence = f"{sentence}, " + ", ".join(extras)
        return sentence + "."
    return line


def _plain_prompt(command: StageCommand, lines: Sequence[str], *, model: str) -> tuple[str, int]:
    """One-sentence prompt. No JSON sample, so the model cannot copy it."""
    task = _task_sentence(command)
    body = [str(line).strip() for line in lines if str(line).strip()]
    bitnet = (model or "").strip() == BITNET_B158_2B_MODEL
    if bitnet:
        body = [_spoken_line(line) for line in body]
        if command.label == "List the table titles":
            head = f"Command: {command.label}\n"
            tail = "\nRepeat the titles:"
        else:
            extra = ""
            if "action is find" in command.instruction:
                extra = " Name the matching titles."
            head = f"Command: {command.label}\n{task}.{extra}\n"
            tail = "\nAnswer:"
    else:
        extra = ""
        if "action is find" in command.instruction:
            extra = (
                "\nOn the next line write Ids: and only ids copied from lines that match."
                " Do not count. If none match, write Ids: none."
            )
        head = f"Command: {command.label}\n{task}.{extra}\n\nLines:\n"
        tail = "\n\nAnswer:"
    context = SMALL_CPU_CONTEXT.get((model or "").strip()) or 2048
    budget = context - PLAIN_MAX_TOKENS - _MARGIN
    kept: List[str] = []
    omitted = 0
    for line in body:
        candidate = head + "\n".join(kept + [line]) + tail
        if len(candidate) > budget and kept:
            omitted = len(body) - len(kept)
            break
        if len(head + line + tail) > budget and not kept:
            omitted = len(body)
            break
        kept.append(line)
    else:
        omitted = 0
    if omitted:
        note = f"omitted: {omitted} more lines"
        while kept and len(head + "\n".join(kept + [note]) + tail) > budget:
            kept.pop()
            omitted += 1
            note = f"omitted: {omitted} more lines"
        if len(head + note + tail) <= budget:
            kept.append(note)
    text = head + ("\n".join(kept) if kept else "(none)") + tail
    if command.label not in text:
        text = f"Command: {command.label}\n{task}.\nAnswer:"
    return text, PLAIN_MAX_TOKENS


def collapse_repeated_reply(text: str) -> str:
    """Keep one copy when the model prints the same phrase over and over."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) >= 3:
        counts: Dict[str, int] = {}
        for line in lines:
            counts[line] = counts.get(line, 0) + 1
        top = max(counts, key=counts.get)
        if counts[top] >= 3 and counts[top] >= len(lines) // 2:
            return top
    raw = " ".join((text or "").split())
    if len(raw) < 48:
        return (text or "").strip()
    for size in range(24, len(raw) // 3 + 1):
        piece = raw[:size].rstrip()
        if len(piece) < 24:
            continue
        copies = 0
        rest = raw
        while rest.startswith(piece):
            copies += 1
            rest = rest[len(piece):].lstrip(" ")
        if copies >= 3 and len(rest) < len(piece):
            return piece.strip(" ,\"{}")
    return (text or "").strip()


def _mentioned_titles(reply: str, lines: Sequence[str]) -> List[str]:
    found: List[str] = []
    haystack = reply.lower()
    for line in lines:
        title = _titles_from_line(str(line))
        if title and title.lower() in haystack and title not in found:
            found.append(title)
    return found


def parse_plain_stage_reply(
    raw: str,
    command: StageCommand,
    lines: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Turn a one-sentence reply into the stage-command shape."""
    text = collapse_repeated_reply(raw)
    text = re.sub(r"(?i)\boutput\s*:\s*", "", text)
    text = text.replace(_SCHEMA_ECHO, " ")
    text = re.sub(r'"?action"?\s*:\s*"?(none|find)"?', " ", text, flags=re.I)
    text = re.sub(r'"?table_ids"?\s*:\s*\[[^\]]*\]\}?', " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,\"{}")
    wants_ids = "action is find" in command.instruction
    ids: List[str] = []
    reply_parts: List[str] = []
    for piece in re.split(r"\s+(?=Ids:)", text, flags=re.I):
        if piece.lower().startswith("ids:"):
            body = piece.split(":", 1)[1].strip()
            if body.lower() in {"", "none", "n/a"}:
                continue
            seen: set[str] = set()
            for part in re.split(r"[, ]+", body):
                sid = part.strip()
                if sid and sid.lower() != "none" and sid not in seen:
                    seen.add(sid)
                    ids.append(sid)
        elif piece.strip():
            reply_parts.append(piece.strip())
    reply = " ".join(reply_parts).strip(" :")
    if reply.lower().startswith(command.label.lower()):
        reply = reply[len(command.label):].strip(" :\"")
    mentioned = _mentioned_titles(reply, lines or [])
    if command.label == "List the table titles" and mentioned:
        reply = ", ".join(mentioned)
    if not reply and ids:
        reply = "Ids: " + ", ".join(ids)
    if not reply:
        reply = "No answer."
    action = "find" if wants_ids and ids else "none"
    if not wants_ids:
        ids = []
    return {"reply": reply, "action": action, "table_ids": ids}


_BLANK_TITLES = {"", "untitled", "—", "–", "-", "none", "n/a", "null"}


def _fact_table(line: str) -> tuple[str, str, str, Dict[str, str]] | None:
    """Parse ``table | id | title | review=yes`` into kind, id, title, flags."""
    parts = [part.strip() for part in str(line).split("|")]
    if len(parts) < 3:
        return None
    kind = parts[0].lower()
    if kind not in {"table", "ungrouped"}:
        return None
    flags: Dict[str, str] = {}
    for extra in parts[3:]:
        if "=" not in extra:
            continue
        key, value = extra.split("=", 1)
        flags[key.strip().lower()] = value.strip().lower()
    return kind, parts[1], parts[2], flags


def _blank_title(title: str) -> bool:
    return title.strip().lower() in _BLANK_TITLES


def _line_matches_find(command: StageCommand, kind: str, title: str, flags: Dict[str, str]) -> bool:
    if command.label == "Which tables need review?":
        return flags.get("review") == "yes"
    if command.label == "Which tables have no title?":
        return _blank_title(title)
    if command.label == "Which tables are not grouped?":
        return kind == "ungrouped"
    if command.label == "Which tables are missing a description?":
        return flags.get("description") == "no"
    return True


def _reply_is_id_list(reply: str) -> bool:
    text = (reply or "").strip()
    if not text.lower().startswith("ids:"):
        return False
    body = text.split(":", 1)[1]
    parts = [part for part in re.split(r"[, ]+", body) if part]
    return bool(parts)


def _found_sentence(command: StageCommand, count: int) -> str:
    noun = "table" if count == 1 else "tables"
    verb = {
        "Which tables have no title?": "has no title" if count == 1 else "have no title",
        "Which tables need review?": "needs review" if count == 1 else "need review",
        "Which tables are not grouped?": "is not grouped" if count == 1 else "are not grouped",
        "Which tables are missing a description?": (
            "is missing a description" if count == 1 else "are missing a description"
        ),
    }.get(command.label, "matches" if count == 1 else "match")
    return f"{count} {noun} {verb}."


def _none_sentence(command: StageCommand, *, named_real_ids: bool) -> str:
    if named_real_ids:
        return {
            "Which tables have no title?": "None of those ids are tables with no title.",
            "Which tables need review?": "None of those ids need review.",
            "Which tables are not grouped?": "None of those ids are ungrouped tables.",
            "Which tables are missing a description?": "None of those ids are missing a description.",
        }.get(command.label, "None of those ids match.")
    return {
        "Which tables have no title?": "No tables are missing a title.",
        "Which tables need review?": "No tables need review.",
        "Which tables are not grouped?": "No tables are ungrouped.",
        "Which tables are missing a description?": "No tables are missing a description.",
    }.get(command.label, "No matching tables.")


def select_stage_ids(
    parsed: Dict[str, Any],
    command: StageCommand,
    lines: Sequence[str] | None,
) -> Dict[str, Any]:
    """Keep ids the model named only when that line answers the command."""
    reply = str(parsed.get("reply") or "").strip() or "No answer."
    wants_ids = "action is find" in command.instruction
    if not wants_ids:
        return {"reply": reply, "action": "none", "table_ids": []}

    allowed: Dict[str, tuple[str, str, str, Dict[str, str]]] = {}
    for line in lines or []:
        fact = _fact_table(str(line))
        if fact is None or not fact[1]:
            continue
        if _line_matches_find(command, fact[0], fact[2], fact[3]):
            allowed[fact[1]] = fact

    kept: List[str] = []
    seen: set[str] = set()
    emitted = [str(tid or "").strip() for tid in (parsed.get("table_ids") or []) if str(tid or "").strip()]
    for sid in emitted:
        if sid in allowed and sid not in seen:
            seen.add(sid)
            kept.append(sid)

    if kept:
        if _reply_is_id_list(reply) or reply == "No answer.":
            reply = _found_sentence(command, len(kept))
        return {"reply": reply, "action": "find", "table_ids": kept}
    if _reply_is_id_list(reply) or reply == "No answer.":
        if not allowed:
            reply = _none_sentence(command, named_real_ids=False)
        elif emitted:
            reply = _none_sentence(command, named_real_ids=True)
        else:
            reply = "No ids were copied from the lines."
    return {"reply": reply, "action": "none", "table_ids": []}


def build_command_prompt(command: StageCommand, lines: Sequence[str], *, model: str) -> tuple[str, int]:
    """Return the full prompt and max_tokens. The command string is always kept."""
    if uses_plain_stage_reply(model):
        return _plain_prompt(command, lines, model=model)
    head = (
        "You are Dhara. Answer using only the lines below. Never invent an id.\n\n"
        f"Command: {command.label}\n"
        f"{command.instruction}\n\n"
        "Lines:\n"
    )
    tail = (
        "\n\nReturn only JSON with keys reply, action, and table_ids.\n"
        "reply is one sentence. action is none or find. table_ids is a list of ids."
    )
    body = [str(line).strip() for line in lines if str(line).strip()]
    context = SMALL_CPU_CONTEXT.get((model or "").strip())
    if context is not None:
        budget = context - COMMAND_MAX_TOKENS - _MARGIN
        kept: List[str] = []
        omitted = 0
        for line in body:
            candidate = head + "\n".join(kept + [line]) + tail
            if len(candidate) > budget and kept:
                omitted = len(body) - len(kept)
                break
            if len(head + line + tail) > budget and not kept:
                omitted = len(body)
                break
            kept.append(line)
        else:
            omitted = 0
        if omitted:
            note = f"omitted: {omitted} more lines"
            while kept and len(head + "\n".join(kept + [note]) + tail) > budget:
                kept.pop()
                omitted += 1
                note = f"omitted: {omitted} more lines"
            if len(head + note + tail) <= budget:
                kept.append(note)
        text = head + ("\n".join(kept) if kept else "(none)") + tail
        if command.label not in text:
            text = f"Command: {command.label}\n{command.instruction}\n" + tail
        return text, COMMAND_MAX_TOKENS
    text = head + ("\n".join(body) if body else "(none)") + tail
    return text, COMMAND_MAX_TOKENS


def run_stage_command(
    *,
    command: str,
    lines: Sequence[str] | None,
    api_key: str,
) -> Dict[str, Any]:
    """Ask the configured model to answer one fixed command."""
    spec = match_stage_command(command)
    if spec is None:
        raise ValueError("Unknown command")
    from app.services.llm.factory import live_openai_chat

    llm = live_openai_chat(api_key)
    if llm is None:
        raise ValueError("An LLM API key is required in Settings")

    prompt, max_tokens = build_command_prompt(spec, list(lines or []), model=llm.model)
    plain = uses_plain_stage_reply(llm.model)
    client = llm.openai_sdk()
    create_kwargs: Dict[str, Any] = {
        "model": llm.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if plain:
        create_kwargs["stop"] = ["\n\n", "\nCommand:", "\nLines:", "\nInstruct:"]
    response_format = gemma_2b_json_response_format(llm.model)
    if response_format is not None and not plain:
        create_kwargs["response_format"] = response_format
    resp = client.chat.completions.create(**create_kwargs)
    raw = llm.completion_text(resp.choices[0].message).strip()
    if plain:
        parsed = parse_plain_stage_reply(raw, spec, lines=lines or [])
    else:
        try:
            data = llm.loads_json(raw, context="stage_command")
        except json.JSONDecodeError:
            data = loads_llm_json(raw) or {}
        if not isinstance(data, dict) or not data:
            logger.warning("stage_command: non-JSON reply profile=%s: %s", llm.profile_tag(), raw[:300])
            parsed = {"reply": raw or "No answer.", "action": "none", "table_ids": []}
        else:
            reply = str(data.get("reply") or "").strip() or raw
            action = str(data.get("action") or "none").strip().lower()
            if action != "find":
                action = "none"
            ids_raw = data.get("table_ids") if action == "find" else []
            table_ids: List[str] = []
            if isinstance(ids_raw, list):
                seen: set[str] = set()
                for tid in ids_raw:
                    sid = str(tid or "").strip()
                    if sid and sid not in seen:
                        seen.add(sid)
                        table_ids.append(sid)
            parsed = {"reply": reply, "action": action, "table_ids": table_ids}
    return select_stage_ids(parsed, spec, lines or [])
