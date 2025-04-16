#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import shutil
import subprocess
import platform

def print_colored(text, color_code):
    """Print colored text to the console."""
    # Skip color codes on Windows unless running in a supported terminal
    if platform.system() == "Windows" and not os.environ.get("TERM"):
        print(text)
    else:
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

def test_java_version():
    """Test the Java version and return True if compatible."""
    try:
        result = subprocess.run(
            ["java", "-version"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        stderr = result.stderr
        if "version" in stderr:
            print_success(f"Java version detected: {stderr.split()[2].strip('\"')}")
            return True
        else:
            print_error("Java version information not found.")
            return False
    except Exception as e:
        print_error(f"Error checking Java version: {e}")
        return False

def check_directory_permissions(path):
    """Check if the directory has read/write permissions."""
    read_access = os.access(path, os.R_OK)
    write_access = os.access(path, os.W_OK)
    
    if read_access and write_access:
        print_success(f"Directory {path} has read and write permissions.")
        return True
    else:
        permission_issues = []
        if not read_access:
            permission_issues.append("read")
        if not write_access:
            permission_issues.append("write")
        print_error(f"Directory {path} lacks {' and '.join(permission_issues)} permissions.")
        return False

def find_jar_file(path, pattern="cpsolver*.jar"):
    """Find JAR files matching a pattern."""
    import glob
    jar_files = glob.glob(os.path.join(path, pattern))
    # Filter out javadoc and sources JARs
    jar_files = [f for f in jar_files if not ('javadoc' in f or 'sources' in f)]
    return jar_files

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
    
    # Check directory permissions
    if not check_directory_permissions(cpsolver_path):
        print_error("The cpsolver directory needs proper read/write permissions for the API to function correctly.")
        if platform.system() == "Windows":
            print_info("You may need to run this script as Administrator or adjust permissions.")
        else:
            print_info("You may need to run: chmod -R u+rw cpsolver/")
    
    # Check for JAR files with flexible matching
    main_jar_files = find_jar_file(cpsolver_path)
    if main_jar_files:
        print_success(f"Found main JAR file: {os.path.basename(main_jar_files[0])}")
    else:
        print_error("No cpsolver JAR file found. Please ensure it's available in the cpsolver directory.")
        return 1
    
    # Check for lib directory and required dependencies
    lib_dir = cpsolver_path / "lib"
    if lib_dir.exists() and lib_dir.is_dir():
        print_success(f"Found lib directory: {lib_dir}")
        # Check for required libraries
        required_libraries = ["log4j-api", "log4j-core", "dom4j"]
        missing_libraries = []
        for lib in required_libraries:
            lib_files = find_jar_file(lib_dir, f"{lib}*.jar")
            if lib_files:
                print_success(f"Found library: {os.path.basename(lib_files[0])}")
            else:
                print_error(f"Missing required library: {lib}")
                missing_libraries.append(lib)
        
        if missing_libraries:
            print_error("Some required libraries are missing. The solver may not work properly.")
    else:
        print_error("lib directory not found. Please ensure it exists in the cpsolver directory.")
        return 1
    
    # Check for config file
    config_file = cpsolver_path / "config.cfg"
    if config_file.exists():
        print_success(f"Found configuration file: {config_file}")
    else:
        print_error(f"Missing configuration file: {config_file}")
        return 1
    
    # Check for input directory and files
    input_dir = cpsolver_path / "input"
    if not input_dir.exists():
        print_info(f"Creating input directory at: {input_dir}")
        try:
            input_dir.mkdir()
            print_success("Created input directory successfully.")
        except Exception as e:
            print_error(f"Failed to create input directory: {e}")
            return 1
    else:
        print_success("input directory exists.")
    
    # Check for Java
    print_info("Checking for Java installation...")
    java_path = shutil.which("java")
    if java_path:
        print_success(f"Java found at: {java_path}")
        test_java_version()
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
        
        # Check if solved_output directory has sample solution files
        solution_files = list(solved_output_path.glob("*/solution.xml"))
        if solution_files:
            print_success(f"Found {len(solution_files)} existing solution files. Solution retrieval will work for these problems.")
        else:
            print_info("No existing solution files found. Submit some problems first before retrieving solutions.")
    
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