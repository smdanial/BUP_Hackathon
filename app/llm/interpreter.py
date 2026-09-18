import os
import json
from typing import Any
from google import genai
from google.genai import types


def interpret_notes(operator_notes: list[str]) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_no_ops(len(operator_notes))

    try:
        client = genai.Client(api_key=api_key)
    except Exception:
        return _fallback_no_ops(len(operator_notes))

    directive_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "note_index": types.Schema(type=types.Type.INTEGER),
            "applies": types.Schema(type=types.Type.BOOLEAN),
            "directive_type": types.Schema(
                type=types.Type.STRING,
                enum=[
                    "solar_reduction",
                    "minimum_battery_reserve",
                    "no_charge_window",
                    "no_discharge_window",
                    "max_grid_window",
                    "no_op",
                ],
            ),
            "structured_adjustment": types.Schema(
                type=types.Type.OBJECT,
                nullable=True,
                properties={
                    "hours": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.INTEGER),
                    ),
                    "factor": types.Schema(type=types.Type.NUMBER),
                    "minimum_energy_kwh": types.Schema(type=types.Type.NUMBER),
                    "max_grid_kwh": types.Schema(type=types.Type.NUMBER),
                },
            ),
            "explanation": types.Schema(type=types.Type.STRING),
        },
        required=["note_index", "applies", "directive_type", "structured_adjustment", "explanation"],
    )

    schema = types.Schema(
        type=types.Type.ARRAY,
        items=directive_schema,
    )

    system_instruction = (
        "You are a grid operations parser. Convert each operator note into a structured directive.\n"
        "Do not invent data, perform math, or hallucinate battery/tariff specs.\n"
        "Return exactly one JSON object per note in the same order.\n\n"
        "Directive types and structured_adjustment shapes:\n"
        "- solar_reduction: {\"hours\": [int], \"factor\": float}  // factor between 0.0 and 1.0\n"
        "- minimum_battery_reserve: {\"hours\": [int], \"minimum_energy_kwh\": float}  // kWh >= 0\n"
        "- no_charge_window: {\"hours\": [int]}  // no extra keys\n"
        "- no_discharge_window: {\"hours\": [int]}  // no extra keys\n"
        "- max_grid_window: {\"hours\": [int], \"max_grid_kwh\": float}  // kWh >= 0\n"
        "- no_op: null structured_adjustment\n\n"
        "Time windows (\"hours\") must be whole-hour integers 0-23. "
        "E.g., \"1 PM to 3 PM\" -> [13, 14]. Use inclusive ranges.\n"
        "If a note is irrelevant or unactionable, return no_op with applies=false."
    )

    user_prompt = "Operator notes:\n" + "\n".join(f"{i}: {note}" for i, note in enumerate(operator_notes))

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=user_prompt)])],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
            ),
        )

        text = response.text or "[]"
        parsed = json.loads(text)

        if not isinstance(parsed, list):
            return _fallback_no_ops(len(operator_notes))

        result = []
        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                result.append(_make_no_op(i))
                continue
            item["note_index"] = i
            if item.get("directive_type") == "no_op":
                item["applies"] = False
                item["structured_adjustment"] = None
            result.append(item)

        while len(result) < len(operator_notes):
            result.append(_make_no_op(len(result)))

        return result[: len(operator_notes)]

    except Exception:
        return _fallback_no_ops(len(operator_notes))


def _make_no_op(i: int) -> dict:
    return {
        "note_index": i,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "Failed to parse or API error",
    }


def _fallback_no_ops(n: int) -> list[dict]:
    return [_make_no_op(i) for i in range(n)]