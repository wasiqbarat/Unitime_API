#!/usr/bin/env python3
"""
JSON to XML Converter for Timetabling Problem

This script converts a minimal JSON timetabling problem definition to the XML format
required by the UniTime CPSolver for course timetabling.

Usage:
    python json_to_xml_converter.py input.json output.xml

"""

import json
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
import sys
import datetime
import argparse
import re

def create_element(parent, tag, text=None, **attrs):
    """Helper function to create an XML element with attributes and text."""
    element = ET.SubElement(parent, tag, **attrs)
    if text is not None:
        element.text = str(text)
    return element

def format_days_string(days_list):
    """Convert a list of days to a binary string representation.
    
    Example: ["Monday", "Wednesday", "Friday"] -> "1010100"
    """
    day_mapping = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }
    
    days_binary = ['0'] * 7
    for day in days_list:
        day_lower = day.lower()
        if day_lower in day_mapping:
            days_binary[day_mapping[day_lower]] = '1'
    
    return ''.join(days_binary)

def time_to_slots(time_str):
    """Convert a time string (HH:MM) to slot number.
    
    With 288 slots per day (5-minute slots), each hour has 12 slots.
    """
    hours, minutes = map(int, time_str.split(':'))
    # Calculate minutes since midnight
    minutes_since_midnight = hours * 60 + minutes
    # Convert to slot number (assuming 5-minute slots)
    slot = minutes_since_midnight // 5
    return slot

def convert_json_to_xml(json_data):
    """Convert JSON timetabling data to XML format for UniTime CPSolver."""
    
    # Create ID mappings for all entity types
    # Use index+1 as numeric ID (ensuring no zeros)
    room_id_mapping = {}
    for i, room_data in enumerate(json_data.get("rooms", [])):
        room_id_mapping[room_data["id"]] = str(i+1)
    
    instructor_id_mapping = {}
    for i, instructor_data in enumerate(json_data.get("instructors", [])):
        instructor_id_mapping[instructor_data["id"]] = str(i+1)
    
    # Also map any instructors mentioned in classes but not in instructors section
    instructor_names = set()
    for class_data in json_data.get("classes", []):
        if "instructor" in class_data:
            instructor_names.add(class_data["instructor"])
    
    # Add any missing instructors to the mapping
    for i, instructor_name in enumerate(instructor_names):
        if instructor_name not in instructor_id_mapping:
            instructor_id_mapping[instructor_name] = str(i+101)
    
    class_id_mapping = {}
    for i, class_data in enumerate(json_data.get("classes", [])):
        class_id_mapping[class_data["id"]] = str(i+1)
    
    # Create root element
    root = ET.Element("timetable")
    root.set("version", "2.4")
    root.set("campus", "CAMPUS")
    root.set("term", "1")
    root.set("year", "2023")
    root.set("created", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set("nrDays", "5")
    root.set("slotsPerDay", "288")
    root.set("type", "course")  # Required field
    root.set("studWeights", "false")  # Required field
    root.set("instrWeights", "false")  # Required field
    root.set("diffRoomWeights", "false")  # Required field
    root.set("diffTimeWeights", "false")  # Required field
    root.set("longerWeights", "false")  # Required field
    root.set("deptBalancing", "false")  # Required field
    root.set("perturbations", "false")  # Required field
    
    # Process travel times (required element with entries)
    travel_times_element = create_element(root, "traveltimes")
    # Add a default travel time to ensure element isn't empty
    create_element(travel_times_element, "travel", fromBldId="1", toBldId="1", time="0")
    
    # Process instructors section
    instructors_element = create_element(root, "instructors")
    for i, instructor_data in enumerate(json_data.get("instructors", [])):
        instructor_id = instructor_id_mapping[instructor_data["id"]]
        create_element(instructors_element, "instructor", 
                       id=instructor_id, 
                       externalId=instructor_data["id"],
                       name=instructor_data.get("name", f"Instructor {instructor_id}"))
    
    # Add any missing instructors from classes
    for instructor_name in instructor_names:
        if instructor_name not in instructor_id_mapping:
            continue
        instructor_id = instructor_id_mapping[instructor_name]
        create_element(instructors_element, "instructor", 
                      id=instructor_id, 
                      externalId=instructor_name,
                      name=instructor_name)
    
    # Process rooms
    rooms_element = create_element(root, "rooms")
    for room_data in json_data.get("rooms", []):
        room_id = room_id_mapping[room_data["id"]]
        create_element(rooms_element, "room", 
                      id=room_id, 
                      externalId=room_data["id"],
                      capacity=str(room_data["capacity"]),
                      building="1",
                      constraint="1")
    
    # Add departments section
    departments_element = create_element(root, "departments")
    create_element(departments_element, "department", 
                  id="1", 
                  externalId="DEPT1",
                  name="Department 1",
                  deptCode="DEPT1")
    
    # Add instructional types section (required by solver)
    itypes_element = create_element(root, "instructionalTypes")
    create_element(itypes_element, "instructionalType", 
                  id="1", 
                  reference="Lec", 
                  name="Lecture",
                  abbreviation="Lec", 
                  type="normal",
                  organized="true")
    
    create_element(itypes_element, "instructionalType", 
                  id="2", 
                  reference="Rec", 
                  name="Recitation",
                  abbreviation="Rec", 
                  type="normal",
                  organized="true")
    
    # Add subjects section
    subjects_element = create_element(root, "subjects")
    create_element(subjects_element, "subject", 
                  id="1", 
                  externalId="SUBJ1",
                  name="Subject 1")
    
    # Add academic areas section (required by solver)
    academic_areas = create_element(root, "academicAreas")
    create_element(academic_areas, "academicArea", id="1", abbv="COMP", name="Computer Science")
    
    # Add position majors section (required by solver)
    pos_majors = create_element(root, "posMajors")
    create_element(pos_majors, "posMajor", id="1", code="CS", name="Computer Science", academicAreaId="1")
    
    # Add student groups section (required by solver)
    student_groups = create_element(root, "studentGroups")
    create_element(student_groups, "studentGroup", id="1", code="CSG", name="CS Group", type="MAJOR")
    
    # Add date patterns section (required by solver)
    date_patterns = create_element(root, "datePatterns")
    create_element(date_patterns, "datePattern", 
                  id="1", 
                  name="Full Term", 
                  pattern="111111111111111", 
                  type="Standard",
                  visible="true")
    
    # Add offerings section (with config and subpart)
    offerings_element = create_element(root, "offerings")
    
    # Group classes by course (if available)
    courses = {}
    for class_data in json_data.get("classes", []):
        course = class_data.get("course", "DEFAULT")
        if course not in courses:
            courses[course] = []
        courses[course].append(class_data)
    
    # Create offerings for each course
    for i, (course, classes) in enumerate(courses.items()):
        offering_id = str(i+1)
        offering_element = create_element(offerings_element, "offering", 
                                         id=offering_id, 
                                         name=course)
        
        # Add course element (required by solver)
        course_element = create_element(offering_element, "course", 
                                      id=offering_id,
                                      courseNbr=f"COURSE{offering_id}",
                                      subjectId="1",
                                      title=course,
                                      schedBookOnly="false")
        
        # Add courseCredit element (required by solver)
        course_credit = create_element(course_element, "courseCredit", 
                                     creditType="standard",
                                     creditUnitType="units",
                                     creditFormat="fixedUnit",
                                     fixedCredit="3")
        
        # Add config for this offering
        config_element = create_element(offering_element, "config", 
                                       id=offering_id, 
                                       name=f"Config {offering_id}",
                                       limit="100")
        
        # Add subpart for lectures (required structure)
        subpart_element = create_element(config_element, "subpart", 
                                        id=offering_id, 
                                        itype="1",
                                        name="Lecture", 
                                        type="lec",
                                        suffix="Lec",
                                        minPerWeek="150")
        
        # Add itype reference (required by solver)
        create_element(subpart_element, "itype", id="1", name="Lecture", abbreviation="Lec")
        
        # Add sections for each class
        for j, class_data in enumerate(classes):
            class_id = class_id_mapping[class_data["id"]]
            section_id = f"{offering_id}{j+1}"
            create_element(subpart_element, "section", 
                          id=section_id, 
                          name=f"Section {section_id}",
                          limit=str(class_data.get("students", 30)),
                          classId=class_id,
                          scheduleNote="auto-generated")
    
    # Add time patterns section
    time_patterns_element = create_element(root, "timePatterns")
    
    # Add default time patterns
    create_element(time_patterns_element, "timePattern",
                  id="1",
                  name="1h MWF",
                  nrMeetings="3",
                  minsPerMeeting="50",
                  days="1010100",
                  slotsPerMeeting="10",
                  breakTime="0",
                  times="90,102,114,126,138,150,162,174,186,198,210")
    
    create_element(time_patterns_element, "timePattern",
                  id="2",
                  name="1.5h TTh",
                  nrMeetings="2",
                  minsPerMeeting="75",
                  days="0101000",
                  slotsPerMeeting="15",
                  breakTime="0",
                  times="90,102,114,126,138,150,162,174,186,198,210")
    
    # Process classes
    classes_element = create_element(root, "classes")
    for class_data in json_data.get("classes", []):
        class_id = class_id_mapping[class_data["id"]]
        
        # Find which offering and subpart this class belongs to
        course = class_data.get("course", "DEFAULT")
        offering_id = None
        for i, (c, _) in enumerate(courses.items()):
            if c == course:
                offering_id = str(i+1)
                break
        
        if not offering_id:
            offering_id = "1"
        
        # Create class element with all required attributes
        class_element = create_element(classes_element, "class", 
                                      id=class_id, 
                                      classId=class_id,  # Duplicate ID as classId is expected
                                      departmentClassId=class_id,  # Needed by solver
                                      subjectId="1",
                                      instructorId="1", # Default instructor reference
                                      courseId=offering_id,  # Link to course
                                      schedulingSubpartId=offering_id,  # Link to subpart
                                      studentSchedulingEnabled="true",
                                      isCommitted="false",
                                      nrRooms="1",
                                      timetable="false",
                                      roomNames="",
                                      externalId=class_data["id"],
                                      managingDept="1",  # Link to department
                                      classLimit=str(class_data.get("students", 30)),
                                      snapshotLimit="0")
        
        # Add date pattern
        date_pattern = create_element(class_element, "datePattern", 
                                     id="1", 
                                     name="Full Term", 
                                     type="Standard", 
                                     visible="true")
        
        # Add instructor if specified
        if "instructor" in class_data:
            instructor_id = instructor_id_mapping[class_data["instructor"]]
            create_element(class_element, "instructor", id=instructor_id)
        
        # Add time preferences with direct time elements (required structure for solver)
        time_prefs = create_element(class_element, "timePreferences")
        
        # Add proper time preferences structure
        timePattern = create_element(time_prefs, "timePattern", 
                                    name="Default", 
                                    nrMeetings="3", 
                                    minsPerMeeting="50",
                                    type="Standard",
                                    breakTime="0")  # Add explicit breakTime
        
        # Add preference entries with explicit values - use format expected by solver
        # Create 24 hours x 7 days grid with all preferences set to 0
        for day in range(7):
            for hour in range(24):
                slot = hour * 12  # 12 five-minute slots per hour
                create_element(timePattern, "pref", 
                             day=str(day), 
                             slot=str(slot), 
                             pref="0",
                             prefLevel="0")  # Add explicit prefLevel
        
        # Add direct time elements to the class (required by solver)
        # Monday, Wednesday, Friday slots
        create_element(class_element, "time", 
                      days="1010100",  # MWF
                      start="90",      # 7:30am
                      length="12",     # 60 minutes (12 5-minute slots)
                      timePattern="1",
                      datePatternId="1",
                      breakTime="0",
                      pref="0")  # Add explicit pref
        
        # Tuesday, Thursday slots
        create_element(class_element, "time", 
                      days="0101000",  # TTh
                      start="90",      # 7:30am
                      length="18",     # 90 minutes (18 5-minute slots)
                      timePattern="2",
                      datePatternId="1",
                      breakTime="0",
                      pref="0")  # Add explicit pref
        
        # Add room groups (required by solver)
        roomGroups = create_element(class_element, "roomGroups")
        create_element(roomGroups, "roomGroup", id="1", name="Default")
        
        # Add room preferences (required for solver)
        room_prefs = create_element(class_element, "roomPreferences")
        for room_data in json_data.get("rooms", []):
            room_id = room_id_mapping[room_data["id"]]
            # Use "0" as a valid string for preference (ensure it's not a null value)
            create_element(room_prefs, "room", id=room_id, pref="0")
    
    # Add distributions section (constraints between classes)
    distributions_element = create_element(root, "distributions")
    
    # Process mutually exclusive constraints
    if "distribution_constraints" in json_data and "mutually_exclusive" in json_data["distribution_constraints"]:
        for i, class_group in enumerate(json_data["distribution_constraints"]["mutually_exclusive"]):
            distribution = create_element(distributions_element, "distribution", 
                                         id=str(i+1), 
                                         type="DIFF_TIME",
                                         required="true",  
                                         pref="1.0",
                                         prefLevel="Required")  # Add explicit prefLevel
            
            for class_id in class_group:
                numeric_id = class_id_mapping.get(class_id, "1")
                create_element(distribution, "class", id=numeric_id)
    
    # Process back-to-back constraints
    if "distribution_constraints" in json_data and "back_to_back" in json_data["distribution_constraints"]:
        for i, class_group in enumerate(json_data["distribution_constraints"]["back_to_back"]):
            distribution = create_element(distributions_element, "distribution", 
                                         id=str(i+101), 
                                         type="BTB_TIME",
                                         required="true",
                                         pref="1.0",
                                         prefLevel="Required")  # Add explicit prefLevel
            
            for class_id in class_group:
                numeric_id = class_id_mapping.get(class_id, "1")
                create_element(distribution, "class", id=numeric_id)
    
    # Add students section
    students_element = create_element(root, "students")
    for i, student_data in enumerate(json_data.get("students", [])):
        student_id = str(i+1)
        student_element = create_element(students_element, "student", 
                                        id=student_id, 
                                        firstName=f"Student{student_id}",
                                        lastName=f"User{student_id}",
                                        externalId=student_data.get("id", f"S{student_id}"),
                                        dummy="false",
                                        priority="0.1",
                                        minCredit="0",
                                        maxCredit="20",
                                        projectedCredit="0")
        
        # Add academic area to student (required by solver)
        acad_area = create_element(student_element, "academicArea", id="1")
        
        # Add major to student (required by solver)
        major = create_element(student_element, "major", id="1")
        
        # Add student group to student (required by solver)
        group = create_element(student_element, "group", id="1")
        
        # Add class references for each student
        for class_id in student_data.get("classes", []):
            numeric_id = class_id_mapping.get(class_id, "1")
            create_element(student_element, "class", id=numeric_id, weight="1.0")
    
    # If no students in data, add one default student
    if not json_data.get("students", []):
        student_element = create_element(students_element, "student", 
                                       id="1", 
                                       firstName="Default",
                                       lastName="Student",
                                       externalId="S1",
                                       dummy="false",
                                       priority="0.1",
                                       minCredit="0",
                                       maxCredit="20",
                                       projectedCredit="0")
        
        # Add academic area to default student
        acad_area = create_element(student_element, "academicArea", id="1")
        
        # Add major to default student
        major = create_element(student_element, "major", id="1")
        
        # Add student group to default student
        group = create_element(student_element, "group", id="1")
        
        # Add all classes to default student
        for class_id in class_id_mapping.values():
            create_element(student_element, "class", id=class_id, weight="1.0")
    
    # Add buildings section
    buildings_element = create_element(root, "buildings")
    create_element(buildings_element, "building", 
                  id="1", 
                  externalId="MAIN",
                  name="Main Building",
                  x="0", y="0")
    
    # Add solutions section
    solutions_element = create_element(root, "solutions")
    create_element(solutions_element, "solution", 
                  id="1",
                  commit="1", 
                  update="1", 
                  save="1")
    
    # Return the formatted XML string
    return ET.tostring(root, encoding='utf-8')

def prettify_xml(xml_string):
    """Format XML string to be more readable."""
    dom = minidom.parseString(xml_string)
    return dom.toprettyxml(indent="  ")

def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(description='Convert JSON timetabling data to XML format.')
    parser.add_argument('input_file', help='Input JSON file')
    parser.add_argument('output_file', help='Output XML file')
    
    args = parser.parse_args()
    
    try:
        # Read JSON data
        with open(args.input_file, 'r') as f:
            json_data = json.load(f)
        
        # Convert to XML
        xml_data = convert_json_to_xml(json_data)
        
        # Format XML
        pretty_xml = prettify_xml(xml_data)
        
        # Write to output file
        with open(args.output_file, 'w') as f:
            f.write(pretty_xml)
        
        print(f"Successfully converted {args.input_file} to {args.output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
