/**
 * Main application initialization
 */

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initApp();
});

function initApp() {
    // Initialize auth manager
    authManager.init();
    
    // Initialize chat manager
    chatManager.init();
    
    // Setup logout button
    setupLogoutButton();
    
    // Check if already authenticated
    if (SessionStorage.isAuthenticated()) {
        authManager.showMainLayout();
        authManager.loadDevices();
    } else {
        authManager.showAuthModal();
    }
}

function setupLogoutButton() {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to logout?')) {
                await authManager.logout();
                chatManager.clearHistory();
            }
        });
    }
}

// Handle unload event
window.addEventListener('unload', function() {
    // Session storage is automatically cleared on tab close
    // This is by design - no credentials persist
});
