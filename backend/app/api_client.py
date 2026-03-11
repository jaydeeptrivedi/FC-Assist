"""FieldClimate API client."""
import requests
import json
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pytz
from .auth import HMACAuth, TokenAuth


class FieldClimateClient:
    """Client for FieldClimate API v2."""
    
    BASE_URL = "https://api.fieldclimate.com/v2"
    
    def __init__(self, auth):
        """
        Initialize client.
        
        Args:
            auth: HMACAuth or TokenAuth instance
        """
        self.auth = auth
    
    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Build request headers based on auth type."""
        headers = {"Content-Type": "application/json"}
        
        if isinstance(self.auth, HMACAuth):
            sig_headers = self.auth.sign_request(method, path)
            headers.update(sig_headers)
        elif isinstance(self.auth, TokenAuth):
            headers.update(self.auth.get_headers())
        
        return headers
    
    def _make_request(self, method: str, path: str) -> Dict[str, Any]:
        """
        Make HTTP request to API.
        
        Args:
            method: HTTP method
            path: API path
        
        Returns:
            JSON response
        
        Raises:
            Exception: If API call fails
        """
        url = self.BASE_URL + path
        headers = self._get_headers(method, path)
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            
            if status_code == 401:
                raise Exception("Authentication failed: Invalid credentials")
            elif status_code == 403:
                raise Exception("API subscription inactive or no access to this device")
            elif status_code == 404:
                raise Exception("Device not found")
            elif status_code == 429:
                raise Exception("Rate limit exceeded: Please try again later")
            else:
                raise Exception(f"API error: {e.response.text}")
        except requests.exceptions.Timeout:
            raise Exception("API request timeout: Please try again")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
    
    def get_user_stations(self) -> List[Dict]:
        """
        Fetch user's accessible stations/devices.
        
        Returns:
            List of station dictionaries
        """
        response = self._make_request("GET", "/user/stations")
        
        # Response is a flat list of stations
        if isinstance(response, list):
            return response
        return []
    
    def get_sensor_data(
        self,
        device_id: str,
        data_type: str,
        start_timestamp: int,
        end_timestamp: int
    ) -> Dict[str, Any]:
        """
        Fetch sensor data for a device.
        
        Args:
            device_id: Device ID (alphanumeric identifier from station name.original)
            data_type: 'raw', 'hourly', 'daily', or 'monthly'
            start_timestamp: Unix timestamp (start)
            end_timestamp: Unix timestamp (end)
        
        Returns:
            {dates: [...], data: [{name, unit, values: {...}}, ...]}
        """
        if data_type not in ['raw', 'hourly', 'daily', 'monthly']:
            raise ValueError(f"Invalid data_type: {data_type}")
        
        # Build path with alphanumeric device ID
        path = f"/data/{device_id}/{data_type}/from/{start_timestamp}/to/{end_timestamp}"
        
        response = self._make_request("GET", path)
        
        return response
    
    def parse_sensor_response(self, response: Dict) -> Dict[str, Dict]:
        """
        Parse API response into sensor-keyed dictionary.
        
        Args:
            response: {dates: [...], data: [{name, unit, aggr, values: {...}}, ...]}
        
        Returns:
            {sensor_name: {unit, decimals, dates, values}, ...}
        """
        dates = response.get('dates', [])
        data_list = response.get('data', [])
        
        parsed = {}
        for sensor_data in data_list:
            sensor_name = sensor_data.get('name', 'Unknown')
            parsed[sensor_name] = {
                'name': sensor_data.get('name'),
                'unit': sensor_data.get('unit'),
                'decimals': sensor_data.get('decimals', 1),
                'aggregations': sensor_data.get('aggr', []),
                'dates': dates,
                'values': sensor_data.get('values', {})
            }
        
        return parsed
    
    def get_sensor_metadata(self, device_id: str) -> List[Dict]:
        """
        Fetch sensor metadata for a device.
        
        Args:
            device_id: Device ID (alphanumeric identifier)
        
        Returns:
            List of sensor metadata dictionaries
        """
        path = f"/station/{device_id}/sensors"
        response = self._make_request("GET", path)
        
        # Response is typically a list of sensor metadata
        if isinstance(response, list):
            return response
        return []
    
    def get_device_licenses(self, device_id: str) -> Dict[str, Any]:
        """
        Fetch licenses attached to a device.
        
        Args:
            device_id: Device ID (alphanumeric identifier)
        
        Returns:
            Dictionary containing licenses info (Forecast, WorkPlanning, models, etc.)
        """
        path = f"/station/{device_id}/licenses"
        response = self._make_request("GET", path)
        return response


def human_date_to_timestamp(date_str: str, timezone_name: str = 'UTC') -> int:
    """
    Convert human-readable date to Unix timestamp.
    
    Args:
        date_str: Date string (e.g., "2026-03-01", "March 1", "today", "yesterday")
        timezone_name: Timezone identifier (e.g., "Europe/Vienna")
    
    Returns:
        Unix timestamp
    """
    from dateutil import parser as date_parser
    
    date_str = date_str.lower().strip()
    tz = pytz.timezone(timezone_name)
    now = datetime.now(tz)
    
    # Handle relative dates
    if date_str in ['today', 'now']:
        target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_str == 'yesterday':
        target_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_str == 'tomorrow':
        target_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif 'last 7 days' in date_str or '7 days ago' in date_str:
        target_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif 'this month' in date_str:
        target_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif 'this week' in date_str:
        # Start of current week (Monday)
        target_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Try to parse as regular date
        try:
            parsed = date_parser.parse(date_str, fuzzy=False)
            # Make timezone aware if it isn't
            if parsed.tzinfo is None:
                parsed = tz.localize(parsed)
            target_date = parsed
        except:
            raise ValueError(f"Could not parse date: {date_str}")
    
    return int(target_date.timestamp())
