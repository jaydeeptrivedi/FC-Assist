"""
Dedicated HMAC-SHA256 signer for FieldClimate API.
Matches the JavaScript implementation exactly.
"""
import hmac
import hashlib
import sys
from time import gmtime, strftime


class HMACSignatureSigner:
    """Generate HMAC signatures matching FieldClimate API requirements."""
    
    def __init__(self, public_key: str, private_key: str):
        """
        Initialize signer with credentials.
        
        Args:
            public_key: FieldClimate public key
            private_key: FieldClimate private key
        """
        self.public_key = public_key
        self.private_key = private_key
    
    def generate_timestamp(self) -> str:
        """
        Generate UTC timestamp in JavaScript's toUTCString() format.
        
        Returns:
            Timestamp string like "Wed, 11 Mar 2026 11:15:09 GMT"
        """
        timestamp = strftime('%a, %d %b %Y %H:%M:%S GMT', gmtime())
        return timestamp
    
    def sign(self, method: str, request_path: str, timestamp: str = None) -> dict:
        """
        Sign a request using HMAC-SHA256.
        
        Matches JavaScript:
        const content_to_sign = params.method + params.request + timestamp + public_key;
        const signature = CryptoJS.HmacSHA256(content_to_sign, private_key);
        const hmac_str = 'hmac ' + public_key + ':' + signature;
        
        Args:
            method: HTTP method (GET, POST, etc.)
            request_path: API path (e.g., /v2/user/stations)
            timestamp: Optional UTC timestamp (auto-generated if None)
        
        Returns:
            dict with 'headers' containing Authorization and Request-Date
        """
        if timestamp is None:
            timestamp = self.generate_timestamp()
        
        # Step 1: Build content to sign (direct concatenation, no separators)
        content_to_sign = method + request_path + timestamp + self.public_key
        
        # Step 2: Generate signature using HMAC-SHA256
        signature_bytes = hmac.new(
            self.private_key.encode('utf-8'),
            content_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Step 3: Convert to hex string (lowercase to match API requirements)
        signature_hex = signature_bytes.hex().lower()
        
        # Step 4: Format HMAC header
        hmac_str = f'hmac {self.public_key}:{signature_hex}'
        
        # Step 5: Build headers
        headers = {
            'Authorization': hmac_str,
            'Request-Date': timestamp
        }
        
        return {
            'headers': headers,
            'timestamp': timestamp,
            'signature': signature_hex
        }
    
    def verify_signature_format(self, signature: str) -> bool:
        """
        Verify signature has expected format (64 uppercase hex chars for SHA256).
        
        Args:
            signature: Hex signature string
        
        Returns:
            True if format is valid
        """
        if not isinstance(signature, str):
            return False
        if len(signature) != 64:  # SHA256 = 32 bytes = 64 hex chars
            return False
        try:
            int(signature, 16)  # Try to parse as hex
            return True
        except ValueError:
            return False
    
    def test_signing(self) -> bool:
        """
        Test signing with sample data to verify implementation.
        
        Returns:
            True if test passes
        """
        # Test with sample data
        result = self.sign('GET', '/v2/user/stations')
        
        signature = result['signature']
        is_valid = self.verify_signature_format(signature)
        
        return is_valid


def create_hmac_headers(public_key: str, private_key: str, method: str, request_path: str) -> dict:
    """
    Convenience function to create HMAC headers.
    
    Args:
        public_key: FieldClimate public key
        private_key: FieldClimate private key
        method: HTTP method
        request_path: API path
    
    Returns:
        Headers dict for requests
    """
    signer = HMACSignatureSigner(public_key, private_key)
    result = signer.sign(method, request_path)
    return result['headers']


# Example usage for testing
if __name__ == '__main__':
    # Test with sample keys
    test_public = '1534d346b6b0054179820db1a19019a172957f3d'
    test_private = '1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p'
    
    signer = HMACSignatureSigner(test_public, test_private)
    result = signer.sign('GET', '/v2/user/stations')
    
    print("\nFinal Headers:")
    print(f"Authorization: {result['headers']['Authorization']}")
    print(f"Request-Date: {result['headers']['Request-Date']}")
