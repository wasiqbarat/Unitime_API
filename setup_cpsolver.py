#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import shutil

def print_colored(text, color_code):
    """Print colored text to the console."""
    print(f"\033[{color_code}m{text}\033[0m")

def print_success(text):
    """Print success message in green."""
    print_colored(text, '92')

def print_error(text):
    """Print error message in red."""
    print_colored(text, '91')

def print_info(text):
    """Print info message in blue."""
    print_colored(text, '94')

def main():
    """Main entry point for the setup script."""
    print_info("===== Unitime Solver API Setup =====")
    print_info("Checking for cpsolver directory...")
    
    # Get the current working directory
    current_dir = Path(os.getcwd())
    print_info(f"Current working directory: {current_dir}")
    
    # Try different potential locations for the cpsolver directory
    potential_paths = [
        Path("cpsolver"),              # In the current directory
        Path("../cpsolver"),           # One level up
        Path("./cpsolver"),            # Explicitly in current directory
        current_dir / "cpsolver",      # Using absolute path
        Path("/app/cpsolver"),         # Docker container path
    ]
    
    found_paths = []
    
    # Check all potential paths
    for path in potential_paths:
        if path.exists() and path.is_dir():
            print_success(f"Found cpsolver directory at: {path}")
            found_paths.append(path)
        else:
            print_info(f"Directory not found at: {path}")
    
    if not found_paths:
        print_error("No cpsolver directory found in any of the expected locations.")
        print_info("Please ensure that the cpsolver directory is properly installed or set the SOLVER_PATH environment variable.")
        return 1
    
    # Use the first found path for verification
    cpsolver_path = found_paths[0]
    print_info(f"Using cpsolver path: {cpsolver_path}")
    
    # Check for required files
    required_files = [
        "cpsolver-1.4.74.jar",
        "lib/log4j-api-2.20.0.jar",
        "lib/log4j-core-2.20.0.jar",
        "lib/dom4j-2.1.4.jar",
        "config.cfg",
        "input/problem.xml"
    ]
    
    missing_files = []
    for file in required_files:
        file_path = cpsolver_path / file
        if file_path.exists():
            print_success(f"Found required file: {file}")
        else:
            print_error(f"Missing required file: {file}")
            missing_files.append(file)
    
    if missing_files:
        print_error("Some required files are missing. Please ensure the cpsolver directory is properly set up.")
        return 1
    
    # Check for Java
    print_info("Checking for Java installation...")
    java_path = shutil.which("java")
    if java_path:
        print_success(f"Java found at: {java_path}")
    else:
        print_error("Java not found. Please ensure Java is installed and available in PATH.")
        return 1
    
    # Create solved_output directory if it doesn't exist
    solved_output_path = cpsolver_path / "solved_output"
    if not solved_output_path.exists():
        print_info(f"Creating solved_output directory at: {solved_output_path}")
        try:
            solved_output_path.mkdir()
            print_success("Created solved_output directory successfully.")
        except Exception as e:
            print_error(f"Failed to create solved_output directory: {e}")
            return 1
    else:
        print_success("solved_output directory already exists.")
    
    # All checks passed
    print_success("All checks passed! The cpsolver setup is valid.")
    print_info("You can now run the Unitime Solver API with the following command:")
    print_info("    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    
    # If a path was found, suggest setting the environment variable
    if found_paths:
        print_info("To explicitly set the cpsolver path, use the SOLVER_PATH environment variable:")
        print_info(f"    set SOLVER_PATH={found_paths[0]}  # Windows")
        print_info(f"    export SOLVER_PATH={found_paths[0]}  # Linux/macOS")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 