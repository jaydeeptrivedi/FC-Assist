"""FastAPI application for FC Assist chatbot."""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import sys
import os
import traceback
from typing import Optional, Dict, Any

from .schemas import (
    AuthCredentials, AuthResponse, DevicesListResponse, ChatRequest, ChatResponse,
    SensorsListResponse, LogoutResponse, QueryResult
)
from .auth import session_manager, HMACAuth, TokenAuth
from .api_client import FieldClimateClient
from .intent_parser import IntentParser, suggest_sensors


app = FastAPI(title="FC Assist Chatbot", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/verify", response_model=AuthResponse)
async def verify_credentials(request: AuthCredentials):
    """
    Verify user credentials and create session.
    
    Args:
        request: AuthCredentials with method and credentials
    
    Returns:
        AuthResponse with session_id and devices count
    """
    try:
        # Validate auth method
        if request.method not in ['hmac', 'token']:
            raise ValueError(f"Unknown auth method: {request.method}")
        
        # Create auth object
        if request.method == 'hmac':
            if 'public_key' not in request.credentials or 'private_key' not in request.credentials:
                raise ValueError("HMAC requires public_key and private_key")
            
            auth = HMACAuth(
                request.credentials['public_key'],
                request.credentials['private_key']
            )
        else:  # token
            if 'auth_token' not in request.credentials:
                raise ValueError("Token auth requires auth_token")
            
            auth = TokenAuth(request.credentials['auth_token'])
        
        # Test credentials by fetching user stations
        client = FieldClimateClient(auth)
        stations = client.get_user_stations()
        
        if not stations:
            raise ValueError("No stations found for user")
        
        # Create session
        session_id = session_manager.create_session(request.method, request.credentials)
        
        return AuthResponse(
            session_id=session_id,
            status="success",
            message="Authentication successful",
            devices_count=len(stations)
        )
    
    except Exception as e:
        error_msg = str(e)
        if "Authentication failed" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg
            )
        elif "subscription" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )


@app.get("/api/config/hmac-keys")
async def get_hmac_keys_from_env():
    """
    Get HMAC keys from environment variables if available.
    This allows frontend to auto-populate credentials from environment.
    
    Returns:
        Dict with public_key and private_key if available in environment
    
    Raises:
        HTTPException 404 if keys are not configured in environment
    """
    try:
        public_key = os.getenv('FC_PUBLIC_KEY')
        private_key = os.getenv('FC_PRIVATE_KEY')
        
        if not public_key or not private_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HMAC keys not configured in environment"
            )
        
        return {
            "public_key": public_key,
            "private_key": private_key
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving HMAC keys: {str(e)}"
        )


@app.get("/api/devices")
async def list_devices(session_id: str):
    """
    List user's accessible devices/stations.
    
    Args:
        session_id: Valid session ID
    
    Returns:
        List of devices with metadata
    """
    try:
        # Validate session
        auth = session_manager.get_session(session_id)
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Fetch stations
        client = FieldClimateClient(auth)
        stations = client.get_user_stations()
        
        devices = []
        for station in stations:
            try:
                # Get alphanumeric device ID from name.original
                device_id = station.get('name', {}).get('original')
                if not device_id:
                    print(f"[DEVICE PARSE ERROR] No alphanumeric ID found in station", file=sys.stderr)
                    continue
                
                device = {
                    "device_id": device_id,  # Alphanumeric ID (e.g., "0000011F")
                    "name": station.get('name', {}).get('custom', 'Unknown'),
                    "device_name": station.get('info', {}).get('device_name', ''),
                    "timezone": station.get('position', {}).get('timezoneCode', 'UTC') if station.get('position') else 'UTC',
                    "last_communication": station.get('dates', {}).get('last_communication', ''),
                    "available_sensors": _extract_sensor_names(station)
                }
                devices.append(device)
            except Exception as device_error:
                print(f"[DEVICE PARSE ERROR] Failed to parse station: {str(device_error)}", file=sys.stderr)
                print(f"[DEVICE PARSE ERROR] Station data: {station}", file=sys.stderr)
                # Skip this device and continue
                continue
        
        # Build response (convert to dict-compatible format)
        response_devices = []
        for device in devices:
            response_devices.append(device)
        
        return {
            "session_id": session_id,
            "devices": response_devices,
            "total_count": len(response_devices)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEVICES ERROR] {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching devices: {str(e)}"
        )


@app.get("/api/sensors")
async def get_sensors(session_id: str, device_id: int):
    """
    List available sensors for a device.
    
    Args:
        session_id: Valid session ID
        device_id: Device ID
    
    Returns:
        List of sensor names
    """
    try:
        # Validate session
        auth = session_manager.get_session(session_id)
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Fetch user's devices
        client = FieldClimateClient(auth)
        stations = client.get_user_stations()
        
        # Find matching device (using alphanumeric ID from name.original)
        for station in stations:
            if station.get('name', {}).get('original') == device_id:
                sensors = _extract_sensor_names(station)
                return SensorsListResponse(
                    device_id=device_id,
                    sensors=sensors
                )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching sensors: {str(e)}"
        )


@app.get("/api/sensor-info")
async def get_sensor_info(session_id: str, device_id: str):
    """
    Get simplified sensor information (Device ID + comma-separated names).
    
    Args:
        session_id: Valid session ID
        device_id: Alphanumeric device ID
    
    Returns:
        {device_id: "xxx", sensors: "Sensor1, Sensor2, ..."}
    """
    try:
        # Validate session
        auth = session_manager.get_session(session_id)
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Fetch sensors from FieldClimate API
        client = FieldClimateClient(auth)
        sensors_metadata = client.get_sensor_metadata(device_id)
        
        # Extract sensor names
        sensor_names = [s.get('name', s.get('name_original', 'Unknown')) for s in sensors_metadata]
        sensor_names = [s for s in sensor_names if s]  # Filter out empty
        
        return {
            "device_id": device_id,
            "sensors": ", ".join(sensor_names),
            "count": len(sensor_names)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching sensor info: {str(e)}"
        )


@app.get("/api/licenses")
async def get_licenses(session_id: str, device_id: str):
    """
    Get licenses attached to a device.
    
    Args:
        session_id: Valid session ID
        device_id: Alphanumeric device ID
    
    Returns:
        {device_id: "xxx", licenses: {...}}
    """
    try:
        # Validate session
        auth = session_manager.get_session(session_id)
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Fetch licenses from FieldClimate API
        client = FieldClimateClient(auth)
        licenses = client.get_device_licenses(device_id)
        
        # Format licenses for display
        formatted_licenses = _format_licenses(licenses)
        
        return {
            "device_id": device_id,
            "licenses": licenses,
            "summary": formatted_licenses
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching licenses: {str(e)}"
        )


@app.post("/api/query", response_model=ChatResponse)
async def process_query(request: ChatRequest):
    """
    Process user chat query and fetch sensor data.
    
    Args:
        request: ChatRequest with message and optional device_id
    
    Returns:
        ChatResponse with bot message and query results
    """
    try:
        # Validate session
        auth = session_manager.get_session(request.session_id)
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Fetch user's devices
        client = FieldClimateClient(auth)
        stations = client.get_user_stations()
        
        # Get timezone from device or default
        timezone = 'UTC'
        if request.device_id:
            for station in stations:
                if station.get('name', {}).get('original') == request.device_id:
                    tz = station.get('position', {}).get('timezoneCode') if station.get('position') else None
                    timezone = tz if tz else 'UTC'
                    break
        
        # Extract available device info
        available_devices = []
        for station in stations:
            device_info = {
                'device_id': station.get('name', {}).get('original'),  # Alphanumeric ID
                'name': station.get('name', {}).get('custom', 'Unknown'),
                'device_name': station.get('info', {}).get('device_name', '')
            }
            available_devices.append(device_info)
        
        # Parse user intent
        device_id = request.device_id
        sensors_for_parsing = []
        
        # If device_id provided, get sensors for that device
        if device_id:
            for station in stations:
                if station.get('name', {}).get('original') == device_id:
                    sensors_for_parsing = _extract_sensor_names(station)
                    break
        else:
            # Use sensors from first device for now
            if stations:
                sensors_for_parsing = _extract_sensor_names(stations[0])
        
        parser = IntentParser(available_devices, sensors_for_parsing, timezone)
        intent = parser.parse(request.user_message)
        
        # Handle license query (user asking "what licenses do I have")
        if intent.intent_type == 'get_licenses':
            if not device_id and not intent.device_id:
                # Need to specify device for license info
                if available_devices:
                    device_table = _format_devices_table(available_devices)
                    bot_msg = f"❌ Please select or type a device ID to see license information.\n\nYour devices:\n\n{device_table}"
                else:
                    bot_msg = "❌ No devices found. Please check your account access."
                return ChatResponse(
                    session_id=request.session_id,
                    bot_message=bot_msg,
                    query_result=None,
                )
            
            # Get licenses for the device
            device_for_license = device_id or intent.device_id
            licenses_data = client.get_device_licenses(device_for_license)
            
            licenses_table_data = _format_licenses(licenses_data)
            
            # Check if licenses exist
            if not licenses_table_data.get('tables') or len(licenses_table_data.get('tables', [])) == 0:
                bot_msg = f"❌ Licenses don't exist for this device ({device_for_license})"
                return ChatResponse(
                    session_id=request.session_id,
                    bot_message=bot_msg,
                    query_result=None,
                )
            
            bot_msg = f"📋 License information for device {device_for_license}"
            
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=QueryResult(
                    formatted_text=bot_msg,
                    query_params={},
                    table_data=licenses_table_data,
                    licenses_data=licenses_data
                ),
            )
        
        # Handle sensor list query (user asking "what sensors are available")
        if intent.intent_type == 'list_sensors':
            # Return list of available sensors
            available_sensors = sensors_for_parsing
            if not device_id and not intent.device_id:
                # Need to specify device for sensor list
                if available_devices:
                    device_table = _format_devices_table(available_devices)
                    bot_msg = f"❌ Please select or type a device ID to see available sensors.\n\nYour devices:\n\n{device_table}"
                else:
                    bot_msg = "❌ No devices found. Please check your account access."
                return ChatResponse(
                    session_id=request.session_id,
                    bot_message=bot_msg,
                    query_result=None,
                    error=None
                )
            
            # Get device_id if not provided
            if not device_id:
                device_id = intent.device_id
            
            # Validate device exists
            found_device = None
            for station in stations:
                if station.get('name', {}).get('original') == device_id:
                    found_device = station
                    available_sensors = _extract_sensor_names(station)
                    break
            
            if not found_device:
                # Device not found - provide helpful error
                if available_devices:
                    device_table = _format_devices_table(available_devices)
                    bot_msg = f"❌ This device ID doesn't exist or you don't have access to this device.\n\nDevice ID entered: {device_id}\n\nYour available devices:\n\n{device_table}"
                else:
                    bot_msg = f"❌ Device ID '{device_id}' not found and you have no available devices."
                return ChatResponse(
                    session_id=request.session_id,
                    bot_message=bot_msg,
                    query_result=None,
                    error=f"Invalid device ID: {device_id}"
                )
            
            # Format sensor list as simple text
            sensor_list = "\n".join([f"• {s}" for s in available_sensors])
            bot_msg = f"Available sensors for device {device_id}"
            
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=QueryResult(
                    formatted_text=bot_msg,
                    query_params={},
                    sensors_data=available_sensors
                ),
                error=None
            )
        
        # Check if we need user to specify device (only if not already provided)
        if not device_id and intent.is_ambiguous and intent.clarification_needed == "device":
            # Build a formatted table of devices
            device_table = _format_devices_table(available_devices)
            bot_msg = f"Please select a device to query:\n\n{device_table}"
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=None,
                error=None
            )
        
        # Use provided device_id or from intent
        if not device_id:
            device_id = intent.device_id
        
        # Validate device_id is provided
        if not device_id:
            # If still no device_id, ask user to select one
            if available_devices:
                device_table = _format_devices_table(available_devices)
                bot_msg = f"❌ Please select or type a device ID to query.\n\nYour available devices:\n\n{device_table}"
            else:
                bot_msg = "❌ No devices found. Please check your account access."
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=None,
                error="No device selected"
            )
        
        # Validate device exists and user has access
        found_device = None
        for station in stations:
            if station.get('name', {}).get('original') == device_id:
                found_device = station
                break
        
        if not found_device:
            # Device not found - provide helpful error
            if available_devices:
                device_list = ", ".join([d['device_id'] for d in available_devices])
                device_table = _format_devices_table(available_devices)
                bot_msg = f"❌ This device ID doesn't exist or you don't have access to this device.\n\nDevice ID entered: {device_id}\n\nYour available devices:\n\n{device_table}"
            else:
                bot_msg = f"❌ Device ID '{device_id}' not found and you have no available devices."
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=None,
                error=f"Invalid device ID: {device_id}"
            )
        
        # Fetch sensor data
        try:
            response = client.get_sensor_data(
                device_id,
                intent.data_type,
                intent.start_timestamp,
                intent.end_timestamp
            )
            
            # For raw data, limit results if user didn't specify dates
            if intent.data_type == 'raw' and not intent.date_range_specified:
                response = _limit_raw_data(response, intent.raw_limit or 8)
        except Exception as e:
            bot_msg = f"Error fetching data: {str(e)}"
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=None,
                error=str(e)
            )
        
        # Parse response
        parsed_sensors = client.parse_sensor_response(response)
        
        # Filter to requested sensors if specified, otherwise show all
        if intent.sensor_names:
            filtered = {}
            for sensor_name in intent.sensor_names:
                # Try exact match first
                if sensor_name in parsed_sensors:
                    filtered[sensor_name] = parsed_sensors[sensor_name]
                else:
                    # Try case-insensitive match
                    matched = False
                    for api_sensor, data in parsed_sensors.items():
                        # 1. Exact case-insensitive match
                        if api_sensor.lower() == sensor_name.lower():
                            filtered[api_sensor] = data
                            matched = True
                            break
                        # 2. Substring match (if sensor_name is contained in api_sensor)
                        elif sensor_name.lower() in api_sensor.lower():
                            filtered[api_sensor] = data
                            matched = True
                            break
                        # 3. Keyword match (check if key words match)
                        elif any(keyword in api_sensor.lower() for keyword in sensor_name.lower().split()):
                            if not matched or 'temperature' in sensor_name.lower():  # Prioritize temperature matches
                                filtered[api_sensor] = data
                                matched = True
                                break
            parsed_sensors = filtered
        
        if not parsed_sensors:
            # No matching sensors found
            available_names = list(response.get('data', [])) if response.get('data') else []
            available_names = [s.get('name', 'Unknown') for s in available_names]
            
            suggestions = suggest_sensors(request.user_message, available_names)
            
            bot_msg = "No matching sensors found. "
            if suggestions:
                bot_msg += f"Did you mean: {', '.join(suggestions)}?"
            else:
                bot_msg += "Run /sensors to see available sensors for this device."
            
            return ChatResponse(
                session_id=request.session_id,
                bot_message=bot_msg,
                query_result=None,
                error="No sensors matched"
            )
        
        # Format results as text and table
        formatted_text = _format_sensor_results(parsed_sensors, intent)
        table_data = _format_sensor_table(parsed_sensors, intent, device_id)
        
        bot_msg = f"Data retrieved for {_format_date_range(intent)} ({intent.data_type})"
        
        return ChatResponse(
            session_id=request.session_id,
            bot_message=bot_msg,
            query_result=QueryResult(
                formatted_text=formatted_text,
                query_params={
                    'device_id': device_id,
                    'data_type': intent.data_type
                },
                table_data=table_data
            ),
            error=None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        return ChatResponse(
            session_id=request.session_id,
            bot_message=f"Error processing query: {error_str}",
            query_result=None,
            error=error_str
        )


@app.post("/api/logout", response_model=LogoutResponse)
async def logout(session_id: str):
    """
    Logout user and clear session.
    
    Args:
        session_id: Valid session ID
    
    Returns:
        LogoutResponse
    """
    try:
        if session_manager.clear_session(session_id):
            return LogoutResponse(
                status="success",
                message="Logout successful"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session ID"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


# Helper functions

def _limit_raw_data(response: Dict[str, Any], limit: int = 8) -> Dict[str, Any]:
    """
    Limit raw data response to last N entries.
    
    Args:
        response: API response with dates and data
        limit: Maximum number of entries to return (default 8)
    
    Returns:
        Limited response dictionary
    """
    if not response or 'dates' not in response:
        return response
    
    dates = response.get('dates', [])
    data_list = response.get('data', [])
    
    # If already fewer than limit, return as is
    if len(dates) <= limit:
        return response
    
    # Keep last N entries
    limited_dates = dates[-limit:]
    limited_data = []
    
    for sensor_data in data_list:
        limited_sensor = sensor_data.copy()
        values = sensor_data.get('values', {})
        limited_values = {}
        
        # Limit each value array
        for agg_type, value_list in values.items():
            if isinstance(value_list, list):
                limited_values[agg_type] = value_list[-limit:]
            else:
                limited_values[agg_type] = value_list
        
        limited_sensor['values'] = limited_values
        limited_data.append(limited_sensor)
    
    return {
        'dates': limited_dates,
        'data': limited_data
    }


def _extract_sensor_names(station: dict) -> list:
    """Extract available sensor names from station metadata."""
    try:
        sensors = set()
        
        # Get from metadata if available (handle None)
        meta = station.get('meta') or {}
        
        # Common sensor mappings from metadata
        mappings = {
            'airTemp': 'Air temperature',
            'rh': 'Relative Humidity',
            'rain_last': 'Precipitation',
            'rain1h': 'Precipitation',
            'rain7d': 'Precipitation',
            'battery': 'Battery',
            'solarPanel': 'Solar Panel',
            'lw': 'Leaf Wetness',
            'airTemperatureDailyMinimum': 'Air temperature',
            'wind': 'Wind Speed',
            'gust': 'Wind Gust',
        }
        
        for meta_key, sensor_name in mappings.items():
            if meta_key in meta and meta[meta_key] is not None:
                sensors.add(sensor_name)
        
        # Add common defaults if no sensors found
        if not sensors:
            sensors.update([
                'Air temperature',
                'Relative Humidity',
                'Precipitation',
                'Solar Panel',
                'Battery'
            ])
        
        return sorted(list(sensors))
    except Exception as e:
        print(f"[SENSOR EXTRACT ERROR] {str(e)}", file=sys.stderr)
        # Return defaults on error
        return ['Air temperature', 'Relative Humidity', 'Precipitation', 'Solar Panel', 'Battery']


def _format_sensor_results(parsed_sensors: dict, intent) -> str:
    """Format sensor results as readable text table."""
    if not parsed_sensors:
        return "No data matched your query."
    
    lines = []
    
    for sensor_name, sensor_data in parsed_sensors.items():
        lines.append(f"\n📊 {sensor_name} ({intent.data_type})")
        lines.append("=" * 60)
        
        dates = sensor_data['dates']
        values = sensor_data['values']
        unit = sensor_data.get('unit', '')
        decimals = sensor_data.get('decimals', 1)
        
        # Build header
        aggregations = sensor_data.get('aggregations', list(values.keys()))
        header_parts = [f"{'Date':<20}"]
        
        for agg in aggregations:
            if agg in values:
                header_parts.append(f"{agg.upper():<12}")
        
        lines.append(" | ".join(header_parts))
        lines.append("-" * 60)
        
        # Build rows
        for i, date_str in enumerate(dates):
            row_parts = [f"{date_str:<20}"]
            
            for agg in aggregations:
                if agg in values and i < len(values[agg]):
                    val = values[agg][i]
                    if val is not None:
                        formatted_val = f"{val:.{decimals}f} {unit}".strip()
                    else:
                        formatted_val = "N/A"
                    row_parts.append(f"{formatted_val:<12}")
            
            lines.append(" | ".join(row_parts))
        
        lines.append(f"\nUnit: {unit} | Decimals: {decimals}")
    
    return "\n".join(lines)


def _format_sensor_table(parsed_sensors: dict, intent, device_id: str = None) -> Dict[str, Any]:
    """Format sensor results as consolidated table data for UI display - all sensors in one table."""
    if not parsed_sensors:
        return None
    
    # Consolidate all sensors into a single table
    sensor_names = list(parsed_sensors.keys())
    date_range = _format_date_range(intent)
    
    # Get all dates from first sensor (assume all sensors have same dates)
    first_sensor = list(parsed_sensors.values())[0]
    all_dates = first_sensor.get('dates', [])
    
    # Build unified headers: Date, then for each sensor: [Agg1, Agg2, ...]
    headers = ['Date']
    sensor_column_map = {}  # Map sensor to its column indices
    
    for sensor_name in sensor_names:
        sensor_data = parsed_sensors[sensor_name]
        aggregations = sensor_data.get('aggregations', list(sensor_data.get('values', {}).keys()))
        sensor_column_map[sensor_name] = {
            'start_col': len(headers),
            'aggregations': aggregations,
            'unit': sensor_data.get('unit', ''),
            'decimals': sensor_data.get('decimals', 1)
        }
        
        # Add column headers: Sensor Name (Agg1), Sensor Name (Agg2), etc.
        for agg in aggregations:
            col_header = f"{sensor_name} ({agg.replace('_', ' ').title()})"
            headers.append(col_header)
    
    # Build unified rows
    rows = []
    for date_idx, date_str in enumerate(all_dates):
        row = [date_str]
        
        # Add values for each sensor
        for sensor_name in sensor_names:
            sensor_data = parsed_sensors[sensor_name]
            values = sensor_data.get('values', {})
            decimals = sensor_data.get('decimals', 1)
            aggregations = sensor_column_map[sensor_name]['aggregations']
            
            for agg in aggregations:
                if agg in values and date_idx < len(values[agg]):
                    val = values[agg][date_idx]
                    if val is not None:
                        formatted_val = f"{val:.{decimals}f}"
                    else:
                        formatted_val = ""
                else:
                    formatted_val = ""
                
                row.append(formatted_val)
        
        rows.append(row)
    
    table_obj = {
        'name': f"Consolidated Data - {', '.join(sensor_names)}",
        'data_type': intent.data_type,
        'headers': headers,
        'rows': rows,
        'sensor_details': sensor_column_map
    }
    
    return {
        'tables': [table_obj],
        'device_id': device_id,
        'sensors': sensor_names,
        'date_range': date_range,
        'data_type': intent.data_type
    }


def _format_date_range(intent) -> str:
    """Format date range from intent."""
    from datetime import datetime
    
    if intent.start_timestamp and intent.end_timestamp:
        start = datetime.fromtimestamp(intent.start_timestamp).strftime("%Y-%m-%d")
        end = datetime.fromtimestamp(intent.end_timestamp).strftime("%Y-%m-%d")
        return f"{start} to {end}"
    
    return "current period"


def _format_devices_table(devices: list) -> str:
    """Format devices as a clean table for display."""
    if not devices:
        return "No devices available"
    
    lines = []
    lines.append("Available Devices:")
    lines.append("-" * 80)
    lines.append(f"{'ID':<15} | {'Device Name':<30} | {'Timezone':<20}")
    lines.append("-" * 80)
    
    for device in devices:
        device_id = device.get('device_id', 'N/A')
        name = device.get('name', 'Unknown')[:28]
        timezone = device.get('timezone', 'UTC')
        lines.append(f"{device_id:<15} | {name:<30} | {timezone:<20}")
    
    lines.append("-" * 80)
    lines.append("\nSelect a device from the dropdown above and try your query again.")
    
    return "\n".join(lines)


def _format_licenses(licenses_data: dict) -> Dict[str, Any]:
    """Format license information as table data."""
    if not licenses_data:
        return {
            'tables': [],
            'summary': "No licenses attached to this device"
        }
    
    tables = []
    
    # Forecast licenses
    forecast = licenses_data.get('Forecast', [])
    if forecast and len(forecast) > 0:
        rows = []
        for lic in forecast:
            from_date = lic.get('from', 'N/A')
            to_date = lic.get('to', 'N/A')
            rows.append([from_date, to_date])
        
        tables.append({
            'name': 'Weather Forecast',
            'headers': ['Start Date', 'End Date'],
            'rows': rows
        })
    
    # Work Planning licenses
    work_planning = licenses_data.get('WorkPlanning', [])
    if work_planning and len(work_planning) > 0:
        rows = []
        for lic in work_planning:
            from_date = lic.get('from', 'N/A')
            to_date = lic.get('to', 'N/A')
            rows.append([from_date, to_date])
        
        tables.append({
            'name': 'Work Planning',
            'headers': ['Start Date', 'End Date'],
            'rows': rows
        })
    
    # Disease models
    models = licenses_data.get('models', {})
    if models:
        for model_name, model_licenses in models.items():
            rows = []
            for lic in model_licenses:
                from_date = lic.get('from', 'N/A')
                to_date = lic.get('to', 'N/A')
                rows.append([from_date, to_date])
            
            tables.append({
                'name': model_name,
                'headers': ['Start Date', 'End Date'],
                'rows': rows
            })
    
    return {
        'tables': tables,
        'summary': f"Found {len(tables)} license(s)"
    }


# Mount static files
try:
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
except:
    pass  # Static files not available in dev


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
