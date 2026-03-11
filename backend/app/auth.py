"""Authentication and session management."""
import time
import json
import sys
from typing import Optional, Dict, Union
from datetime import datetime, timedelta
from .hmac_signer import HMACSignatureSigner


class HMACAuth:
    """HMAC-SHA256 authentication for FieldClimate API."""
    
    def __init__(self, public_key: str, private_key: str):
        self.public_key = public_key
        self.private_key = private_key
        self.signer = HMACSignatureSigner(public_key, private_key)
    
    def sign_request(self, method: str, path: str, timestamp: str = None) -> Dict[str, str]:
        """
        Generate HMAC-SHA256 signature for FieldClimate API.
        
        Uses dedicated HMACSignatureSigner for clean separation of concerns.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /v2/user/stations)
            timestamp: Optional UTC timestamp (auto-generated if None)
        
        Returns:
            Headers dict with Authorization and Request-Date
        """
        result = self.signer.sign(method, path, timestamp)
        return result['headers']


class TokenAuth:
    """Token-based authentication."""
    
    def __init__(self, token: str):
        self.token = token
    
    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.token}"
        }


class SessionManager:
    """In-memory session management (no persistence)."""
    
    def __init__(self):
        self._sessions: Dict[str, Dict] = {}
        self._session_timeout = 3600  # 1 hour in seconds
    
    def create_session(self, auth_method: str, credentials: Dict) -> str:
        """
        Create a new session.
        
        Args:
            auth_method: 'hmac' or 'token'
            credentials: {public_key, private_key} or {auth_token}
        
        Returns:
            Session ID
        """
        import secrets
        session_id = secrets.token_urlsafe(32)
        
        if auth_method == 'hmac':
            auth_obj = HMACAuth(
                credentials.get('public_key'),
                credentials.get('private_key')
            )
        elif auth_method == 'token':
            auth_obj = TokenAuth(credentials.get('auth_token'))
        else:
            raise ValueError(f"Unknown auth method: {auth_method}")
        
        self._sessions[session_id] = {
            'auth': auth_obj,
            'method': auth_method,
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Union[HMACAuth, TokenAuth]]:
        """Get auth object from session ID."""
        if session_id not in self._sessions:
            return None
        
        session = self._sessions[session_id]
        
        # Check if session expired
        if datetime.now() - session['last_activity'] > timedelta(seconds=self._session_timeout):
            del self._sessions[session_id]
            return None
        
        # Update last activity
        session['last_activity'] = datetime.now()
        
        return session['auth']
    
    def get_session_method(self, session_id: str) -> Optional[str]:
        """Get auth method for session."""
        if session_id not in self._sessions:
            return None
        return self._sessions[session_id]['method']
    
    def clear_session(self, session_id: str) -> bool:
        """Clear session credentials."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def is_session_valid(self, session_id: str) -> bool:
        """Check if session is valid and not expired."""
        return session_id in self._sessions and self.get_session(session_id) is not None


# Global session manager
session_manager = SessionManager()
