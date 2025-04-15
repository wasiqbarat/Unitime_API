#!/usr/bin/env python3
"""
JSON to XML Converter for University Course Timetabling

This script converts a JSON input format for university course timetabling
to the XML format required by the Cpsolver library.
"""

import json
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
import datetime
import argparse
import sys
import re
from typing import Dict, List, Any, Tuple, Optional

class JSONtoXMLConverter:
    """
    Converter class for transforming JSON timetabling data to XML format
    compatible with Cpsolver library.
    """
    
    def __init__(self, json_data: Dict[str, Any]):
        """
        Initialize the converter with JSON data.
        
        Args:
            json_data: Dictionary containing the JSON data
        """
        self.json_data = json_data
        self.root = None
        self.day_map = {
            "Saturday": 0,
            "Sunday": 1,
            "Monday": 2,
            "Tuesday": 3,
            "Wednesday": 4,
            "Thursday": 5,
            "Friday": 6
        }
        
        # Default location for rooms if not specified
        self.default_location = "450,450"
        
        # Counter for constraint IDs
        self.constraint_id_counter = 1
        
        # ID mapping for non-numeric IDs
        self.id_mapping = {}
        self.next_numeric_id = 1000  # Starting ID for replacement
        
    def ensure_numeric_id(self, id_value):
        """
        Ensure that the ID is numeric.
        
        Args:
            id_value: The ID value to check
            
        Returns:
            A numeric ID value
        """
        # If already numeric, return as int
        if isinstance(id_value, (int, float)) or (isinstance(id_value, str) and id_value.isdigit()):
            return int(id_value)
            
        # If string but not numeric, create a mapping
        if isinstance(id_value, str):
            if id_value not in self.id_mapping:
                self.id_mapping[id_value] = self.next_numeric_id
                self.next_numeric_id += 1
            return self.id_mapping[id_value]
            
        # Default case
        return self.next_numeric_id
        
    def convert(self) -> str:
        """
        Convert JSON data to XML format.
        
        Returns:
            String containing the formatted XML
        """
        # Create root element
        self.root = ET.Element("timetable")
        
        # Add root attributes from general section
        general = self.json_data.get("general", {})
        self.root.set("version", "2.4")
        self.root.set("initiative", "puWestLafayetteTrdtn")  # Default value
        self.root.set("term", general.get("academic_session", "2025Fal"))
        self.root.set("year", str(general.get("year", 2025)))
        self.root.set("created", datetime.datetime.now().strftime("%a %b %d %H:%M:%S  %Y"))
        self.root.set("nrDays", "7")
        self.root.set("slotsPerDay", "288")
        
        # Add comment
        comment = ET.Comment(general.get("description", "University Course Timetabling"))
        self.root.append(comment)
        
        # Process rooms
        self._process_rooms()
        
        # Process classes
        self._process_classes()
        
        # Process constraints (always include the groupConstraints element)
        group_constraints_elem = ET.SubElement(self.root, "groupConstraints")
        
        # Add mutually exclusive constraints if available
        mutually_exclusive = self.json_data.get("mutuallyExclusive", {})
        if mutually_exclusive and mutually_exclusive.get("pairs", []):
            self._add_mutually_exclusive_constraints(group_constraints_elem)
        
        # Convert to string with pretty formatting
        rough_string = ET.tostring(self.root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def _process_rooms(self):
        """Process rooms data and add to XML"""
        rooms_data = self.json_data.get("rooms", {})
        if not rooms_data:
            # Create at least one dummy room if no rooms are provided
            rooms_elem = ET.SubElement(self.root, "rooms")
            room_elem = ET.SubElement(rooms_elem, "room")
            room_elem.set("id", "1")
            room_elem.set("constraint", "true")
            room_elem.set("capacity", "100")
            room_elem.set("location", self.default_location)
            return
            
        rooms_elem = ET.SubElement(self.root, "rooms")
        
        # Skip the description field
        for room_id, capacity in rooms_data.items():
            if room_id == "description":
                continue
                
            # Ensure numeric room ID
            numeric_room_id = self.ensure_numeric_id(room_id)
                
            room_elem = ET.SubElement(rooms_elem, "room")
            room_elem.set("id", str(numeric_room_id))
            room_elem.set("constraint", "true")
            room_elem.set("capacity", str(capacity))
            room_elem.set("location", self.default_location)
    
    def _convert_time_to_slots(self, time_str: str) -> Tuple[int, int]:
        """
        Convert time string (e.g., "7:45-9:15") to start slot and length.
        
        Args:
            time_str: Time range string in format "HH:MM-HH:MM"
            
        Returns:
            Tuple of (start_slot, length_in_slots)
        """
        start_time, end_time = time_str.split('-')
        
        # Parse start time
        start_hour, start_min = map(int, start_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        
        # Parse end time
        end_hour, end_min = map(int, end_time.split(':'))
        end_minutes = end_hour * 60 + end_min
        
        # Calculate slots (assuming 5-minute slots)
        start_slot = start_minutes // 5
        length = (end_minutes - start_minutes) // 5
        
        return start_slot, length
    
    def _get_day_pattern(self, day_index: int) -> str:
        """
        Generate a binary day pattern string for XML.
        
        Args:
            day_index: Index of the day (0=Saturday, 1=Sunday, etc.)
            
        Returns:
            Binary string representing the day pattern
        """
        pattern = ['0'] * 7
        pattern[day_index] = '1'
        return ''.join(pattern)
    
    def _get_preference_value(self, pref_code: int) -> float:
        """
        Convert preference code to preference value.
        
        Args:
            pref_code: Preference code from JSON
            
        Returns:
            Preference value for XML
        """
        # Use the preferences mapping from JSON if available
        preferences = self.json_data.get("preferences", {})
        
        # Default mapping if not found
        pref_map = {
            -3: -100.0,  # required
            -2: -20.0,   # strongly preferred
            -1: -10.0,   # preferred
            0: 0.0,      # neutral
            1: 10.0,     # discouraged
            2: 20.0,     # strongly discouraged
            3: 100.0,    # prohibited
            4: 1000.0    # not available
        }
        
        return float(pref_map.get(pref_code, 0.0))
    
    def _process_classes(self):
        """Process classes data and add to XML"""
        classes_data = self.json_data.get("classes", {})
        if not classes_data:
            # Create at least one dummy class if no classes are provided
            classes_elem = ET.SubElement(self.root, "classes")
            class_elem = ET.SubElement(classes_elem, "class")
            class_elem.set("id", "1")
            class_elem.set("offering", "1")
            class_elem.set("config", "1")
            class_elem.set("committed", "false")
            class_elem.set("subpart", "1")
            class_elem.set("classLimit", "30")
            class_elem.set("scheduler", "1")
            class_elem.set("dates", "1" * 288)
            return
            
        classes_elem = ET.SubElement(self.root, "classes")
        
        # Default dates pattern - all 1's for 288 days (full semester)
        default_dates = "1" * 288
        
        # Skip the description field
        scheduler_id = 1
        for class_id, class_info in classes_data.items():
            if class_id == "description":
                continue
                
            # Ensure numeric class ID
            numeric_class_id = self.ensure_numeric_id(class_id)
                
            class_elem = ET.SubElement(classes_elem, "class")
            class_elem.set("id", str(numeric_class_id))
            class_elem.set("offering", str(numeric_class_id))
            class_elem.set("config", str(numeric_class_id))
            class_elem.set("committed", "false")
            class_elem.set("subpart", str(numeric_class_id))
            class_elem.set("classLimit", str(class_info.get("capacity", 30)))
            class_elem.set("scheduler", str(scheduler_id))
            
            # Add dates attribute (required)
            class_elem.set("dates", default_dates)
            
            # Add instructor
            teacher = class_info.get("teacher")
            if teacher:
                instructor_elem = ET.SubElement(class_elem, "instructor")
                # Ensure numeric teacher ID
                numeric_teacher_id = self.ensure_numeric_id(teacher)
                instructor_elem.set("id", str(numeric_teacher_id))
            else:
                # Add a default instructor if none provided
                instructor_elem = ET.SubElement(class_elem, "instructor")
                instructor_elem.set("id", str(numeric_class_id + 1))
            
            # Add room preferences
            self._add_room_preferences(class_elem)
            
            # Add time preferences based on teacher availability
            self._add_time_preferences(class_elem, teacher, class_info.get("slots", 2))
            
            scheduler_id += 1
    
    def _add_room_preferences(self, class_elem: ET.Element):
        """
        Add room preferences to a class element.
        
        Args:
            class_elem: The class XML element to add room preferences to
        """
        rooms_data = self.json_data.get("rooms", {})
        ignore_capacity = self.json_data.get("constraints", {}).get("ignoreClassCapacity", {}).get("value", False)
        
        class_capacity = int(class_elem.get("classLimit", 0))
        
        # Ensure at least one room preference is added
        room_added = False
        
        for room_id, capacity in rooms_data.items():
            if room_id == "description":
                continue
                
            # Skip rooms that are too small unless ignoreClassCapacity is true
            if not ignore_capacity and int(capacity) < class_capacity:
                continue
                
            # Ensure numeric room ID
            numeric_room_id = self.ensure_numeric_id(room_id)
                
            room_elem = ET.SubElement(class_elem, "room")
            room_elem.set("id", str(numeric_room_id))
            room_elem.set("pref", "0")  # Neutral preference by default
            room_added = True
        
        # If no rooms were added, add a default one
        if not room_added:
            first_room_id = next((self.ensure_numeric_id(room_id) for room_id in rooms_data.keys() if room_id != "description"), 1)
            room_elem = ET.SubElement(class_elem, "room")
            room_elem.set("id", str(first_room_id))
            room_elem.set("pref", "0")
    
    def _add_time_preferences(self, class_elem: ET.Element, teacher: str, required_slots: int):
        """
        Add time preferences to a class element based on teacher availability.
        
        Args:
            class_elem: The class XML element to add time preferences to
            teacher: Teacher name
            required_slots: Number of time slots required for this class
        """
        time_slots = self.json_data.get("timeSlots", {})
        teacher_prefs = self.json_data.get("teachers", {}).get(teacher, {})
        
        # Get all days time slots
        all_slots = time_slots.get("allDays", [])
        
        # If no time slots are provided, add some default ones
        if not all_slots:
            # Default time preferences - assuming 6 hours in a day (18 slots of 20 minutes each)
            default_times = [
                ("0100000", 93, 18),  # Monday morning
                ("0100000", 111, 18), # Monday mid-morning
                ("0100000", 129, 18), # Monday noon
                ("0010000", 93, 18),  # Tuesday morning
                ("0010000", 111, 18), # Tuesday mid-morning
                ("0010000", 129, 18)  # Tuesday noon
            ]
            
            # Add default times
            for days, start, length in default_times:
                time_elem = ET.SubElement(class_elem, "time")
                time_elem.set("days", days)
                time_elem.set("start", str(start))
                time_elem.set("length", str(length))
                time_elem.set("pref", "0.0")
                time_elem.set("breakTime", "10")
            
            return
        
        # Flag to track if we've added at least one time preference
        time_added = False
        
        # Process each day
        for day_name, day_index in self.day_map.items():
            # Get teacher preferences for this day
            day_prefs = teacher_prefs.get(day_name, [0] * len(all_slots))
            
            # Process each time slot
            for slot_index, time_str in enumerate(all_slots):
                # Skip if we don't have preference data for this slot
                if slot_index >= len(day_prefs):
                    continue
                    
                pref_code = day_prefs[slot_index]
                pref_value = self._get_preference_value(pref_code)
                
                # Skip not available time slots
                if pref_code == 4:  # not available
                    continue
                
                time_added = True
                start_slot, length = self._convert_time_to_slots(time_str)
                
                time_elem = ET.SubElement(class_elem, "time")
                time_elem.set("days", self._get_day_pattern(day_index))
                time_elem.set("start", str(start_slot))
                time_elem.set("length", str(length))
                time_elem.set("pref", str(pref_value))
                # Add breakTime attribute (required for some solvers)
                time_elem.set("breakTime", "10")
        
        # If no time preferences were added, add some default ones
        if not time_added:
            # Default time preferences
            default_times = [
                ("0100000", 93, 18),  # Monday morning
                ("0100000", 111, 18), # Monday mid-morning
                ("0100000", 129, 18), # Monday noon
                ("0010000", 93, 18),  # Tuesday morning
                ("0010000", 111, 18), # Tuesday mid-morning
                ("0010000", 129, 18)  # Tuesday noon
            ]
            
            # Add default times
            for days, start, length in default_times:
                time_elem = ET.SubElement(class_elem, "time")
                time_elem.set("days", days)
                time_elem.set("start", str(start))
                time_elem.set("length", str(length))
                time_elem.set("pref", "0.0")
                time_elem.set("breakTime", "10")
    
    def _add_mutually_exclusive_constraints(self, group_constraints_elem: ET.Element):
        """
        Add mutually exclusive class constraints to the group constraints element.
        
        Args:
            group_constraints_elem: The group constraints XML element
        """
        mutually_exclusive = self.json_data.get("mutuallyExclusive", {})
        pairs = mutually_exclusive.get("pairs", [])
        
        for pair in pairs:
            if len(pair) != 2:
                continue
                
            # Ensure numeric class IDs
            numeric_class_id1 = self.ensure_numeric_id(pair[0])
            numeric_class_id2 = self.ensure_numeric_id(pair[1])
            
            # Create DIFF_TIME constraint
            constraint_elem = ET.SubElement(group_constraints_elem, "constraint")
            constraint_elem.set("id", str(self.constraint_id_counter))
            constraint_elem.set("type", "DIFF_TIME")
            constraint_elem.set("pref", "R")  # Required
            
            # Add classes to constraint
            class_elem1 = ET.SubElement(constraint_elem, "class")
            class_elem1.set("id", str(numeric_class_id1))
            
            class_elem2 = ET.SubElement(constraint_elem, "class")
            class_elem2.set("id", str(numeric_class_id2))
            
            self.constraint_id_counter += 1


def main():
    """Main function to parse arguments and run the converter"""
    parser = argparse.ArgumentParser(description='Convert JSON timetabling data to XML format')
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument('-o', '--output', help='Output XML file path (default: stdout)')
    
    args = parser.parse_args()
    
    try:
        # Read JSON input
        with open(args.input_file, 'r') as f:
            json_data = json.load(f)
        
        # Convert to XML
        converter = JSONtoXMLConverter(json_data)
        xml_output = converter.convert()
        
        # Write output
        if args.output:
            with open(args.output, 'w') as f:
                f.write(xml_output)
        else:
            print(xml_output)
            
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
