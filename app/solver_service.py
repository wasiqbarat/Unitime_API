import os
import subprocess
import threading
import logging
import sys
from typing import Dict, Optional
from pathlib import Path

# Get the current working directory
CURRENT_DIR = Path(os.getcwd())

# Define constants for solver paths and configuration - more flexible approach
# Try different potential locations for the cpsolver directory
POTENTIAL_CPSOLVER_PATHS = [
    Path("cpsolver"),              # In the current directory
    Path("../cpsolver"),           # One level up
    Path("./cpsolver"),            # Explicitly in current directory
    CURRENT_DIR / "cpsolver",      # Using absolute path
    Path("/app/cpsolver"),         # Docker container path
]

# Find the first path that exists
CPSOLVER_PATH = None
for path in POTENTIAL_CPSOLVER_PATHS:
    if path.exists():
        CPSOLVER_PATH = path
        break

# If no path exists, default to the first one
if CPSOLVER_PATH is None:
    CPSOLVER_PATH = POTENTIAL_CPSOLVER_PATHS[0]
    logging.warning(f"No cpsolver directory found. Defaulting to {CPSOLVER_PATH}")

class SolverService:
    """Service for running the Unitime solver operations."""
    
    def __init__(self, cpsolver_path: Path = None):
        """Initialize the solver service with the path to the cpsolver directory."""
        # Allow cpsolver path to be passed in or use the default
        self.cpsolver_path = cpsolver_path or CPSOLVER_PATH
        self.logger = logging.getLogger("solver_service")
        self._process = None
        self._solve_thread = None
        self._is_solving = False
        
        # Log information about paths for debugging
        self.logger.info(f"Current working directory: {os.getcwd()}")
        self.logger.info(f"Using cpsolver path: {self.cpsolver_path}")
        self.logger.info(f"Path exists: {self.cpsolver_path.exists()}")
    
    def run_test_solver(self) -> Dict:
        """
        Runs the test solver command and returns the result.
        
        The command runs:
        java -Xmx512m -cp "cpsolver-1.4.74.jar;lib/log4j-api-2.20.0.jar;lib/log4j-core-2.20.0.jar;lib/dom4j-2.1.4.jar" 
        org.cpsolver.coursett.Test config.cfg input/problem.xml solved_output/
        
        Returns:
            Dict containing status of the solver run and any output
        """
        try:
            # Check if the cpsolver directory exists
            if not self.cpsolver_path.exists():
                error_message = f"Cpsolver directory not found at: {self.cpsolver_path}"
                self.logger.error(error_message)
                return {
                    "status": "error",
                    "message": error_message
                }
            
            # Store the original directory to go back to
            original_dir = os.getcwd()
            
            # Change to cpsolver directory for the command to work properly
            os.chdir(self.cpsolver_path)
            
            # Adjust the classpath separator based on the operating system
            # Windows uses semicolons, Unix-like systems use colons
            separator = ";" if sys.platform.startswith("win") else ":"
            classpath = separator.join([
                "cpsolver-1.4.74.jar",
                "lib/log4j-api-2.20.0.jar",
                "lib/log4j-core-2.20.0.jar",
                "lib/dom4j-2.1.4.jar"
            ])
            
            # Construct the command
            command = [
                "java", "-Xmx512m", 
                "-cp", classpath,
                "org.cpsolver.coursett.Test", 
                "config.cfg", "input/problem.xml", "solved_output/"
            ]
            
            # Log the command for debugging
            self.logger.info(f"Running command: {' '.join(command)}")
            
            # Run the command and capture output
            self._is_solving = True
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Create a function to monitor the process
            def monitor_process():
                try:
                    stdout, stderr = self._process.communicate()
                    exit_code = self._process.returncode
                    self._is_solving = False
                    
                    # Log the outcome
                    self.logger.info(f"Solver process completed with exit code: {exit_code}")
                    if stderr:
                        self.logger.error(f"Solver error output: {stderr}")
                    if stdout:
                        self.logger.info(f"Solver output: {stdout[:500]}...") # Log first 500 chars
                    
                    # Return to the original directory
                    os.chdir(original_dir)
                    
                    return stdout, stderr, exit_code
                except Exception as e:
                    self.logger.error(f"Error in monitor thread: {e}")
                    self._is_solving = False
                    # Return to the original directory
                    os.chdir(original_dir)
            
            # Start the monitoring in a separate thread
            self._solve_thread = threading.Thread(target=monitor_process)
            self._solve_thread.start()
            
            return {
                "status": "started",
                "message": "Solver process started successfully",
                "cpsolver_path": str(self.cpsolver_path)
            }
        
        except Exception as e:
            self._is_solving = False
            error_message = str(e)
            self.logger.error(f"Error running solver: {error_message}")
            
            # Try to change back to the original directory if we changed it
            try:
                if 'original_dir' in locals():
                    os.chdir(original_dir)
            except:
                pass
                
            return {
                "status": "error",
                "message": f"Failed to start solver: {error_message}"
            }
    
    def get_solver_status(self) -> Dict:
        """
        Get the current status of the solver.
        
        Returns:
            Dict containing the status information
        """
        if self._is_solving:
            return {
                "status": "running",
                "message": "Solver is currently running"
            }
        elif self._process is None:
            return {
                "status": "not_started",
                "message": "Solver has not been started"
            }
        else:
            return {
                "status": "completed",
                "message": f"Solver completed with exit code: {self._process.returncode}"
            }
    
    def stop_solver(self) -> Dict:
        """
        Stop the currently running solver process.
        
        Returns:
            Dict containing the result of the stop operation
        """
        if not self._is_solving or self._process is None:
            return {
                "status": "not_running",
                "message": "No solver process is currently running"
            }
        
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._is_solving = False
            return {
                "status": "stopped",
                "message": "Solver process has been stopped"
            }
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._is_solving = False
            return {
                "status": "killed",
                "message": "Solver process had to be forcefully terminated"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error stopping solver: {str(e)}"
            }
