from fastapi import FastAPI, Depends, HTTPException, Request, Body, Response, Header
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path 

from .solver_service import SolverService 
from .solution_service import SolutionService
from .models import ProblemSubmission, ProblemResponse, StatusRequest, StatusResponse, SolverStatus, XMLProblemSubmission, SolutionResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger("main")

# Initialize FastAPI app
app = FastAPI(
    title="Unitime Solver API",
    description="API for interacting with the Unitime course timetabling solver",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, modify for production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Custom middleware to handle text content
@app.middleware("http")
async def preserve_text_formatting(request: Request, call_next):
    """Middleware to preserve text formatting in responses"""
    response = await call_next(request)
    return response

# Get cpsolver path from environment variable or use default
def get_cpsolver_path():
    env_path = os.environ.get("SOLVER_PATH")
    if env_path:
        path = Path(env_path)
        logger.info(f"Using cpsolver path from environment: {path}")
        return path
    return None  # Will use default paths in SolverService

# Dependency to get SolverService instance
def get_solver_service():
    cpsolver_path = get_cpsolver_path()
    return SolverService(cpsolver_path=cpsolver_path)

# Dependency to get SolutionService instance
def get_solution_service():
    cpsolver_path = get_cpsolver_path()
    return SolutionService(cpsolver_path=cpsolver_path)

# API endpoints for solver operations
@app.post("/solver/start", tags=["solver"])
async def start_solver(solver_service: SolverService = Depends(get_solver_service)):
    """
    Starts the Unitime solver with the test configuration.
    
    This endpoint executes the Java command to run the Unitime solver with 
    predefined configuration and data files.
    """
    result = solver_service.run_test_solver()
    if result["status"] == "error":
        logger.error(f"Solver start error: {result['message']}")
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@app.get("/solver/status", tags=["solver"])
async def get_solver_status(solver_service: SolverService = Depends(get_solver_service)):
    """
    Gets the current status of the Unitime solver.
    
    Returns information about whether the solver is running, completed, or has not been started.
    """
    return solver_service.get_solver_status()

@app.post("/solver/stop", tags=["solver"])
async def stop_solver(solver_service: SolverService = Depends(get_solver_service)):
    """
    Stops the currently running Unitime solver process.
    
    This will terminate the solver process if it's currently running.
    """
    result = solver_service.stop_solver()
    if result["status"] == "error":
        logger.error(f"Solver stop error: {result['message']}")
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@app.post("/problems", response_model=ProblemResponse, tags=["problems"])
async def submit_problem(
    problem: ProblemSubmission,
    solver_service: SolverService = Depends(get_solver_service)
):
    """
    Submit a new timetabling problem in JSON format.
    
    The problem will be converted to XML and passed to the solver.
    Returns a unique ID that can be used to check the status of the problem.
    """
    # Convert the Pydantic model to a dictionary for processing
    problem_data = problem.dict(exclude={"name"})
    
    # Pass the problem data and optional name to the solver service
    result = solver_service.solve_problem(problem_data, problem.name)
    
    if result["status"] == "error":
        logger.error(f"Problem submission error: {result['message']}")
        raise HTTPException(status_code=500, detail=result["message"])
    
    return ProblemResponse(
        problem_id=result["problem_id"],
        status=SolverStatus(result["status"]),
        message=result["message"]
    )

@app.post("/problems/xml", response_model=ProblemResponse, tags=["problems"])
async def submit_problem_xml(
    request: Request,
    solver_service: SolverService = Depends(get_solver_service)
):
    """
    Submit a new timetabling problem directly in XML format.
    
    The XML is passed directly to the solver without conversion.
    Put the raw XML content directly in the request body with content-type: application/xml.
    Returns a unique ID that can be used to check the status of the problem.
    
    This endpoint is useful when you have already generated a valid UniTime XML format
    and want to bypass the JSON-to-XML conversion process.
    """
    # Read the XML content directly from the request body
    xml_content = await request.body()
    xml_content_str = xml_content.decode('utf-8')
    
    if not xml_content_str:
        logger.error("Empty XML content received")
        raise HTTPException(status_code=400, detail="XML content cannot be empty")
    
    # Extract optional name from query params if provided
    problem_name = request.query_params.get('name')
    
    # Pass the XML content and optional name to the solver service
    result = solver_service.solve_problem_from_xml(xml_content_str, problem_name)
    
    if result["status"] == "error":
        logger.error(f"XML problem submission error: {result['message']}")
        raise HTTPException(status_code=500, detail=result["message"])
    
    return ProblemResponse(
        problem_id=result["problem_id"],
        status=SolverStatus(result["status"]),
        message=result["message"]
    )

@app.get("/problems/{problem_id}", response_model=StatusResponse, tags=["problems"])
async def get_problem(
    problem_id: str,
    solver_service: SolverService = Depends(get_solver_service)
):
    """
    Get a problem's details including its current status.
    
    Returns the current status of the problem solving process, whether a solution is available,
    and the contents of the debug.log file if it exists.
    """
    result = solver_service.get_problem_status(problem_id)
    
    # Only raise HTTP exception if the problem is not found
    if result["status"] == "error" and "not found" in result["message"]:
        logger.error(f"Problem status check error: {result['message']}")
        raise HTTPException(status_code=404, detail=result["message"])
    
    # For other error types, we still want to return the complete response
    # Ensure debug_log preserves formatting if it exists
    debug_log = result.get("debug_log")
    
    return StatusResponse(
        problem_id=result["problem_id"],
        status=SolverStatus(result["status"]),
        message=result["message"],
        solution_available=result["solution_available"],
        debug_log=debug_log
    )

@app.get("/problems/{problem_id}/solution", response_model=SolutionResponse, tags=["problems"])
async def get_problem_solution(
    problem_id: str,
    solution_service: SolutionService = Depends(get_solution_service)
):
    """
    Get the solution for a specific problem in JSON format.
    
    Returns the solution data as a structured JSON object with class assignments,
    room assignments, and time assignments.
    
    If no solution is available, a 404 error is returned.
    """
    json_solution = solution_service.get_solution_json(problem_id)
    if not json_solution:
        raise HTTPException(status_code=404, detail=f"No solution found for problem {problem_id}")
    
    return json_solution

@app.get("/problems/{problem_id}/solution/xml", tags=["problems"])
async def get_problem_solution_xml(
    problem_id: str,
    solution_service: SolutionService = Depends(get_solution_service)
):
    """
    Get the solution for a specific problem in XML format.
    
    Returns the raw XML solution as generated by the solver.
    This endpoint is useful for systems that need the original XML format.
    
    If no solution is available, a 404 error is returned.
    """
    xml_solution = solution_service.get_solution_xml(problem_id)
    if not xml_solution:
        raise HTTPException(status_code=404, detail=f"No solution found for problem {problem_id}")
    
    return Response(
        content=xml_solution,
        media_type="application/xml"
    )

@app.delete("/problems/{problem_id}", tags=["problems"])
async def cancel_problem(
    problem_id: str,
    solver_service: SolverService = Depends(get_solver_service)
):
    """
    Cancel a specific problem solver process.
    
    This will terminate the solver process for the specified problem if it's currently running.
    """
    result = solver_service.stop_problem_solver(problem_id)
    
    if result["status"] == "error":
        logger.error(f"Problem solver cancellation error: {result['message']}")
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result

# Root endpoint for health check
@app.get("/", tags=["health"])
async def read_root():
    """
    Health check endpoint.
    
    Returns a simple message to confirm the API is running.
    """
    return {"status": "ok", "message": "Unitime Solver API is running"}

# Application startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Unitime Solver API")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # Log available environment variables (useful for debugging)
    solver_path = os.environ.get("SOLVER_PATH", "Not set")
    logger.info(f"SOLVER_PATH environment variable: {solver_path}")

# Main execution block
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

