"""
Solution service module for retrieving and converting solver solutions.

This module provides functionality to:
- Retrieve raw XML solutions from the solver's output directory
- Convert XML solutions to a structured JSON format for frontend consumption
- Handle error cases when solutions are not available
"""

import os
import logging
import xml.etree.ElementTree as ET
import re
from typing import Dict, List, Optional, Any

# Import configuration constants from solver_service
from .solver_service import CPSOLVER_PATH

class SolutionService:
    """Service for retrieving and converting solver solutions."""
    
    def __init__(self, cpsolver_path=None):
        """Initialize the solution service with the path to the cpsolver directory."""
        self.cpsolver_path = cpsolver_path or CPSOLVER_PATH
        self.logger = logging.getLogger("solution_service")
    
    def get_solution_xml(self, problem_id: str) -> Optional[str]:
        """
        Get the raw XML solution for a problem.
        
        Args:
            problem_id: The unique identifier of the problem
            
        Returns:
            The raw XML content of the solution file, or None if no solution exists
        """
        solution_path = os.path.join(self.cpsolver_path, "solved_output", problem_id, "solution.xml")
        if not os.path.exists(solution_path):
            self.logger.warning(f"Solution file not found for problem {problem_id}")
            return None
            
        try:
            with open(solution_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error reading solution file for problem {problem_id}: {e}")
            return None
    
    def get_solution_json(self, problem_id: str) -> Optional[Dict]:
        """
        Get the solution in JSON format.
        
        Args:
            problem_id: The unique identifier of the problem
            
        Returns:
            A dictionary containing the converted solution data, or None if no solution exists
        """
        xml_content = self.get_solution_xml(problem_id)
        if not xml_content:
            return None
            
        # Convert XML to JSON
        try:
            converter = XMLtoJSONConverter(xml_content)
            return converter.convert()
        except Exception as e:
            self.logger.error(f"Error converting solution to JSON for problem {problem_id}: {e}")
            return {
                "error": True,
                "message": f"Failed to convert solution: {str(e)}"
            }


class XMLtoJSONConverter:
    """Converter for transforming XML solution data to JSON format."""
    
    def __init__(self, xml_content: str):
        """
        Initialize the converter with XML content.
        
        Args:
            xml_content: The raw XML solution string
        """
        self.xml_content = xml_content
        self.logger = logging.getLogger("xml_to_json_converter")
        
    def convert(self) -> Dict:
        """
        Convert solution XML to JSON format.
        
        Returns:
            A dictionary containing the structured solution data
        """
        try:
            root = ET.fromstring(self.xml_content)
            
            # Create base result structure
            result = {
                "solution": {
                    "info": self._extract_solution_info(root),
                    "classes": self._extract_classes(root)
                }
            }
            
            return result
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML format: {e}")
        
    def _extract_solution_info(self, root) -> Dict:
        """
        Extract solution metadata from the XML root.
        
        Args:
            root: The XML root element
            
        Returns:
            A dictionary containing solution metadata
        """
        # Extract runtime from XML comments first
        runtime = "Less than a minute"  # Default value
        
        # Try to extract runtime from comments in the original XML
        if self.xml_content:
            # Use regex to find the Time: line in the comments
            time_match = re.search(r'Time:\s*([0-9.]+)\s*min', self.xml_content)
            if time_match:
                time_value = float(time_match.group(1))
                if time_value > 0:
                    runtime = f"{time_value} minutes"
        
        info = {
            "version": root.get("version", ""),
            "created": root.get("created", ""),
            "runtime": runtime
        }
        
        # Extract statistics from the XML
        stats = {}
        
        # Try to extract statistics from XML comments
        comment_pattern = r'<!--Solution Info:(.*?)-->'
        comment_match = re.search(comment_pattern, self.xml_content, re.DOTALL)
        if comment_match:
            comment_text = comment_match.group(1)
            lines = comment_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # Skip time field as we handle it separately
                        if key != "Time":
                            stats[key] = value
        
        # Also look for explicit statistic elements
        for stat in root.findall(".//statistic"):
            name = stat.get("name", "")
            value = stat.text or ""
            stats[name] = value
            
        if stats:
            info["statistics"] = stats
            
        return info
        
    def _extract_classes(self, root) -> List[Dict]:
        """
        Extract class assignments from the XML root.
        
        Args:
            root: The XML root element
            
        Returns:
            A list of dictionaries containing class assignment data
        """
        classes = []
        
        # Find all class elements in the solution
        for class_elem in root.findall(".//classes/class"):
            class_id = class_elem.get("id", "")
            
            class_data = {
                "id": class_id,
                "name": class_elem.get("name", ""),
                "offering": class_elem.get("offering", ""),
                "assignment": {}
            }
            
            # Find assigned time (the time element with solution="true")
            assigned_time = None
            for time_elem in class_elem.findall("time[@solution='true']"):
                assigned_time = time_elem
                break
                
            if assigned_time is not None:
                days = assigned_time.get("days", "")
                start_slot = int(assigned_time.get("start", "0"))
                length = int(assigned_time.get("length", "0"))
                
                # Convert to human-readable format
                start_hour = start_slot // 12
                start_minute = (start_slot % 12) * 5
                
                end_slot = start_slot + length
                end_hour = end_slot // 12
                end_minute = (end_slot % 12) * 5
                
                # Format times in 12-hour format with AM/PM
                start_time = self._format_time(start_hour, start_minute)
                end_time = self._format_time(end_hour, end_minute)
                
                class_data["assignment"]["time"] = {
                    "days": self._decode_days(days),
                    "start": start_time,
                    "end": end_time,
                    "raw": {
                        "days": days,
                        "start_slot": start_slot,
                        "length": length
                    }
                }
            
            # Find assigned rooms (room elements with solution="true")
            rooms = []
            for room_elem in class_elem.findall("room[@solution='true']"):
                rooms.append({
                    "id": room_elem.get("id", ""),
                    "name": room_elem.get("name", "")
                })
                
            if rooms:
                class_data["assignment"]["rooms"] = rooms
                
            # Find assigned instructors (instructor elements with solution="true")
            instructors = []
            for instructor_elem in class_elem.findall("instructor[@solution='true']"):
                instructors.append({
                    "id": instructor_elem.get("id", "")
                })
                
            if instructors:
                class_data["assignment"]["instructors"] = instructors
            
            # Only add classes that have assignments
            if class_data["assignment"]:
                classes.append(class_data)
            
        self.logger.info(f"Extracted {len(classes)} class assignments from solution XML")
        return classes
    
    def _format_time(self, hour: int, minute: int) -> str:
        """
        Format time in 12-hour format with AM/PM.
        
        Args:
            hour: Hour (0-23)
            minute: Minute (0-59)
            
        Returns:
            Formatted time string (e.g., "9:30 AM")
        """
        period = "AM" if hour < 12 else "PM"
        
        # Convert to 12-hour format
        display_hour = hour % 12
        if display_hour == 0:
            display_hour = 12
            
        return f"{display_hour}:{minute:02d} {period}"
    
    def _decode_days(self, days_pattern: str) -> List[str]:
        """
        Decode days pattern to readable format.
        
        Args:
            days_pattern: The binary days pattern (e.g., "1000100" or "۱۰۰۰۰۰۰")
            
        Returns:
            A list of day names corresponding to the pattern
        """
        # Note: The index mapping depends on the solver's configuration
        # This assumes days start with Monday as index 0
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        result = []
        
        # Handle both regular and Unicode digits
        for i, char in enumerate(days_pattern):
            if i >= len(day_names):
                break
                
            # Check for both ASCII "1" and Persian/Arabic "۱" (unicode) 
            if char == "1" or char == "۱":
                result.append(day_names[i])
                
        return result