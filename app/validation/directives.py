from typing import Any


def validate_directives(raw_directives: list[dict], num_notes: int) -> list[dict]:
    allowed_types = {
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
        "no_op",
    }

    def make_no_op(i: int) -> dict:
        return {
            "note_index": i,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "Invalid constraint forced to no_op",
        }

    def validate_hours(hours: Any) -> list[int] | None:
        if not isinstance(hours, list):
            return None
        try:
            hour_ints = [int(h) for h in hours]
        except (ValueError, TypeError):
            return None
        if len(hour_ints) != len(set(hour_ints)):
            return None
        if any(h < 0 or h > 23 for h in hour_ints):
            return None
        return sorted(hour_ints)

    def validate_directive(d: dict, i: int) -> dict:
        if not isinstance(d, dict):
            return make_no_op(i)

        note_index = d.get("note_index")
        if not isinstance(note_index, int) or note_index != i:
            return make_no_op(i)

        directive_type = d.get("directive_type")
        if directive_type not in allowed_types:
            return make_no_op(i)

        applies = d.get("applies")
        if not isinstance(applies, bool):
            return make_no_op(i)

        if directive_type == "no_op":
            if applies is not False:
                return make_no_op(i)
            return {
                "note_index": i,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": d.get("explanation", "Invalid constraint forced to no_op"),
            }

        if applies is not True:
            return make_no_op(i)

        structured_adjustment = d.get("structured_adjustment")
        if not isinstance(structured_adjustment, dict):
            return make_no_op(i)

        hours = validate_hours(structured_adjustment.get("hours"))
        if hours is None:
            return make_no_op(i)

        if directive_type == "solar_reduction":
            factor = structured_adjustment.get("factor")
            if not isinstance(factor, (int, float)) or factor < 0.0 or factor > 1.0:
                return make_no_op(i)
            return {
                "note_index": i,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": hours, "factor": float(factor)},
                "explanation": d.get("explanation", ""),
            }

        if directive_type == "minimum_battery_reserve":
            min_energy = structured_adjustment.get("minimum_energy_kwh")
            if not isinstance(min_energy, (int, float)) or min_energy < 0:
                return make_no_op(i)
            return {
                "note_index": i,
                "applies": True,
                "directive_type": "minimum_battery_reserve",
                "structured_adjustment": {"hours": hours, "minimum_energy_kwh": float(min_energy)},
                "explanation": d.get("explanation", ""),
            }

        if directive_type == "max_grid_window":
            max_grid = structured_adjustment.get("max_grid_kwh")
            if not isinstance(max_grid, (int, float)) or max_grid < 0:
                return make_no_op(i)
            return {
                "note_index": i,
                "applies": True,
                "directive_type": "max_grid_window",
                "structured_adjustment": {"hours": hours, "max_grid_kwh": float(max_grid)},
                "explanation": d.get("explanation", ""),
            }

        if directive_type in ("no_charge_window", "no_discharge_window"):
            extra_keys = set(structured_adjustment.keys()) - {"hours"}
            if extra_keys:
                return make_no_op(i)
            return {
                "note_index": i,
                "applies": True,
                "directive_type": directive_type,
                "structured_adjustment": {"hours": hours},
                "explanation": d.get("explanation", ""),
            }

        return make_no_op(i)

    if not isinstance(raw_directives, list):
        raw_directives = []

    validated = []
    for i in range(num_notes):
        if i < len(raw_directives):
            validated.append(validate_directive(raw_directives[i], i))
        else:
            validated.append(make_no_op(i))

    return validated[:num_notes]