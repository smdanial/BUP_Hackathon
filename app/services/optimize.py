from app.llm.interpreter import interpret_notes
from app.validation.directives import validate_directives
from app.optimizer.solver import build_schedule
from app.models.schemas import OptimizeRequest, OptimizeResponse

def process_optimization(payload: OptimizeRequest) -> dict:
    # 1. LLM Interpreter
    raw_directives = interpret_notes(payload.operator_notes)
    
    # 2. Guardrail Validator
    validated_directives = validate_directives(raw_directives, len(payload.operator_notes))
    
    # 3. Math Optimizer
    hours_dict = [h.model_dump() for h in payload.hours]
    battery_dict = payload.battery.model_dump()
    schedule_result = build_schedule(hours_dict, battery_dict, validated_directives)
    
    # 4. Construct Final Response
    return {
        "scenario_id": payload.scenario_id,
        "directive_interpretation": validated_directives,
        "hourly_plan": schedule_result["hourly_plan"],
        "total_grid_kwh": schedule_result["total_grid_kwh"],
        "total_cost_bdt": schedule_result["total_cost_bdt"],
        "peak_grid_kwh": schedule_result["peak_grid_kwh"],
        "plan_summary": schedule_result["plan_summary"]
    }