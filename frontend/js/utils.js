/**
 * Utility functions for FC Assist frontend
 */

const API_BASE = 'http://localhost:8000/api';

// Format date for display
function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleString();
    } catch {
        return dateString;
    }
}

// Format timestamp to readable date
function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

// Parse date string to Date object
function parseDate(dateStr) {
    try {
        return new Date(dateStr);
    } catch {
        return null;
    }
}

// Display error message
function showError(message, containerId = 'authError') {
    const container = document.getElementById(containerId);
    if (container) {
        container.textContent = message;
        container.style.display = 'block';
    }
}

// Hide error message
function hideError(containerId = 'authError') {
    const container = document.getElementById(containerId);
    if (container) {
        container.style.display = 'none';
    }
}

// Show loading indicator
function showLoading(containerId = 'authLoading') {
    const container = document.getElementById(containerId);
    if (container) {
        container.style.display = 'flex';
        container.style.justifyContent = 'center';
        container.style.gap = '8px';
        container.innerHTML = '<div class="loading"></div> Processing...';
    }
}

// Hide loading indicator
function hideLoading(containerId = 'authLoading') {
    const container = document.getElementById(containerId);
    if (container) {
        container.style.display = 'none';
    }
}

// Make API request
async function apiRequest(endpoint, options = {}) {
    const method = options.method || 'GET';
    const url = new URL(API_BASE + endpoint, window.location.origin);
    
    // Add query parameters for GET requests
    if (method === 'GET' && options.params) {
        Object.entries(options.params).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                url.searchParams.append(key, value);
            }
        });
    }
    
    const config = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    // Add body for POST requests
    if (method === 'POST' && options.data) {
        config.body = JSON.stringify(options.data);
    }
    
    try {
        const response = await fetch(url, config);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `API error: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        throw error;
    }
}

// Session storage helpers (NO localStorage - cleared on tab close)
const SessionStorage = {
    setSessionId(sessionId) {
        sessionStorage.setItem('fc_session_id', sessionId);
    },
    
    getSessionId() {
        return sessionStorage.getItem('fc_session_id');
    },
    
    clearSessionId() {
        sessionStorage.removeItem('fc_session_id');
    },
    
    isAuthenticated() {
        return !!this.getSessionId();
    },
    
    clearAll() {
        sessionStorage.clear();
    }
};

// Debounce function for input
function debounce(func, delay = 300) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Scroll to bottom of element
function scrollToBottom(element) {
    element.scrollTop = element.scrollHeight;
}

// Check if element is scrolled to bottom
function isScrolledToBottom(element) {
    return element.scrollHeight - element.clientHeight <= element.scrollTop + 1;
}
