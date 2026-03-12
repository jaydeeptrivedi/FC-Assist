/**
 * Authentication module for FC Assist
 */

class AuthManager {
    constructor() {
        this.currentSession = null;
        this.devices = [];
    }
    
    // Initialize auth modal
    init() {
        this.setupTabSwitching();
        this.setupFormSubmission();
        this.setupEyeToggle();  // Setup password visibility toggles
        this.preloadHMACKeys();  // Preload HMAC keys from environment variables
        
        // Check if already authenticated
        if (SessionStorage.isAuthenticated()) {
            this.restoreSession();
        }
    }
    
    // Setup tab switching in auth modal
    setupTabSwitching() {
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const tab = e.target.dataset.tab;
                this.switchTab(tab);
            });
        });
    }
    
    // Switch auth tab
    switchTab(tab) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(el => {
            el.classList.remove('active');
        });
        
        // Remove active class from all buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Show selected tab
        const tabContent = document.getElementById(`${tab}-tab`);
        if (tabContent) {
            tabContent.classList.add('active');
        }
        
        // Mark button as active
        event.target.classList.add('active');
    }
    
    // Setup eye toggle buttons for password visibility
    setupEyeToggle() {
        const eyeToggles = document.querySelectorAll('.eye-toggle');
        
        eyeToggles.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                
                const inputId = button.dataset.input;
                const input = document.getElementById(inputId);
                
                if (!input) return;
                
                // Toggle input type
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                
                // Update button classes for visual feedback
                button.classList.toggle('revealed', !isPassword);
            });
        });
    }
    
    // Preload HMAC keys from environment variables if available
    async preloadHMACKeys() {
        try {
            const envKeys = await this.loadHMACKeysFromEnv();
            
            if (envKeys && envKeys.public_key && envKeys.private_key) {
                const publicKeyInput = document.getElementById('publicKey');
                const privateKeyInput = document.getElementById('privateKey');
                
                if (publicKeyInput && privateKeyInput) {
                    publicKeyInput.value = envKeys.public_key;
                    privateKeyInput.value = envKeys.private_key;
                    
                    // Show indicator that keys were preloaded from environment
                    this.showKeyPreloadedIndicator('environment');
                }
            }
        } catch (error) {
            // No env keys available or error occurred, continue without preloading
            console.log('No environment HMAC keys available');
        }
    }
    
    // Load HMAC keys from backend environment variables
    async loadHMACKeysFromEnv() {
        try {
            const response = await apiRequest('/config/hmac-keys', {
                method: 'GET'
            });
            
            if (response && response.public_key && response.private_key) {
                return {
                    public_key: response.public_key,
                    private_key: response.private_key
                };
            }
        } catch (error) {
            // Endpoint may not exist or keys not configured in env
            console.debug('HMAC environment keys not available');
        }
        return null;
    }
    
    // Show visual indicator that keys were preloaded
    showKeyPreloadedIndicator(source = 'environment') {
        const hmacForm = document.getElementById('hmacForm');
        if (!hmacForm) return;
        
        // Remove any existing indicator
        const existing = hmacForm.querySelector('.preloaded-indicator');
        if (existing) existing.remove();
        
        // Create indicator based on source
        const indicator = document.createElement('div');
        indicator.className = 'preloaded-indicator';
        const sourceText = source === 'environment' ? 'environment variables' : 'configuration';
        indicator.innerHTML = `<small style="color: #28a745; font-weight: 600;">✓ HMAC keys preloaded from ${sourceText}</small>`;
        hmacForm.insertBefore(indicator, hmacForm.firstChild);
    }
    
    // Setup form submission
    setupFormSubmission() {
        const hmacForm = document.getElementById('hmacForm');
        const tokenForm = document.getElementById('tokenForm');
        
        if (hmacForm) {
            hmacForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.authenticateWithHMAC();
            });
        }
        
        if (tokenForm) {
            tokenForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.authenticateWithToken();
            });
        }
    }
    
    // Authenticate with HMAC keys
    async authenticateWithHMAC() {
        const publicKey = document.getElementById('publicKey').value.trim();
        const privateKey = document.getElementById('privateKey').value.trim();
        
        if (!publicKey || !privateKey) {
            showError('Please enter both public and private keys');
            return;
        }
        
        await this.authenticate('hmac', {
            public_key: publicKey,
            private_key: privateKey
        });
        
        // Clear form fields
        document.getElementById('publicKey').value = '';
        document.getElementById('privateKey').value = '';
    }
    
    // Authenticate with token
    async authenticateWithToken() {
        const authToken = document.getElementById('authToken').value.trim();
        
        if (!authToken) {
            showError('Please enter your auth token', 'authError');
            return;
        }
        
        await this.authenticate('token', {
            auth_token: authToken
        });
        
        // Clear form field
        document.getElementById('authToken').value = '';
    }
    
    // Send authentication request to backend
    async authenticate(method, credentials) {
        showLoading('authLoading');
        hideError('authError');
        
        try {
            const response = await apiRequest('/auth/verify', {
                method: 'POST',
                data: {
                    method: method,
                    credentials: credentials
                }
            });
            
            if (response.status === 'success') {
                this.currentSession = {
                    sessionId: response.session_id,
                    devicesCount: response.devices_count,
                    authMethod: method
                };
                
                // Store session ID (cleared on tab close)
                SessionStorage.setSessionId(response.session_id);
                
                hideLoading('authLoading');
                this.showMainLayout();
                this.loadDevices();
            } else {
                showError(`Authentication failed: ${response.message}`, 'authError');
            }
        } catch (error) {
            hideLoading('authLoading');
            showError(`Authentication error: ${error.message}`, 'authError');
        }
    }
    
    // Load user's devices
    async loadDevices() {
        if (!this.currentSession) return;
        
        try {
            const response = await apiRequest('/devices', {
                method: 'GET',
                params: {
                    session_id: this.currentSession.sessionId
                }
            });
            
            this.devices = response.devices;
            this.populateDeviceSelect();
        } catch (error) {
            console.error('Error loading devices:', error);
        }
    }
    
    // Populate device dropdown
    populateDeviceSelect() {
        const select = document.getElementById('deviceSelect');
        
        // Clear existing options
        select.innerHTML = '<option value="">Choose a device...</option>';
        
        // Add devices with ID shown clearly
        this.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.device_id;  // Store alphanumeric device ID
            option.textContent = `${device.device_id} (${device.name})`;
            select.appendChild(option);
        });
        
        // Auto-select first device if only one available
        if (this.devices.length === 1) {
            select.value = this.devices[0].device_id;
        }
    }
    
    // Show main layout
    showMainLayout() {
        const authModal = document.getElementById('authModal');
        const mainLayout = document.getElementById('mainLayout');
        
        if (authModal) authModal.classList.remove('modal-active');
        if (mainLayout) mainLayout.style.display = 'flex';
    }
    
    // Show auth modal
    showAuthModal() {
        const authModal = document.getElementById('authModal');
        const mainLayout = document.getElementById('mainLayout');
        
        if (authModal) authModal.classList.add('modal-active');
        if (mainLayout) mainLayout.style.display = 'none';
    }
    
    // Restore session from session storage
    async restoreSession() {
        const sessionId = SessionStorage.getSessionId();
        
        if (sessionId) {
            this.currentSession = {
                sessionId: sessionId,
                authMethod: 'restored'
            };
            
            // Try to verify session is still valid
            try {
                const response = await apiRequest('/devices', {
                    method: 'GET',
                    params: {
                        session_id: sessionId
                    }
                });
                
                this.devices = response.devices;
                this.showMainLayout();
                this.populateDeviceSelect();
            } catch (error) {
                // Session expired
                this.logout();
            }
        }
    }
    
    // Logout user
    async logout() {
        if (this.currentSession) {
            try {
                await apiRequest('/logout', {
                    method: 'POST',
                    params: {
                        session_id: this.currentSession.sessionId
                    }
                });
            } catch (error) {
                console.error('Error during logout:', error);
            }
        }
        
        this.currentSession = null;
        this.devices = [];
        SessionStorage.clearAll();
        this.showAuthModal();
        // Session cleared - HMAC keys will be loaded from environment on next auth attempt
    }
    
    // Get current session ID
    getSessionId() {
        return this.currentSession ? this.currentSession.sessionId : null;
    }
    
    // Get selected device ID (returns string alphanumeric ID)
    getSelectedDeviceId() {
        const select = document.getElementById('deviceSelect');
        return select && select.value ? select.value : null;  // Return string ID, not parsed int
    }
}

// Create global auth manager instance
const authManager = new AuthManager();
