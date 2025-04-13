from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path 

from .solver_service import SolverService 

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
