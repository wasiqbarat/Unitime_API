"""
Data models for the Unitime solver API integration.

This module defines Pydantic models that:
- Represent the structure of requests and responses
- Validate input data for solver operations
- Define the schema for course timetabling data
- Map between API models and Unitime solver formats

These models enable type safety and data validation throughout the application.
"""

# Import standard library modules
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

# Import Pydantic for data validation
from pydantic import BaseModel, Field

class SolverStatus(str, Enum):
    """Enum for the status of the solver process."""
    not_started = "not_started"
    started = "started"
    running = "running"
    completed = "completed"
    error = "error"  # Make sure error status is included
    stopped = "stopped"
    killed = "killed"
    not_running = "not_running"

class ProblemSubmission(BaseModel):
    """Model for submitting a new timetabling problem"""
    general: Dict[str, Any] = Field(..., description="General information about the problem")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Constraints for scheduling")
    timeSlots: Optional[Dict[str, Any]] = Field(None, description="Available time slots")
    preferences: Optional[Dict[str, Any]] = Field(None, description="Preferences for scheduling")
    rooms: Dict[str, Any] = Field(..., description="Available rooms with capacities")
    classes: Dict[str, Any] = Field(..., description="Classes to be scheduled")
    mutuallyExclusive: Optional[Dict[str, Any]] = Field(None, description="Classes that cannot be scheduled together")
    instructors: Optional[Dict[str, Any]] = Field(None, description="Instructor availability and preferences")
    name: Optional[str] = Field(None, description="Optional name for the problem")
    
    class Config:
        extra = "allow"  # Allow additional fields

class ProblemResponse(BaseModel):
    """Response model for problem submission"""
    problem_id: str = Field(..., description="Unique ID for the submitted problem")
    status: SolverStatus = Field(..., description="Current status of the solver")
    message: str = Field(..., description="Additional information about the problem submission")

class StatusRequest(BaseModel):
    """Request model for checking problem status"""
    problem_id: str = Field(..., description="ID of the problem to check")

class StatusResponse(BaseModel):
    """Response model for problem status"""
    problem_id: str = Field(..., description="ID of the checked problem")
    status: SolverStatus = Field(..., description="Current status of the solver")
    message: str = Field(..., description="Additional information about the problem status")
    solution_available: bool = Field(..., description="Whether a solution is available")
    debug_log: Optional[List[str]] = Field(None, description="Contents of the debug.log file as lines if available")
    
    class Config:
        """Configuration for the StatusResponse model"""
        json_encoders = {
            # Customize JSON encoding for certain types if needed
        }
        
        # This ensures that strings are not modified during serialization
        arbitrary_types_allowed = True

class XMLProblemSubmission(BaseModel):
    """Model for submitting a new timetabling problem directly as XML"""
    xml_content: str = Field(..., description="XML representation of the timetabling problem")
    name: Optional[str] = Field(None, description="Optional name for the problem")

# TODO: Define solver request models

# TODO: Define solver response models

# TODO: Define enums for solver statuses and configuration options 

# TODO: Define models for timetabling entities (courses, rooms, instructors, etc.)

# TODO: Define models for solver constraints and preferences
