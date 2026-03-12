"""Intent parser for chat queries."""
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import pytz
from .api_client import human_date_to_timestamp


class Intent:
    """Parsed user intent."""
    
    def __init__(self):
        self.device_id: Optional[int] = None
        self.sensor_names: List[str] = []
        self.data_type: str = 'hourly'  # Default
        self.start_timestamp: Optional[int] = None
        self.end_timestamp: Optional[int] = None
        self.aggregation: Optional[str] = None
        self.raw_query: str = ""
        self.is_ambiguous = False
        self.clarification_needed = ""
        self.intent_type: str = 'query_data'  # 'query_data', 'list_sensors', or 'get_licenses'
        self.date_range_specified: bool = False  # Track if user explicitly mentioned dates
        self.raw_limit: Optional[int] = None  # Limit for raw data (default: 8)


class IntentParser:
    """Parse natural language queries to extract intent."""
    
    def __init__(self, available_devices: List[Dict], available_sensors: List[str], user_timezone: str = 'UTC'):
        """
        Initialize parser.
        
        Args:
            available_devices: List of {device_id, name, device_name}
            available_sensors: List of sensor names available for the device
            user_timezone: User's timezone
        """
        self.available_devices = {
            d['device_id']: d for d in available_devices
        }
        self.available_sensors = available_sensors
        self.user_timezone = user_timezone
    
    def parse(self, user_message: str) -> Intent:
        """
        Parse user message into intent.
        
        Args:
            user_message: Raw user input
        
        Returns:
            Intent object with extracted parameters
        """
        intent = Intent()
        intent.raw_query = user_message
        
        msg_lower = user_message.lower()
        
        # Detect intent type based on user query
        if self._is_asking_for_licenses(msg_lower):
            intent.intent_type = 'get_licenses'
        elif self._is_asking_for_sensors_list(msg_lower):
            intent.intent_type = 'list_sensors'
        else:
            intent.intent_type = 'query_data'
        
        # Extract data type
        if 'raw' in msg_lower:
            intent.data_type = 'raw'
            intent.raw_limit = 8  # Default 8 raw entries
        elif 'hourly' in msg_lower or 'hour' in msg_lower:
            intent.data_type = 'hourly'
        elif 'daily' in msg_lower or 'day' in msg_lower:
            intent.data_type = 'daily'
        elif 'monthly' in msg_lower or 'month' in msg_lower:
            intent.data_type = 'monthly'
        elif 'weekly' in msg_lower or 'week' in msg_lower:
            intent.data_type = 'daily'  # Fallback: daily data for weekly view
        else:
            intent.data_type = 'hourly'  # Default
        
        # Extract device ID
        device_match = self._extract_device(user_message)
        if device_match:
            intent.device_id = device_match
        
        # Extract sensor names
        intent.sensor_names = self._extract_sensors(user_message)
        
        # Extract aggregation preference
        intent.aggregation = self._extract_aggregation(user_message)
        
        # Extract date range
        start_ts, end_ts, dates_specified = self._extract_dates(user_message, intent.data_type)
        intent.start_timestamp = start_ts
        intent.end_timestamp = end_ts
        intent.date_range_specified = dates_specified
        
        # Check for ambiguities
        if not intent.device_id:
            intent.is_ambiguous = True
            intent.clarification_needed = "device"
        
        return intent
    
    def _extract_device(self, message: str) -> Optional[int]:
        """Extract device ID from message."""
        msg_lower = message.lower()
        
        # Look for "device X" pattern
        device_pattern = r'device\s+(\d+)'
        match = re.search(device_pattern, msg_lower)
        if match:
            device_id = int(match.group(1))
            if device_id in self.available_devices:
                return device_id
        
        # Look for device name
        for dev_id, dev_info in self.available_devices.items():
            if dev_info['name'] in message or dev_info['device_name'] in message:
                return dev_id
        
        return None
    
    def _extract_sensors(self, message: str) -> List[str]:
        """Extract sensor names from message - returns ALL matching sensors."""
        msg_lower = message.lower()
        sensors = []
        
        # Look for exact sensor name matches (case-insensitive)
        for sensor in self.available_sensors:
            sensor_lower = sensor.lower()
            if sensor_lower in msg_lower:
                sensors.append(sensor)
        
        # If no exact matches, try fuzzy matching for common keywords
        if not sensors:
            keywords = {
                'air': 'air',  # Match all sensors containing 'air'
                'temperature': 'temperature',
                'temp': 'temperature',
                'humidity': 'humidity',
                'rh': 'humidity',
                'rain': 'precipitation',
                'precip': 'precipitation',
                'precipitation': 'precipitation',
                'solar': 'solar',
                'panel': 'solar',
                'battery': 'battery',
                'leaf': 'wetness',
                'wetness': 'wetness',
                'frost': 'frost',
                'wind': 'wind',
                'gust': 'wind',
            }
            
            # Find the first matching keyword
            matched_keyword = None
            for keyword, match_term in keywords.items():
                if keyword in msg_lower:
                    matched_keyword = match_term
                    break
            
            # If a keyword matched, find ALL available sensors containing that keyword
            if matched_keyword:
                for available_sensor in self.available_sensors:
                    if matched_keyword.lower() in available_sensor.lower():
                        sensors.append(available_sensor)
                
                # If we found multiple sensors matching the keyword, return them all
                if sensors:
                    return sensors
            
            # Fallback: broader substring matching for common keywords
            for keyword in ['temperature', 'humidity', 'rain', 'wind', 'battery', 'solar', 'pressure']:
                if keyword in msg_lower:
                    for available_sensor in self.available_sensors:
                        if keyword in available_sensor.lower():
                            sensors.append(available_sensor)
                    if sensors:
                        break
        
        return sensors
    
    def _extract_aggregation(self, message: str) -> Optional[str]:
        """Extract aggregation preference (avg, max, min, sum, last)."""
        msg_lower = message.lower()
        
        if 'average' in msg_lower or 'avg' in msg_lower:
            return 'avg'
        elif 'maximum' in msg_lower or 'max' in msg_lower:
            return 'max'
        elif 'minimum' in msg_lower or 'min' in msg_lower:
            return 'min'
        elif 'sum' in msg_lower or 'total' in msg_lower:
            return 'sum'
        elif 'last' in msg_lower:
            return 'last'
        
        return None
    
    def _is_asking_for_sensors_list(self, message: str) -> bool:
        """
        Detect if user is asking for a list of sensors vs actual data.
        
        Args:
            message: Lowercased user message
        
        Returns:
            True if asking for sensor list, False if asking for data
        """
        sensor_list_keywords = [
            'which sensors',
            'what sensors',
            'available sensors',
            'list sensors',
            'show sensors',
            'get sensors',
            'sensors available',
            'sensors list',
        ]
        
        for keyword in sensor_list_keywords:
            if keyword in message:
                return True
        
        return False
    
    def _is_asking_for_licenses(self, message: str) -> bool:
        """
        Detect if user is asking for license information.
        
        Args:
            message: Lowercased user message
        
        Returns:
            True if asking for licenses, False otherwise
        """
        license_keywords = [
            'licenses',
            'what licenses',
            'which licenses',
            'my licenses',
            'attached',
            'features attached',
        ]
        
        for keyword in license_keywords:
            if keyword in message:
                return True
        
        return False
    
    def _extract_dates(self, message: str, data_type: str = 'hourly') -> Tuple[Optional[int], Optional[int], bool]:
        """
        Extract date range from message with smart defaults based on data type.
        Handles: "last X days", "last X weeks", "last X months", "from DATE to DATE"
        
        Args:
            message: User message
            data_type: Type of data (hourly, daily, monthly, raw)
        
        Returns:
            (start_timestamp, end_timestamp, dates_specified)
            dates_specified: True if user explicitly mentioned dates, False if using defaults
        """
        msg_lower = message.lower()
        
        # Pattern 1: "last X days/weeks/months"
        last_pattern = r'last\s+(\d+)\s+(days?|weeks?|months?|hours?)'
        match = re.search(last_pattern, msg_lower)
        
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            
            now = datetime.now(pytz.timezone(self.user_timezone))
            end_ts = int(now.timestamp())
            
            try:
                if 'day' in unit:
                    start_ts = int((now - timedelta(days=amount)).timestamp())
                    return (start_ts, end_ts, True)
                elif 'week' in unit:
                    start_ts = int((now - timedelta(weeks=amount)).timestamp())
                    return (start_ts, end_ts, True)
                elif 'month' in unit:
                    # Go back N months
                    new_month = now.month - amount
                    new_year = now.year
                    while new_month <= 0:
                        new_month += 12
                        new_year -= 1
                    start_date = now.replace(year=new_year, month=new_month, day=1, hour=0, minute=0, second=0, microsecond=0)
                    start_ts = int(start_date.timestamp())
                    return (start_ts, end_ts, True)
                elif 'hour' in unit:
                    start_ts = int((now - timedelta(hours=amount)).timestamp())
                    return (start_ts, end_ts, True)
            except Exception:
                pass
        
        # Pattern 2: "from DATE to DATE" or "DATE to DATE"
        from_to_pattern = r'from\s+([^,]+?)\s+to\s+([^,\.\?]+)'
        match = re.search(from_to_pattern, msg_lower)
        
        if match:
            start_str = match.group(1).strip()
            end_str = match.group(2).strip()
        else:
            # Try simpler pattern
            to_pattern = r'([a-z\d\s]+)\s+to\s+([a-z\d\s]+)'
            match = re.search(to_pattern, msg_lower)
            if match:
                start_str = match.group(1).strip()
                end_str = match.group(2).strip()
            else:
                # No explicit date range found - use smart defaults
                return self._get_default_date_range(data_type)
        
        try:
            start_ts = human_date_to_timestamp(start_str, self.user_timezone)
            end_ts = human_date_to_timestamp(end_str, self.user_timezone)
            
            # Ensure end_ts is end of day if not time-specific
            if 'hour' not in msg_lower:
                end_ts = end_ts + 86400  # Add 1 day
            
            return (start_ts, end_ts, True)
        except Exception:
            # If parsing fails, use smart defaults
            return self._get_default_date_range(data_type)
    
    def _get_default_date_range(self, data_type: str = 'hourly') -> Tuple[int, int, bool]:
        """
        Get default date range based on data type.
        
        Args:
            data_type: Type of data (hourly, daily, monthly, raw)
        
        Returns:
            (start_timestamp, end_timestamp, dates_specified=False)
        """
        now = datetime.now(pytz.timezone(self.user_timezone))
        end_ts = int(now.timestamp())
        
        if data_type == 'hourly':
            # Default: Last 24 hours from 12 AM to current hour
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_ts = int(start_of_day.timestamp())
        elif data_type == 'daily':
            # Default: Last 7 days
            start_ts = int((now - timedelta(days=7)).timestamp())
        elif data_type == 'monthly':
            # Default: Current year from January to current month (end of current month)
            start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            start_ts = int(start_of_year.timestamp())
            # End of current month
            if now.month == 12:
                end_of_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                end_of_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_ts = int(end_of_month.timestamp())
        elif data_type == 'raw':
            # For raw data, limit by count (8 entries) in the API call
            # Default range: last 24 hours (will be limited to 8 entries)
            start_ts = int((now - timedelta(hours=24)).timestamp())
        else:
            # Fallback: last 7 days
            start_ts = int((now - timedelta(days=7)).timestamp())
        
        return (start_ts, end_ts, False)


def suggest_sensors(query: str, available_sensors: List[str]) -> List[str]:
    """
    Suggest sensors based on query keywords.
    
    Args:
        query: User's query
        available_sensors: List of available sensors
    
    Returns:
        List of suggested sensor names
    """
    query_lower = query.lower()
    suggestions = []
    
    # Look for any sensor name that partially matches the query
    for sensor in available_sensors:
        sensor_lower = sensor.lower()
        words = sensor_lower.split()
        
        for word in words:
            if len(word) > 2 and word in query_lower:
                suggestions.append(sensor)
                break
    
    return suggestions[:5]  # Return top 5 suggestions
