import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime
import re
from collections import defaultdict # Needed for grouping classes

class JSONtoXMLConverter:
    """
    Converts JSON to UniTime XML, strictly following the user-provided
    research report specification (v2).
    """
    # --- Constants ---
    MINUTES_PER_SLOT = 5
    SLOTS_PER_DAY = (24 * 60) // MINUTES_PER_SLOT # 288
    NR_DAYS = 7 # Use standard 7-day week
    DAY_MAP_STD = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    # Assume term length for 'dates' attribute (e.g., 16 weeks)
    TERM_LENGTH_DAYS = 16 * 7 # 112 days

    def __init__(self, json_data):
        """
        Initializes the converter with JSON data.
        """
        if isinstance(json_data, str):
            self.data = json.loads(json_data)
        elif isinstance(json_data, dict):
            self.data = json_data
        else:
            raise TypeError("json_data must be a dictionary or a JSON string")

        # Extract data sections
        self.general = self.data.get('general', {})
        self.preferences = self.data.get('preferences', {})
        self.rooms_data = self.data.get('rooms', {})
        self.classes_data = self.data.get('classes', {})
        self.instructors_data = self.data.get('instructors', {})
        self.constraints_data = self.data.get('constraints', {})
        self.mutually_exclusive_data = self.data.get('mutuallyExclusive', {})
        self.time_slots_data = self.data.get('timeSlots', {})

        # Use standard day map
        self.day_map = self.DAY_MAP_STD
        self.nr_days = self.NR_DAYS

        self._setup_time_slot_mapping()
        self._setup_id_generators()
        # Store current time based on context provided in user prompt
        # "Current time is Tuesday, April 15, 2025 at 3:15:23 PM EDT."
        # Format: "Tue Apr 15 15:15:23 EDT 2025"
        self.creation_timestamp = "Tue Apr 15 15:15:23 EDT 2025" # From context


    def _parse_time_range(self, time_range_str):
        """Parses HH:MM-HH:MM into start/end minutes from midnight."""
        match = re.match(r'(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})', time_range_str)
        if not match: raise ValueError(f"Invalid time range format: {time_range_str}")
        h1, m1, h2, m2 = map(int, match.groups())
        start_min = h1 * 60 + m1
        end_min = h2 * 60 + m2
        if end_min <= start_min: end_min = start_min + self.MINUTES_PER_SLOT
        return start_min, end_min

    def _setup_time_slot_mapping(self):
        """Creates mapping from logical JSON slot index (0-5) to base slots."""
        self.logical_slot_map = {}
        logical_slots_ranges = self.time_slots_data.get('allDays', [])
        if not logical_slots_ranges:
             print("Warning: No time slots defined in JSON 'timeSlots.allDays'.")
             return
        for i, time_range in enumerate(logical_slots_ranges):
            try:
                start_min, end_min = self._parse_time_range(time_range)
                start_slot = start_min // self.MINUTES_PER_SLOT
                length_slots = max(1, (end_min - start_min) // self.MINUTES_PER_SLOT)
                self.logical_slot_map[i] = {'start': start_slot, 'length': length_slots}
            except ValueError as e:
                print(f"Warning: Could not parse time range '{time_range}'. Skipping. Error: {e}")

    def _setup_id_generators(self):
        """Initializes mappings and counters for generating numeric IDs."""
        # Separate maps for different ID types as per XML structure
        self.room_name_to_id = {}
        self.offering_name_to_id = {}
        self.config_name_to_id = {}
        self.subpart_name_to_id = {}
        self.instructor_name_to_id = {}
        self.class_meeting_ids = [] # Store generated numeric class IDs

        # Counters
        self.next_room_id_counter = 1
        self.next_offering_id_counter = 1
        self.next_config_id_counter = 1
        self.next_subpart_id_counter = 1
        self.next_instructor_id_counter = 1
        self.next_class_meeting_id_counter = 1
        self.next_constraint_id_counter = 1


    def _get_mapped_id(self, name, id_map, counter_attr):
        """Gets or creates a sequential numeric ID for a given name."""
        # Use simple sequential IDs as implied by report for rooms/classes etc.
        hashable_name = str(name)
        if hashable_name not in id_map:
            current_id = getattr(self, counter_attr)
            id_map[hashable_name] = current_id
            setattr(self, counter_attr, current_id + 1)
        return id_map[hashable_name]

    def _create_day_code(self, days_list):
        """Creates a 7-bit binary string for days based on Mon=0..Sun=6."""
        code = ['0'] * self.NR_DAYS
        for day_name in days_list:
            if day_name in self.day_map: code[self.day_map[day_name]] = '1'
        return "".join(code)

    def _get_preference_code(self, level_name):
        """Gets the single character preference code."""
        num_val = self.preferences.get(level_name, 0)
        pref_code_map = { -3: 'R', -2: '-2', -1: '-1', 0: '0', 1: '1', 2: '2', 3: 'P', 4: 'X' }
        # Report implies using numeric string for non-required/prohibited? Let's use standard codes
        # Ensure we return '4' for notAvailable, not 'X', based on report text
        if level_name == "notAvailable": return '4'
        return pref_code_map.get(num_val, str(num_val))

    def convert(self):
        """
        Performs the conversion following the research report specification.

        Returns:
            str: A pretty-printed XML string representing the timetabling problem.
        """
        # --- Root Element Configuration (Report Spec) ---
        academic_session = self.general.get("academic_session", "YYYYXXX")
        year_str = str(self.general.get("year", "")) # Get year
        root = ET.Element("timetable", version="2.4",
                          initiative="custom", # Default from report
                          term=academic_session,
                          year=year_str, # Added year attribute
                          nrDays=str(self.NR_DAYS),
                          slotsPerDay=str(self.SLOTS_PER_DAY),
                          created=self.creation_timestamp) # Use specific timestamp

        # --- Rooms Section (Report Spec) ---
        rooms_element = ET.SubElement(root, "rooms")
        room_id_map = {} # Local map for this conversion: json_name -> numeric_id
        for room_name in self.rooms_data:
             if room_name != "description":
                 # Use dedicated function to get sequential ID
                 room_id_map[room_name] = self._get_mapped_id(room_name, self.room_name_to_id, 'next_room_id_counter')

        for room_name, capacity in self.rooms_data.items():
            if room_name == "description": continue
            numeric_room_id = room_id_map[room_name]
            ET.SubElement(rooms_element, "room",
                          id=str(numeric_room_id),
                          capacity=str(capacity),
                          constraint="true", # Default from report
                          location="0,0") # Default from report

        # --- Classes Section (Report Spec) ---
        classes_element = ET.SubElement(root, "classes")
        # Store mappings for constraint generation
        offering_to_meetings = defaultdict(list)
        instructor_to_meetings = defaultdict(list)
        all_meeting_details = {} # numeric_meeting_id -> {instructor_id: num, offering_id: num}

        for class_name, details in self.classes_data.items():
            if class_name == "description": continue

            # Generate IDs for offering, config, subpart (one per JSON class_name)
            offering_id = self._get_mapped_id(class_name, self.offering_name_to_id, 'next_offering_id_counter')
            config_id = self._get_mapped_id(class_name, self.config_name_to_id, 'next_config_id_counter') # Assuming one config per offering
            subpart_id = self._get_mapped_id(class_name, self.subpart_name_to_id, 'next_subpart_id_counter') # Assuming one subpart

            num_slots = details.get('slots', 1)
            instructor_name = details.get('instructor')
            class_limit = details.get('capacity', 0)
            numeric_instructor_id = None
            if instructor_name:
                numeric_instructor_id = self._get_mapped_id(instructor_name, self.instructor_name_to_id, 'next_instructor_id_counter')

            # Create class meetings
            for i in range(num_slots):
                numeric_meeting_id = self.next_class_meeting_id_counter
                self.next_class_meeting_id_counter += 1
                self.class_meeting_ids.append(numeric_meeting_id) # Store globally if needed elsewhere

                offering_to_meetings[offering_id].append(numeric_meeting_id)
                if numeric_instructor_id is not None:
                    instructor_to_meetings[numeric_instructor_id].append(numeric_meeting_id)
                all_meeting_details[numeric_meeting_id] = {'instructor_id': numeric_instructor_id, 'offering_id': offering_id}


                # Create <class> element
                class_elem = ET.SubElement(classes_element, "class",
                                          id=str(numeric_meeting_id),
                                          offering=str(offering_id),
                                          config=str(config_id),
                                          subpart=str(subpart_id),
                                          scheduler="-1", # Keep null-like ref
                                          department=str(offering_id), # Use offering ID
                                          committed="false", # Default from report
                                          classLimit=str(class_limit),
                                          nrRooms="1", # Default from report
                                          dates="1"*self.TERM_LENGTH_DAYS # Default from report
                                          )

                if numeric_instructor_id is not None:
                    ET.SubElement(class_elem, "instructor", id=str(numeric_instructor_id))

                # Add Time Preferences (Report Spec: iterate all 7 days)
                if instructor_name and instructor_name in self.instructors_data:
                     instructor_day_prefs = self.instructors_data[instructor_name]
                     # Iterate Mon-Sun (0-6)
                     for day_index_std in range(self.NR_DAYS):
                         # Find corresponding day name for JSON lookup
                         day_name_json = None
                         for name, index in self.DAY_MAP_STD.items():
                              if index == day_index_std:
                                   day_name_json = name
                                   break

                         day_code = ['0'] * self.NR_DAYS; day_code[day_index_std] = '1'; day_code_str = "".join(day_code)

                         # Get prefs for this day from JSON, default to unavailable if day missing
                         logical_day_prefs = instructor_day_prefs.get(day_name_json) if day_name_json else None

                         # Iterate through LOGICAL slots (0-5) defined by the JSON structure
                         for logical_slot_index in range(len(self.logical_slot_map)):
                             pref_value = 4 # Default to notAvailable
                             if logical_day_prefs and isinstance(logical_day_prefs, list) and logical_slot_index < len(logical_day_prefs):
                                 pref_value = logical_day_prefs[logical_slot_index]
                             else:
                                 # Handle cases where day is missing or prefs list is wrong length - default pref=4
                                 pref_value = self.preferences.get("notAvailable", 4)


                             # Use numeric preference value directly (report says treat as string, but numeric seems common)
                             # Only add if *not* unavailable, otherwise implicitly unavailable
                             if pref_value != self.preferences.get("notAvailable", 4):
                                 slot_info = self.logical_slot_map.get(logical_slot_index)
                                 if slot_info:
                                      ET.SubElement(class_elem, "time",
                                                   days=day_code_str,
                                                   start=str(slot_info['start']),
                                                   length=str(slot_info['length']),
                                                   pref=str(pref_value), # Use numeric pref
                                                   breakTime="0") # Default from report

                # Add Room Preferences (Filtered by Capacity - Report Spec)
                ignore_cap = self.constraints_data.get('ignoreClassCapacity', {}).get('value', False)
                room_constraint_flag = "false" if ignore_cap else "true" # For the class attr later? No, room pref

                for room_name, capacity in self.rooms_data.items():
                     if room_name == "description": continue
                     numeric_room_id = room_id_map[room_name]
                     # Only add room if capacity is sufficient (respect ignoreClassCapacity=false)
                     if ignore_cap or capacity >= class_limit:
                         ET.SubElement(class_elem, "room", id=str(numeric_room_id),
                                      pref=str(self.preferences.get("neutral", 0)), # Neutral pref
                                      constraint=room_constraint_flag) # Still needed? Sample room has constraint attr


        # --- Add EMPTY students section ---
        ET.SubElement(root, "students")

        # --- Add Group Constraints (Report Spec) ---
        constraints_elem = ET.SubElement(root, "groupConstraints")

        # Apply constraints based on flags
        if self.constraints_data.get("sameRooms", {}).get("value", False):
            for offering_id, meeting_ids in offering_to_meetings.items():
                 if len(meeting_ids) > 1:
                    constraint_id = self._get_mapped_id(f"constraint_{self.next_constraint_id_counter}", {}, 'next_constraint_id_counter')
                    constraint = ET.SubElement(constraints_elem, "constraint", id=str(constraint_id), type="SAME_ROOM", pref="R")
                    for meeting_id in meeting_ids: ET.SubElement(constraint, "class", id=str(meeting_id))

        if self.constraints_data.get("sameSlots", {}).get("value", False):
            for offering_id, meeting_ids in offering_to_meetings.items():
                 if len(meeting_ids) > 1:
                    constraint_id = self._get_mapped_id(f"constraint_{self.next_constraint_id_counter}", {}, 'next_constraint_id_counter')
                    constraint = ET.SubElement(constraints_elem, "constraint", id=str(constraint_id), type="SAME_START", pref="R")
                    for meeting_id in meeting_ids: ET.SubElement(constraint, "class", id=str(meeting_id))

        if self.constraints_data.get("maxOneSlotInDay", {}).get("value", False):
             for offering_id, meeting_ids in offering_to_meetings.items():
                 if len(meeting_ids) > 1:
                    # Apply pairwise prohibited SAME_DAYS
                    for i in range(len(meeting_ids)):
                        for j in range(i + 1, len(meeting_ids)):
                            m1_id = meeting_ids[i]
                            m2_id = meeting_ids[j]
                            constraint_id = self._get_mapped_id(f"constraint_{self.next_constraint_id_counter}", {}, 'next_constraint_id_counter')
                            constraint = ET.SubElement(constraints_elem, "constraint", id=str(constraint_id), type="SAME_DAYS", pref="P")
                            ET.SubElement(constraint, "class", id=str(m1_id))
                            ET.SubElement(constraint, "class", id=str(m2_id))


        if self.constraints_data.get("instructorJustOneClassAtSlot", {}).get("value", False):
             for instructor_id, meeting_ids in instructor_to_meetings.items():
                 if len(meeting_ids) > 1:
                    # Apply pairwise required DIFF_TIME
                    for i in range(len(meeting_ids)):
                        for j in range(i + 1, len(meeting_ids)):
                            m1_id = meeting_ids[i]
                            m2_id = meeting_ids[j]
                            constraint_id = self._get_mapped_id(f"constraint_{self.next_constraint_id_counter}", {}, 'next_constraint_id_counter')
                            constraint = ET.SubElement(constraints_elem, "constraint", id=str(constraint_id), type="DIFF_TIME", pref="R")
                            ET.SubElement(constraint, "class", id=str(m1_id))
                            ET.SubElement(constraint, "class", id=str(m2_id))

        # Mutually Exclusive Pairs
        if "pairs" in self.mutually_exclusive_data:
            for pair in self.mutually_exclusive_data["pairs"]:
                if len(pair) == 2:
                    class1_name, class2_name = pair
                    # Get the offering IDs for these names
                    offering1_id = self.offering_name_to_id.get(class1_name)
                    offering2_id = self.offering_name_to_id.get(class2_name)

                    if offering1_id is not None and offering2_id is not None:
                        class1_meeting_ids = offering_to_meetings.get(offering1_id, [])
                        class2_meeting_ids = offering_to_meetings.get(offering2_id, [])
                        # Apply pairwise required DIFF_TIME between meetings of the two offerings
                        for m1_id_num in class1_meeting_ids:
                            for m2_id_num in class2_meeting_ids:
                                 constraint_id = self._get_mapped_id(f"constraint_{self.next_constraint_id_counter}", {}, 'next_constraint_id_counter')
                                 constraint = ET.SubElement(constraints_elem, "constraint", id=str(constraint_id), type="DIFF_TIME", pref="R") # Changed pref to R per report
                                 ET.SubElement(constraint, "class", id=str(m1_id_num))
                                 ET.SubElement(constraint, "class", id=str(m2_id_num))

        # --- Generate XML String ---
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string.decode('utf-8'))
        return reparsed.toprettyxml(indent="  ")
    
    