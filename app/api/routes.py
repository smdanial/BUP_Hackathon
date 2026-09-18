import traceback
from fastapi import APIRouter, HTTPException
from app.models.schemas import OptimizeRequest, OptimizeResponse
from app.services.optimize import process_optimization

router = APIRouter()

@router.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy_endpoint(request: OptimizeRequest):
    try:
        # 24-hour validation check
        if len(request.hours) != 24:
            raise HTTPException(status_code=400, detail="Exactly 24 hours of data required.")
            
        result = process_optimization(request)
        return result
    except Exception as e:
        # Print traceback for local debugging
        traceback.print_exc()
        # Never leak stack traces to the judge platform, return 500 controlled error
        raise HTTPException(status_code=500, detail="Internal Optimization Error")