"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class AuthCredentials(BaseModel):
    """Authentication credentials (HMAC or token)."""
    method: str  # 'hmac' or 'token'
    credentials: Dict[str, str]  # {public_key, private_key} or {auth_token}


class AuthResponse(BaseModel):
    """Response after authentication."""
    session_id: str
    status: str  # 'success' or 'error'
    message: str
    devices_count: Optional[int] = None


class DeviceInfo(BaseModel):
    """Information about a device/station."""
    device_id: int
    name: str
    device_name: str
    timezone: str
    last_communication: datetime
    available_sensors: List[str]


class DevicesListResponse(BaseModel):
    """Response containing user's devices."""
    session_id: str
    devices: List[DeviceInfo]
    total_count: int


class SensorData(BaseModel):
    """Sensor data with values and metadata."""
    sensor_name: str
    unit: str
    decimals: int
    dates: List[str]
    values: Dict[str, List[Any]]  # {avg: [...], max: [...], min: [...], ...}


class ChatRequest(BaseModel):
    """User chat message."""
    session_id: str
    user_message: str
    device_id: Optional[str] = None  # Alphanumeric device ID


class QueryResult(BaseModel):
    """Result from query processing."""
    sensor_data: Optional[List[SensorData]] = None
    formatted_text: str = ""
    query_params: Dict[str, Any] = {}
    table_data: Optional[Dict[str, Any]] = None  # Structured table data for UI
    licenses_data: Optional[Dict[str, Any]] = None  # Raw license data for grid display
    sensors_data: Optional[List[str]] = None  # Raw sensor list for grid display


class ChatResponse(BaseModel):
    """Response to chat query."""
    session_id: str
    bot_message: str
    query_result: Optional[QueryResult] = None
    error: Optional[str] = None


class SensorsListResponse(BaseModel):
    """Available sensors for a device."""
    device_id: int
    sensors: List[str]


class LogoutResponse(BaseModel):
    """Logout confirmation."""
    status: str
    message: str
