import os
import subprocess
import threading
import logging
import sys
import uuid
import json
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

from .json_to_xml_converter import JSONtoXMLConverter

# Get the current working directory
CURRENT_DIR = os.getcwd()

# Define constants for solver paths and configuration - more flexible approach
# Try different potential locations for the cpsolver directory
POTENTIAL_CPSOLVER_PATHS = [
    os.path.join(CURRENT_DIR, "cpsolver"),        # In the current directory
    os.path.join(CURRENT_DIR, "..", "cpsolver"),  # One level up
    os.path.join(CURRENT_DIR, "cpsolver"),        # Explicitly in current directory
    os.path.join("/app", "cpsolver"),             # Docker container path
]

# Find the first path that exists
CPSOLVER_PATH = None
for path in POTENTIAL_CPSOLVER_PATHS:
    if os.path.exists(path):
        CPSOLVER_PATH = path
        break

# If no path exists, default to the first one
if CPSOLVER_PATH is None:
    CPSOLVER_PATH = POTENTIAL_CPSOLVER_PATHS[0]
    logging.warning(f"No cpsolver directory found. Defaulting to {CPSOLVER_PATH}")

class SolverService:
    """Service for running the Unitime solver operations."""
    
    def __init__(self, cpsolver_path=None):
        """Initialize the solver service with the path to the cpsolver directory."""
        # Allow cpsolver path to be passed in or use the default
        self.cpsolver_path = cpsolver_path or CPSOLVER_PATH
        if isinstance(self.cpsolver_path, Path):
            self.cpsolver_path = str(self.cpsolver_path)
            
        self.cpsolver_path = os.path.abspath(self.cpsolver_path)
        self.logger = logging.getLogger("solver_service")
        self._process = None
        self._solve_thread = None
        self._is_solving = False
        self._problem_processes = {}  # Dictionary to track multiple problems by ID
        
        # Create required directories if they don't exist
        if os.path.exists(self.cpsolver_path):
            # Create solved_output directory
            solved_output_dir = os.path.join(self.cpsolver_path, "solved_output")
            if not os.path.exists(solved_output_dir):
                os.makedirs(solved_output_dir, exist_ok=True)
                self.logger.info(f"Created solved_output directory: {solved_output_dir}")
                
            # Create input directory
            input_dir = os.path.join(self.cpsolver_path, "input")
            if not os.path.exists(input_dir):
                os.makedirs(input_dir, exist_ok=True)
                self.logger.info(f"Created input directory: {input_dir}")
        else:
            self.logger.warning(f"Cpsolver directory not found at: {self.cpsolver_path}")
        
        # Log information about paths for debugging
        self.logger.info(f"Current working directory: {os.getcwd()}")
        self.logger.info(f"Using cpsolver path: {self.cpsolver_path}")
        self.logger.info(f"Path exists: {os.path.exists(self.cpsolver_path)}")
        if os.path.exists(self.cpsolver_path):
            self.logger.info(f"Directory contents: {os.listdir(self.cpsolver_path)}")
    
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
            if not os.path.exists(self.cpsolver_path):
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
            self.logger.info(f"Changed directory to: {os.getcwd()}")
            
            # Check for JAR files
            jar_path = os.path.join(self.cpsolver_path, "cpsolver-1.4.74.jar")
            if not os.path.exists(jar_path):
                import glob
                jar_files = glob.glob(os.path.join(self.cpsolver_path, "cpsolver*.jar"))
                jar_files = [f for f in jar_files if not ('javadoc' in f or 'sources' in f)]
                if jar_files:
                    jar_path = jar_files[0]
                    self.logger.info(f"Found alternative JAR file: {jar_path}")
                else:
                    error_message = f"No suitable cpsolver JAR file found in {self.cpsolver_path}"
                    self.logger.error(error_message)
                    return {
                        "status": "error",
                        "message": error_message
                    }
            
            # Adjust the classpath separator based on the operating system
            separator = ";" if sys.platform.startswith("win") else ":"
            
            # Build classpath using just the main JAR - try to find dependent JARs in lib
            lib_dir = os.path.join(self.cpsolver_path, "lib")
            if os.path.exists(lib_dir) and os.path.isdir(lib_dir):
                self.logger.info(f"Found lib directory: {lib_dir}")
                lib_files = [os.path.join(lib_dir, f) for f in os.listdir(lib_dir) if f.endswith('.jar')]
                self.logger.info(f"Found lib files: {lib_files}")
                classpath = separator.join([jar_path] + lib_files)
            else:
                lib_dir = os.path.join(self.cpsolver_path, "libe")
                if os.path.exists(lib_dir) and os.path.isdir(lib_dir):
                    self.logger.info(f"Found libe directory: {lib_dir}")
                    lib_files = [os.path.join(lib_dir, f) for f in os.listdir(lib_dir) if f.endswith('.jar')]
                    self.logger.info(f"Found lib files: {lib_files}")
                    classpath = separator.join([jar_path] + lib_files)
                else:
                    self.logger.info("No lib directory found, using only main JAR")
                    classpath = jar_path
            
            self.logger.info(f"Using classpath: {classpath}")
            
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

    def solve_problem(self, problem_data: Dict[str, Any], problem_name: Optional[str] = None) -> Dict:
        """
        Process a user submitted problem in JSON format, convert to XML, and solve.
        
        Args:
            problem_data: Dictionary containing the JSON representation of the problem
            problem_name: Optional name for the problem
            
        Returns:
            Dict containing the status and problem ID
        """
        try:
            # Get absolute path to cpsolver directory
            cpsolver_abs_path = os.path.abspath(self.cpsolver_path)
            self.logger.info(f"Absolute cpsolver path: {cpsolver_abs_path}")
            
            # Log detailed environment info for debugging
            self.logger.info(f"Current working directory: {os.getcwd()}")
            self.logger.info(f"Directory exists check: {os.path.exists(cpsolver_abs_path)}")
            self.logger.info(f"Directory contents: {os.listdir(cpsolver_abs_path)}")
            
            # Check if the cpsolver directory exists and create necessary subdirectories
            if not os.path.exists(cpsolver_abs_path):
                error_message = f"Cpsolver directory not found at: {cpsolver_abs_path}"
                self.logger.error(error_message)
                return {
                    "status": "error",
                    "message": error_message
                }
            
            # Ensure solved_output directory exists
            solved_output_dir = os.path.join(cpsolver_abs_path, "solved_output")
            if not os.path.exists(solved_output_dir):
                os.makedirs(solved_output_dir, exist_ok=True)
                self.logger.info(f"Created solved_output directory: {solved_output_dir}")
            
            # Ensure input directory exists
            input_dir = os.path.join(cpsolver_abs_path, "input")
            if not os.path.exists(input_dir):
                os.makedirs(input_dir, exist_ok=True)
                self.logger.info(f"Created input directory: {input_dir}")
            
            # Check for the JAR file directly
            jar_path = os.path.join(cpsolver_abs_path, "cpsolver-1.4.74.jar")
            self.logger.info(f"Checking for JAR file at: {jar_path}")
            self.logger.info(f"JAR file exists: {os.path.exists(jar_path)}")
            
            # If jar file not found, try to find it with a glob pattern
            if not os.path.exists(jar_path):
                import glob
                jar_files = glob.glob(os.path.join(cpsolver_abs_path, "cpsolver*.jar"))
                jar_files = [f for f in jar_files if not ('javadoc' in f or 'sources' in f)]
                if jar_files:
                    jar_path = jar_files[0]
                    self.logger.info(f"Found alternative JAR file: {jar_path}")
                else:
                    error_message = f"No suitable cpsolver JAR file found in {cpsolver_abs_path}"
                    self.logger.error(error_message)
                    return {
                        "status": "error",
                        "message": error_message
                    }
            
            # Get the list of folders in solved_output before running the solver
            existing_folders = set()
            try:
                existing_folders = set(os.listdir(solved_output_dir))
                self.logger.info(f"Found {len(existing_folders)} existing folders in solved_output")
            except Exception as e:
                self.logger.warning(f"Error listing solved_output directory: {e}")
            
            # Use a temporary ID for the XML file
            temp_id = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
            
            # Convert JSON to XML
            try:
                converter = JSONtoXMLConverter(problem_data)
                xml_content = converter.convert()
                
                # Save the XML to the input folder with a temporary name
                xml_file_path = os.path.join(input_dir, f"{temp_id}.xml")
                with open(xml_file_path, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                    
                self.logger.info(f"Problem converted to XML and saved at {xml_file_path}")
            except Exception as e:
                error_message = f"Error converting JSON to XML: {str(e)}"
                self.logger.error(error_message)
                return {
                    "status": "error",
                    "message": error_message
                }
            
            # Store the original directory to go back to
            original_dir = os.getcwd()
            
            try:
                # Change to cpsolver directory for the command to work properly
                os.chdir(cpsolver_abs_path)
                self.logger.info(f"Changed directory to: {os.getcwd()}")
                
                # Adjust the classpath separator based on the operating system
                separator = ";" if sys.platform.startswith("win") else ":"
                
                # Build classpath using just the main JAR - try to find dependent JARs in lib
                lib_dir = os.path.join(cpsolver_abs_path, "lib")
                if os.path.exists(lib_dir) and os.path.isdir(lib_dir):
                    self.logger.info(f"Found lib directory: {lib_dir}")
                    lib_files = [os.path.join(lib_dir, f) for f in os.listdir(lib_dir) if f.endswith('.jar')]
                    self.logger.info(f"Found lib files: {lib_files}")
                    classpath = separator.join([jar_path] + lib_files)
                else:
                    self.logger.info("No lib directory found, using only main JAR")
                    classpath = jar_path
                
                self.logger.info(f"Using classpath: {classpath}")
                
                # Construct the command - use relative paths since we're in the cpsolver directory
                command = [
                    "java", "-Xmx512m", 
                    "-cp", classpath,
                    "org.cpsolver.coursett.Test", 
                    "config.cfg", 
                    os.path.join("input", f"{temp_id}.xml"), 
                    "solved_output/"
                ]
                
                # Log the command for debugging
                self.logger.info(f"Running command: {' '.join(command)}")
                
                # Run the command and capture output
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait a short time for the solver to create its output directory
                import time
                time.sleep(2)
                
                # Check for new folders in solved_output
                new_folders = set()
                try:
                    new_folders = set(os.listdir(solved_output_dir)) - existing_folders
                    self.logger.info(f"Found {len(new_folders)} new folders in solved_output: {new_folders}")
                except Exception as e:
                    self.logger.warning(f"Error listing solved_output directory after solver start: {e}")
                
                if not new_folders:
                    self.logger.warning("No new folder detected in solved_output directory")
                    # If no folder was created, we'll use a fallback ID
                    problem_id = f"{problem_name or 'problem'}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    # Create a directory for this problem's output
                    problem_dir = os.path.join(solved_output_dir, problem_id)
                    try:
                        os.makedirs(problem_dir, exist_ok=True)
                        self.logger.info(f"Created fallback problem directory: {problem_dir}")
                    except Exception as e:
                        self.logger.error(f"Error creating fallback directory: {e}")
                        # Change directory back before raising
                        os.chdir(original_dir)
                        return {
                            "status": "error",
                            "message": f"Error creating problem directory: {str(e)}"
                        }
                else:
                    # Use the first new folder as the problem ID
                    problem_id = list(new_folders)[0]
                    problem_dir = os.path.join(solved_output_dir, problem_id)
                
                # Save the original JSON for reference
                json_file_path = os.path.join(problem_dir, "original.json")
                try:
                    with open(json_file_path, 'w', encoding='utf-8') as f:
                        json.dump(problem_data, f, indent=2)
                    self.logger.info(f"Saved original JSON to {json_file_path}")
                except Exception as e:
                    self.logger.warning(f"Could not save original JSON: {e}")
                
                # Store the process info
                self._problem_processes[problem_id] = {
                    "process": process,
                    "is_solving": True,
                    "start_time": datetime.now()
                }
                
                # Create a function to monitor the process
                def monitor_problem_process(pid):
                    try:
                        process_info = self._problem_processes.get(pid)
                        if not process_info:
                            return
                            
                        proc = process_info["process"]
                        stdout, stderr = proc.communicate()
                        exit_code = proc.returncode
                        
                        # Update status
                        self._problem_processes[pid]["is_solving"] = False
                        self._problem_processes[pid]["exit_code"] = exit_code
                        self._problem_processes[pid]["stdout"] = stdout
                        self._problem_processes[pid]["stderr"] = stderr
                        self._problem_processes[pid]["end_time"] = datetime.now()
                        
                        # Log the outcome
                        self.logger.info(f"Problem {pid} solver process completed with exit code: {exit_code}")
                        if stderr:
                            self.logger.error(f"Problem {pid} solver error output: {stderr}")
                        if stdout:
                            self.logger.info(f"Problem {pid} solver output: {stdout[:500]}...") # Log first 500 chars
                        
                        # Clean up the temporary XML file
                        try:
                            os.remove(xml_file_path)
                            self.logger.info(f"Removed temporary XML file: {xml_file_path}")
                        except Exception as e:
                            self.logger.warning(f"Could not remove temporary XML file: {e}")
                        
                    except Exception as e:
                        self.logger.error(f"Error in monitor thread for problem {pid}: {e}")
                        if pid in self._problem_processes:
                            self._problem_processes[pid]["is_solving"] = False
                            self._problem_processes[pid]["error"] = str(e)
                    finally:
                        # Return to the original directory
                        os.chdir(original_dir)
                
                # Start the monitoring in a separate thread
                thread = threading.Thread(target=monitor_problem_process, args=(problem_id,))
                thread.start()
                
                return {
                    "status": "started",
                    "message": "Solver process started successfully",
                    "problem_id": problem_id
                }
            finally:
                # Make sure we always go back to the original directory if we change it
                try:
                    os.chdir(original_dir)
                    self.logger.info(f"Changed directory back to: {os.getcwd()}")
                except Exception as e:
                    self.logger.error(f"Error changing back to original directory: {e}")
        
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Error running solver for problem: {error_message}")
                
            return {
                "status": "error",
                "message": f"Failed to start solver: {error_message}",
                "problem_id": None
            }
    
    def get_problem_status(self, problem_id: str) -> Dict:
        """
        Get the status of a specific problem.
        
        Args:
            problem_id: ID of the problem to check
            
        Returns:
            Dict containing the status information
        """
        debug_log_content = None
        has_error = False
        error_message = ""
        
        # Try to read the debug.log file if it exists
        problem_dir = os.path.join(self.cpsolver_path, "solved_output", problem_id)
        debug_log_path = os.path.join(problem_dir, "debug.log")
        if os.path.exists(debug_log_path):
            try:
                with open(debug_log_path, 'r', encoding='utf-8', newline='') as f:
                    # Split the log into lines and preserve each line
                    debug_log_content = f.read().splitlines()
                    
                # Check for error messages in the debug log
                for line in debug_log_content:
                    if "ERROR" in line or "Exception" in line or "error" in line.lower():
                        has_error = True
                        error_message = line
                        break
                        
                self.logger.info(f"Read debug.log for problem {problem_id}")
            except Exception as e:
                self.logger.warning(f"Error reading debug.log for problem {problem_id}: {str(e)}")
                debug_log_content = [f"Error reading debug.log: {str(e)}"]
        
        # Check if the problem exists in our tracking dictionary
        if problem_id not in self._problem_processes:
            # Check if the problem folder exists in the solved_output directory
            if not os.path.exists(problem_dir):
                return {
                    "status": "error",
                    "message": f"Problem with ID {problem_id} not found",
                    "problem_id": problem_id,
                    "solution_available": False,
                    "debug_log": debug_log_content
                }
            
            # Check if a solution.xml file exists
            solution_file = os.path.join(problem_dir, "solution.xml")
            solution_available = os.path.exists(solution_file)
            
            if solution_available:
                return {
                    "status": "completed",
                    "message": "Problem has been solved",
                    "problem_id": problem_id,
                    "solution_available": True,
                    "debug_log": debug_log_content
                }
            elif has_error:
                return {
                    "status": "error",
                    "message": f"Solver encountered an error: {error_message}",
                    "problem_id": problem_id,
                    "solution_available": False,
                    "debug_log": debug_log_content
                }
            else:
                return {
                    "status": "not_started",
                    "message": "Problem found but not yet processed",
                    "problem_id": problem_id,
                    "solution_available": False,
                    "debug_log": debug_log_content
                }
        
        # Get the process info
        process_info = self._problem_processes[problem_id]
        
        # Check if the solution file exists
        solution_file = os.path.join(self.cpsolver_path, "solved_output", problem_id, "solution.xml")
        solution_available = os.path.exists(solution_file)
        
        if process_info["is_solving"]:
            elapsed_time = datetime.now() - process_info["start_time"]
            return {
                "status": "running",
                "message": f"Solver is running (elapsed time: {elapsed_time.total_seconds():.2f} seconds)",
                "problem_id": problem_id,
                "solution_available": solution_available,
                "debug_log": debug_log_content
            }
        else:
            if "exit_code" in process_info and process_info["exit_code"] == 0 and not has_error:
                return {
                    "status": "completed",
                    "message": "Solver completed successfully",
                    "problem_id": problem_id,
                    "solution_available": solution_available,
                    "debug_log": debug_log_content
                }
            elif has_error or ("error" in process_info) or ("exit_code" in process_info and process_info["exit_code"] != 0):
                error_msg = process_info.get("error", error_message if has_error else f"Exit code: {process_info.get('exit_code', 'unknown')}")
                return {
                    "status": "error",
                    "message": f"Solver encountered an error: {error_msg}",
                    "problem_id": problem_id,
                    "solution_available": solution_available,
                    "debug_log": debug_log_content
                }
            else:
                return {
                    "status": "completed",
                    "message": f"Solver completed with exit code: {process_info.get('exit_code', 'unknown')}",
                    "problem_id": problem_id,
                    "solution_available": solution_available,
                    "debug_log": debug_log_content
                }
    
    def stop_problem_solver(self, problem_id: str) -> Dict:
        """
        Stop a specific problem solver process.
        
        Args:
            problem_id: ID of the problem to stop
            
        Returns:
            Dict containing the result of the stop operation
        """
        if problem_id not in self._problem_processes:
            return {
                "status": "not_running",
                "message": f"No solver process found for problem ID {problem_id}",
                "problem_id": problem_id
            }
        
        process_info = self._problem_processes[problem_id]
        
        if not process_info["is_solving"]:
            return {
                "status": "not_running",
                "message": f"Solver for problem ID {problem_id} is not currently running",
                "problem_id": problem_id
            }
        
        try:
            process_info["process"].terminate()
            process_info["process"].wait(timeout=5)
            process_info["is_solving"] = False
            return {
                "status": "stopped",
                "message": f"Solver process for problem ID {problem_id} has been stopped",
                "problem_id": problem_id
            }
        except subprocess.TimeoutExpired:
            process_info["process"].kill()
            process_info["is_solving"] = False
            return {
                "status": "killed",
                "message": f"Solver process for problem ID {problem_id} had to be forcefully terminated",
                "problem_id": problem_id
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error stopping solver for problem ID {problem_id}: {str(e)}",
                "problem_id": problem_id
            }

    def solve_problem_from_xml(self, xml_content: str, problem_name: Optional[str] = None) -> Dict:
        """
        Process a user submitted problem in XML format directly.
        
        Args:
            xml_content: String containing the XML representation of the problem
            problem_name: Optional name for the problem
            
        Returns:
            Dict containing the status and problem ID
        """
        try:
            # Get absolute path to cpsolver directory
            cpsolver_abs_path = os.path.abspath(self.cpsolver_path)
            self.logger.info(f"Absolute cpsolver path: {cpsolver_abs_path}")
            
            # Check if the cpsolver directory exists and create necessary subdirectories
            if not os.path.exists(cpsolver_abs_path):
                error_message = f"Cpsolver directory not found at: {cpsolver_abs_path}"
                self.logger.error(error_message)
                return {
                    "status": "error",
                    "message": error_message
                }
            
            # Ensure solved_output directory exists
            solved_output_dir = os.path.join(cpsolver_abs_path, "solved_output")
            if not os.path.exists(solved_output_dir):
                os.makedirs(solved_output_dir, exist_ok=True)
                self.logger.info(f"Created solved_output directory: {solved_output_dir}")
            
            # Ensure input directory exists
            input_dir = os.path.join(cpsolver_abs_path, "input")
            if not os.path.exists(input_dir):
                os.makedirs(input_dir, exist_ok=True)
                self.logger.info(f"Created input directory: {input_dir}")
            
            # Get the list of folders in solved_output before running the solver
            existing_folders = set()
            try:
                existing_folders = set(os.listdir(solved_output_dir))
                self.logger.info(f"Found {len(existing_folders)} existing folders in solved_output")
            except Exception as e:
                self.logger.warning(f"Error listing solved_output directory: {e}")
            
            # Use a temporary ID for the XML file
            temp_id = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
            
            # Save the XML to the input folder with the temporary name
            xml_file_path = os.path.join(input_dir, f"{temp_id}.xml")
            try:
                with open(xml_file_path, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                self.logger.info(f"XML saved at {xml_file_path}")
            except Exception as e:
                error_message = f"Error saving XML file: {str(e)}"
                self.logger.error(error_message)
                return {
                    "status": "error",
                    "message": error_message
                }
            
            # Store the original directory to go back to
            original_dir = os.getcwd()
            
            try:
                # Change to cpsolver directory for the command to work properly
                os.chdir(cpsolver_abs_path)
                self.logger.info(f"Changed directory to: {os.getcwd()}")
                
                # Check for JAR files
                jar_path = os.path.join(cpsolver_abs_path, "cpsolver-1.4.74.jar")
                if not os.path.exists(jar_path):
                    import glob
                    jar_files = glob.glob(os.path.join(cpsolver_abs_path, "cpsolver*.jar"))
                    jar_files = [f for f in jar_files if not ('javadoc' in f or 'sources' in f)]
                    if jar_files:
                        jar_path = jar_files[0]
                        self.logger.info(f"Found alternative JAR file: {jar_path}")
                    else:
                        error_message = f"No suitable cpsolver JAR file found in {cpsolver_abs_path}"
                        self.logger.error(error_message)
                        return {
                            "status": "error",
                            "message": error_message
                        }
                
                # Adjust the classpath separator based on the operating system
                separator = ";" if sys.platform.startswith("win") else ":"
                
                # Build classpath using just the main JAR - try to find dependent JARs in lib
                lib_dir = os.path.join(cpsolver_abs_path, "lib")
                if os.path.exists(lib_dir) and os.path.isdir(lib_dir):
                    self.logger.info(f"Found lib directory: {lib_dir}")
                    lib_files = [os.path.join(lib_dir, f) for f in os.listdir(lib_dir) if f.endswith('.jar')]
                    self.logger.info(f"Found lib files: {lib_files}")
                    classpath = separator.join([jar_path] + lib_files)
                else:
                    self.logger.info("No lib directory found, using only main JAR")
                    classpath = jar_path
                
                self.logger.info(f"Using classpath: {classpath}")
                
                # Construct the command - use relative paths since we're in the cpsolver directory
                command = [
                    "java", "-Xmx512m", 
                    "-cp", classpath,
                    "org.cpsolver.coursett.Test", 
                    "config.cfg", 
                    os.path.join("input", f"{temp_id}.xml"), 
                    "solved_output/"
                ]
                
                # Log the command for debugging
                self.logger.info(f"Running command: {' '.join(command)}")
                
                # Run the command and capture output
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait a short time for the solver to create its output directory
                import time
                time.sleep(2)
                
                # Check for new folders in solved_output
                new_folders = set()
                try:
                    new_folders = set(os.listdir(solved_output_dir)) - existing_folders
                    self.logger.info(f"Found {len(new_folders)} new folders in solved_output: {new_folders}")
                except Exception as e:
                    self.logger.warning(f"Error listing solved_output directory after solver start: {e}")
                
                if not new_folders:
                    self.logger.warning("No new folder detected in solved_output directory")
                    # If no folder was created, we'll use a fallback ID
                    problem_id = f"{problem_name or 'problem'}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    # Create a directory for this problem's output
                    problem_dir = os.path.join(solved_output_dir, problem_id)
                    try:
                        os.makedirs(problem_dir, exist_ok=True)
                        self.logger.info(f"Created fallback problem directory: {problem_dir}")
                    except Exception as e:
                        self.logger.error(f"Error creating fallback directory: {e}")
                        # Change directory back before raising
                        os.chdir(original_dir)
                        return {
                            "status": "error",
                            "message": f"Error creating problem directory: {str(e)}"
                        }
                else:
                    # Use the first new folder as the problem ID
                    problem_id = list(new_folders)[0]
                    problem_dir = os.path.join(solved_output_dir, problem_id)
                
                # Save the original XML for reference
                xml_file_path_copy = os.path.join(problem_dir, "original.xml")
                try:
                    with open(xml_file_path_copy, 'w', encoding='utf-8') as f:
                        f.write(xml_content)
                    self.logger.info(f"Saved original XML to {xml_file_path_copy}")
                except Exception as e:
                    self.logger.warning(f"Could not save original XML: {e}")
                
                # Store the process info
                self._problem_processes[problem_id] = {
                    "process": process,
                    "is_solving": True,
                    "start_time": datetime.now()
                }
                
                # Create a function to monitor the process
                def monitor_problem_process(pid):
                    try:
                        process_info = self._problem_processes.get(pid)
                        if not process_info:
                            return
                            
                        proc = process_info["process"]
                        stdout, stderr = proc.communicate()
                        exit_code = proc.returncode
                        
                        # Update status
                        self._problem_processes[pid]["is_solving"] = False
                        self._problem_processes[pid]["exit_code"] = exit_code
                        self._problem_processes[pid]["stdout"] = stdout
                        self._problem_processes[pid]["stderr"] = stderr
                        self._problem_processes[pid]["end_time"] = datetime.now()
                        
                        # Log the outcome
                        self.logger.info(f"Problem {pid} solver process completed with exit code: {exit_code}")
                        if stderr:
                            self.logger.error(f"Problem {pid} solver error output: {stderr}")
                        if stdout:
                            self.logger.info(f"Problem {pid} solver output: {stdout[:500]}...") # Log first 500 chars
                        
                        # Clean up the temporary XML file
                        try:
                            os.remove(xml_file_path)
                            self.logger.info(f"Removed temporary XML file: {xml_file_path}")
                        except Exception as e:
                            self.logger.warning(f"Could not remove temporary XML file: {e}")
                        
                    except Exception as e:
                        self.logger.error(f"Error in monitor thread for problem {pid}: {e}")
                        if pid in self._problem_processes:
                            self._problem_processes[pid]["is_solving"] = False
                            self._problem_processes[pid]["error"] = str(e)
                    finally:
                        # Return to the original directory
                        os.chdir(original_dir)
                
                # Start the monitoring in a separate thread
                thread = threading.Thread(target=monitor_problem_process, args=(problem_id,))
                thread.start()
                
                return {
                    "status": "started",
                    "message": "Solver process started successfully",
                    "problem_id": problem_id
                }
            finally:
                # Make sure we always go back to the original directory if we change it
                try:
                    os.chdir(original_dir)
                    self.logger.info(f"Changed directory back to: {os.getcwd()}")
                except Exception as e:
                    self.logger.error(f"Error changing back to original directory: {e}")
        
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Error running solver for problem: {error_message}")
                
            return {
                "status": "error",
                "message": f"Failed to start solver: {error_message}",
                "problem_id": None
            }
