/**
 * Chat module for FC Assist
 */

class ChatManager {
    constructor() {
        this.messages = [];
        this.isLoading = false;
    }
    
    // Initialize chat
    init() {
        this.setupEventListeners();
        this.setupQuickQueryButtons();
    }
    
    // Setup event listeners
    setupEventListeners() {
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        const deviceSelect = document.getElementById('deviceSelect');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        if (userInput) {
            userInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Auto-expand textarea
            userInput.addEventListener('input', () => {
                userInput.style.height = 'auto';
                userInput.style.height = Math.min(userInput.scrollHeight, 250) + 'px';
            });
        }
        
        if (deviceSelect) {
            // Can use device select to filter queries
        }
    }
    
    // Setup quick query button handlers
    setupQuickQueryButtons() {
        const quickQueryButtons = document.querySelectorAll('.quick-query-btn');
        const userInput = document.getElementById('userInput');
        
        if (!userInput || quickQueryButtons.length === 0) return;
        
        quickQueryButtons.forEach(button => {
            button.addEventListener('click', () => {
                const query = button.getAttribute('data-query');
                if (query) {
                    // Insert query into textarea
                    userInput.value = query;
                    
                    // Focus textarea
                    userInput.focus();
                    
                    // Auto-expand textarea
                    userInput.style.height = 'auto';
                    userInput.style.height = Math.min(userInput.scrollHeight, 250) + 'px';
                    
                    // Scroll to input area
                    userInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    
                    // Optional: Auto-send after short delay
                    setTimeout(() => {
                        this.sendMessage();
                    }, 300);
                }
            });
        });
    }
    
    // Send message
    async sendMessage() {
        const userInput = document.getElementById('userInput');
        if (!userInput) return;
        
        const message = userInput.value.trim();
        if (!message) return;
        
        // Check if user is authenticated
        const sessionId = authManager.getSessionId();
        if (!sessionId) {
            // Display error in chat
            this.addMessage('❌ Please authenticate first', 'bot');
            return;
        }
        
        // Get selected device
        const deviceId = authManager.getSelectedDeviceId();
        
        // Validate device is selected
        if (!deviceId) {
            // Display error in chat
            this.addMessage('❌ Please select or type a device ID from the dropdown before querying', 'bot');
            return;
        }
        
        // Add user message to chat
        this.addMessage(message, 'user');
        
        // Clear input
        userInput.value = '';
        
        // Send query to backend
        this.queryBackend(sessionId, message, deviceId);
    }
    
    // Query backend
    async queryBackend(sessionId, message, deviceId) {
        this.isLoading = true;
        const sendBtn = document.getElementById('sendBtn');
        
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.textContent = 'Loading...';
        }
        
        try {
            const response = await apiRequest('/query', {
                method: 'POST',
                data: {
                    session_id: sessionId,
                    user_message: message,
                    device_id: deviceId
                }
            });
            
            // Check if this is a licenses or sensors query
            const messageLower = message.toLowerCase();
            const isLicenseQuery = messageLower.includes('license') || messageLower.includes('license');
            const isSensorQuery = messageLower.includes('sensor') || messageLower.includes('available');
            
            // Handle licenses grid
            if (isLicenseQuery && response.query_result) {
                // Check if response contains license data
                const licenseData = response.query_result.license_data || 
                                  response.query_result.licenses_data ||
                                  response.query_result.licenses;
                if (licenseData) {
                    this.addLicensesGridMessage(licenseData, response.bot_message);
                } else {
                    // Fall back to regular message
                    this.addMessage(response.bot_message, 'bot');
                    if (response.query_result && response.query_result.table_data) {
                        this.addTableMessage(response.query_result.table_data);
                    } else if (response.query_result && response.query_result.formatted_text) {
                        this.addMessage(response.query_result.formatted_text, 'data');
                    }
                }
            } 
            // Handle sensors grid
            else if (isSensorQuery && response.query_result) {
                // Check if response contains sensor data
                const sensorData = response.query_result.sensor_data || 
                                 response.query_result.sensors_data ||
                                 response.query_result.sensors;
                if (sensorData) {
                    this.addSensorsGridMessage(sensorData, response.bot_message);
                } else {
                    // Fall back to regular message
                    this.addMessage(response.bot_message, 'bot');
                    if (response.query_result && response.query_result.table_data) {
                        this.addTableMessage(response.query_result.table_data);
                    } else if (response.query_result && response.query_result.formatted_text) {
                        this.addMessage(response.query_result.formatted_text, 'data');
                    }
                }
            }
            // Default handling
            else {
                // Add bot message
                this.addMessage(response.bot_message, 'bot');
                
                // If there's table data, render it
                if (response.query_result && response.query_result.table_data) {
                    this.addTableMessage(response.query_result.table_data);
                } else if (response.query_result && response.query_result.formatted_text) {
                    this.addMessage(response.query_result.formatted_text, 'data');
                }
            }
        } catch (error) {
            this.addMessage(`❌ Error: ${error.message}`, 'bot');
        } finally {
            this.isLoading = false;
            
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
            }
        }
    }
    
    // Add message to chat
    addMessage(text, type = 'bot') {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;
        
        // Create message element
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (type === 'user') {
            messageDiv.classList.add('user-message');
            contentDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;
        } else if (type === 'bot') {
            messageDiv.classList.add('bot-message');
            // Format markdown-style text (preserve line breaks)
            const formattedText = text
                .split('\n')
                .map(line => `<p>${escapeHtml(line) || '&nbsp;'}</p>`)
                .join('');
            contentDiv.innerHTML = formattedText;
        } else if (type === 'data') {
            messageDiv.classList.add('bot-message');
            const preDiv = document.createElement('div');
            preDiv.className = 'message-data';
            preDiv.innerHTML = `<pre>${escapeHtml(text)}</pre>`;
            contentDiv.appendChild(preDiv);
        }
        
        messageDiv.appendChild(contentDiv);
        
        // Add copy button in message-actions wrapper
        if (type !== 'user') {
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            
            const copyBtn = document.createElement('button');
            copyBtn.className = 'btn-copy';
            copyBtn.title = 'Copy message';
            copyBtn.innerHTML = '📋 Copy';
            copyBtn.addEventListener('click', () => this.copyMessageToClipboard(text, copyBtn));
            
            actionsDiv.appendChild(copyBtn);
            messageDiv.appendChild(actionsDiv);
        }
        
        // Add timestamp
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        messageDiv.appendChild(timeSpan);
        
        chatMessages.appendChild(messageDiv);
        
        // Auto-scroll to bottom
        setTimeout(() => {
            scrollToBottom(chatMessages);
        }, 100);
        
        this.messages.push({
            text,
            type,
            timestamp: new Date(),
            element: messageDiv
        });
    }
    
    // Copy message text to clipboard
    copyMessageToClipboard(text, button) {
        navigator.clipboard.writeText(text).then(() => {
            const originalHTML = button.innerHTML;
            button.innerHTML = '✓ Copied';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }
    // Add table data message to chat
    addTableMessage(tableData) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages || !tableData.tables || tableData.tables.length === 0) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot-message';
        
        const tableContainer = document.createElement('div');
        tableContainer.className = 'message-table-container p-3';
        
        // Add context header (device ID, date range, data type)
        if (tableData.device_id || tableData.date_range || tableData.data_type) {
            const contextHeader = document.createElement('div');
            contextHeader.className = 'table-context-header mb-3 pb-3 border-bottom';
            
            let contextHTML = '<div class="d-flex flex-wrap gap-3" style="font-size: 13px;">';
            
            if (tableData.device_id) {
                contextHTML += `
                    <div>
                        <strong class="text-muted">Device:</strong>
                        <span class="badge bg-primary ms-2">${escapeHtml(tableData.device_id)}</span>
                    </div>
                `;
            }
            
            if (tableData.date_range) {
                contextHTML += `
                    <div>
                        <strong class="text-muted">Period:</strong>
                        <span class="badge bg-info text-dark ms-2">${escapeHtml(tableData.date_range)}</span>
                    </div>
                `;
            }
            
            if (tableData.data_type) {
                contextHTML += `
                    <div>
                        <strong class="text-muted">Type:</strong>
                        <span class="badge bg-secondary ms-2">${tableData.data_type.toUpperCase()}</span>
                    </div>
                `;
            }
            
            contextHTML += '</div>';
            contextHeader.innerHTML = contextHTML;
            tableContainer.appendChild(contextHeader);
        }
        
        tableData.tables.forEach(table => {
            const tableWrapper = document.createElement('div');
            tableWrapper.className = 'mb-4';
            
            // Table title with Badge
            const titleDiv = document.createElement('div');
            titleDiv.className = 'mb-2';
            titleDiv.innerHTML = `
                <h6 class="mb-2">
                    <span class="badge bg-info text-dark">${table.data_type.toUpperCase()}</span>
                    <span class="ms-2">${escapeHtml(table.name)}</span>
                    <span class="badge bg-secondary ms-2">${escapeHtml(table.unit || 'N/A')}</span>
                </h6>
            `;
            tableWrapper.appendChild(titleDiv);
            
            // Create Bootstrap table
            const table_elem = document.createElement('table');
            table_elem.className = 'table table-striped table-bordered table-hover table-sm';
            
            // Create header
            const thead = document.createElement('thead');
            thead.className = 'table-dark';
            const headerRow = document.createElement('tr');
            table.headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                th.className = 'px-2 py-2';
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table_elem.appendChild(thead);
            
            // Create body
            const tbody = document.createElement('tbody');
            table.rows.forEach((row, idx) => {
                const tr = document.createElement('tr');
                
                row.forEach((cell, colIdx) => {
                    const td = document.createElement('td');
                    td.textContent = cell;
                    td.className = 'px-2 py-2';
                    if (colIdx === 0) {
                        td.className += ' fw-bold text-muted';
                    } else {
                        td.className += ' text-end';
                    }
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
            table_elem.appendChild(tbody);
            
            tableWrapper.appendChild(table_elem);
            tableContainer.appendChild(tableWrapper);
        });
        
        messageDiv.appendChild(tableContainer);
        
        // Add copy button for table data
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn-copy btn-copy-table';
        copyBtn.title = 'Copy table data';
        copyBtn.innerHTML = '<i class="icon-copy">📋</i>';
        copyBtn.addEventListener('click', () => this.copyTableToClipboard(tableData, copyBtn));
        messageDiv.appendChild(copyBtn);
        
        // Add timestamp
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        messageDiv.appendChild(timeSpan);
        
        chatMessages.appendChild(messageDiv);
        
        // Auto-scroll to bottom
        setTimeout(() => {
            scrollToBottom(chatMessages);
        }, 100);
    }
    
    // Copy table data to clipboard as TSV/CSV format
    copyTableToClipboard(tableData, button) {
        let csvContent = '';
        
        // Add header with context
        if (tableData.device_id) {
            csvContent += `Device: ${tableData.device_id}\n`;
        }
        if (tableData.date_range) {
            csvContent += `Period: ${tableData.date_range}\n`;
        }
        if (tableData.data_type) {
            csvContent += `Type: ${tableData.data_type}\n`;
        }
        csvContent += '\n';
        
        // Add each table as TSV (tab-separated for Excel compatibility)
        tableData.tables.forEach((table, tableIdx) => {
            if (tableIdx > 0) csvContent += '\n';
            csvContent += `${table.name} (${table.unit})\n`;
            
            // Headers
            csvContent += table.headers.join('\t') + '\n';
            
            // Rows
            table.rows.forEach(row => {
                csvContent += row.join('\t') + '\n';
            });
        });
        
        navigator.clipboard.writeText(csvContent).then(() => {
            const originalHTML = button.innerHTML;
            button.innerHTML = '<i class="icon-check">✓</i>';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }

    // Add licenses grid message to chat
    addLicensesGridMessage(licensesData, botMessageText) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;
        
        // First add the bot message
        this.addMessage(botMessageText, 'bot');
        
        // Create licenses grid message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot-message';
        
        const gridContainer = document.createElement('div');
        gridContainer.className = 'message-table-container p-3';
        
        const title = document.createElement('h6');
        title.className = 'mb-3';
        title.innerHTML = '<span class="badge bg-info text-dark">LICENSES</span>';
        gridContainer.appendChild(title);
        
        const gridDiv = document.createElement('div');
        gridDiv.className = 'grid-container';
        
        // Parse licenses data
        const licenses = this.parseLicensesData(licensesData);
        
        licenses.forEach(license => {
            const gridItem = document.createElement('div');
            gridItem.className = 'grid-item';
            
            const header = document.createElement('div');
            header.className = 'grid-item-header';
            header.innerHTML = `
                <span class="grid-item-badge ${license.status === 'active' ? 'license-active' : 'license-expired'}">
                    ${license.status.toUpperCase()}
                </span>
            `;
            gridItem.appendChild(header);
            
            const content = document.createElement('div');
            content.className = 'grid-item-content';
            content.innerHTML = `
                <div class="grid-item-row">
                    <span class="grid-item-label">Type</span>
                    <span class="grid-item-value">${escapeHtml(license.type)}</span>
                </div>
                <div class="grid-item-row">
                    <span class="grid-item-label">From</span>
                    <span class="grid-item-value">${license.from}</span>
                </div>
                <div class="grid-item-row">
                    <span class="grid-item-label">To</span>
                    <span class="grid-item-value">${license.to}</span>
                </div>
                <div class="grid-item-row">
                    <span class="grid-item-label">Days Remaining</span>
                    <span class="grid-item-value">${license.daysRemaining}</span>
                </div>
            `;
            gridItem.appendChild(content);
            gridDiv.appendChild(gridItem);
        });
        
        gridContainer.appendChild(gridDiv);
        messageDiv.appendChild(gridContainer);
        
        // Add copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn-copy btn-copy-table';
        copyBtn.title = 'Copy licenses data';
        copyBtn.innerHTML = '📋 Copy';
        copyBtn.addEventListener('click', () => this.copyLicensesData(licenses, copyBtn));
        messageDiv.appendChild(copyBtn);
        
        // Add timestamp
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        messageDiv.appendChild(timeSpan);
        
        chatMessages.appendChild(messageDiv);
        
        // Auto-scroll to bottom
        setTimeout(() => {
            scrollToBottom(chatMessages);
        }, 100);
    }

    // Parse and format licenses data
    parseLicensesData(licensesData) {
        const licenses = [];
        const now = new Date();
        
        if (typeof licensesData === 'string') {
            try {
                licensesData = JSON.parse(licensesData);
            } catch (e) {
                return licenses;
            }
        }
        
        // Process each license type
        for (const [type, items] of Object.entries(licensesData)) {
            if (Array.isArray(items)) {
                items.forEach(item => {
                    if (item.from && item.to) {
                        const toDate = new Date(item.to);
                        const daysRemaining = Math.ceil((toDate - now) / (1000 * 60 * 60 * 24));
                        const status = daysRemaining > 0 ? 'active' : 'expired';
                        
                        licenses.push({
                            type: type.replace(/([A-Z])/g, ' $1').trim(),
                            from: new Date(item.from).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
                            to: toDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
                            daysRemaining: status === 'active' ? `${daysRemaining} days` : 'Expired',
                            status: status
                        });
                    }
                });
            } else if (typeof items === 'object' && items !== null) {
                // Handle nested license objects like models: { Asparagus: [...] }
                for (const [subType, subItems] of Object.entries(items)) {
                    if (Array.isArray(subItems)) {
                        subItems.forEach(item => {
                            if (item.from && item.to) {
                                const toDate = new Date(item.to);
                                const daysRemaining = Math.ceil((toDate - now) / (1000 * 60 * 60 * 24));
                                const status = daysRemaining > 0 ? 'active' : 'expired';
                                
                                licenses.push({
                                    type: `${type} - ${subType}`,
                                    from: new Date(item.from).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
                                    to: toDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
                                    daysRemaining: status === 'active' ? `${daysRemaining} days` : 'Expired',
                                    status: status
                                });
                            }
                        });
                    }
                }
            }
        }
        
        return licenses;
    }

    // Copy licenses data to clipboard
    copyLicensesData(licenses, button) {
        let csvContent = 'License Type,From Date,To Date,Status,Days Remaining\n';
        licenses.forEach(lic => {
            csvContent += `"${lic.type}","${lic.from}","${lic.to}","${lic.status}","${lic.daysRemaining}"\n`;
        });
        
        navigator.clipboard.writeText(csvContent).then(() => {
            const originalHTML = button.innerHTML;
            button.innerHTML = '✓ Copied';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }

    // Add sensors grid message to chat
    addSensorsGridMessage(sensorsData, botMessageText) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;
        
        // First add the bot message
        this.addMessage(botMessageText, 'bot');
        
        // Create sensors grid message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot-message';
        
        const gridContainer = document.createElement('div');
        gridContainer.className = 'message-table-container p-3';
        
        const title = document.createElement('h6');
        title.className = 'mb-3';
        title.innerHTML = '<span class="badge bg-info text-dark">AVAILABLE SENSORS</span>';
        gridContainer.appendChild(title);
        
        const gridDiv = document.createElement('div');
        gridDiv.className = 'sensors-table-grid';
        
        // Parse sensors data
        const sensors = this.parseSensorsData(sensorsData);
        
        sensors.forEach(sensor => {
            const sensorCard = document.createElement('div');
            sensorCard.className = 'sensor-card';
            
            sensorCard.innerHTML = `
                <div class="sensor-card-name">📊 ${escapeHtml(sensor.name)}</div>
                <div class="sensor-card-type">${escapeHtml(sensor.type)}</div>
            `;
            
            gridDiv.appendChild(sensorCard);
        });
        
        gridContainer.appendChild(gridDiv);
        messageDiv.appendChild(gridContainer);
        
        // Add copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn-copy btn-copy-table';
        copyBtn.title = 'Copy sensors list';
        copyBtn.innerHTML = '📋 Copy';
        copyBtn.addEventListener('click', () => this.copySensorsData(sensors, copyBtn));
        messageDiv.appendChild(copyBtn);
        
        // Add timestamp
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        messageDiv.appendChild(timeSpan);
        
        chatMessages.appendChild(messageDiv);
        
        // Auto-scroll to bottom
        setTimeout(() => {
            scrollToBottom(chatMessages);
        }, 100);
    }

    // Parse and format sensors data
    parseSensorsData(sensorsData) {
        const sensors = [];
        
        if (typeof sensorsData === 'string') {
            try {
                sensorsData = JSON.parse(sensorsData);
            } catch (e) {
                // If it's a plain string with sensor names, split by common delimiters
                const names = sensorsData.split(/,|;|\n/).map(s => s.trim()).filter(s => s);
                return names.map(name => ({
                    name: name,
                    type: 'Sensor'
                }));
            }
        }
        
        if (Array.isArray(sensorsData)) {
            sensorsData.forEach(sensor => {
                if (typeof sensor === 'string') {
                    sensors.push({
                        name: sensor,
                        type: 'Sensor'
                    });
                } else if (typeof sensor === 'object' && sensor.name) {
                    sensors.push({
                        name: sensor.name,
                        type: sensor.type || 'Sensor'
                    });
                }
            });
        } else if (typeof sensorsData === 'object') {
            for (const [name, details] of Object.entries(sensorsData)) {
                sensors.push({
                    name: name,
                    type: typeof details === 'string' ? details : 'Sensor'
                });
            }
        }
        
        return sensors;
    }

    // Copy sensors data to clipboard
    copySensorsData(sensors, button) {
        let csvContent = 'Sensor Name,Type\n';
        sensors.forEach(sensor => {
            csvContent += `"${sensor.name}","${sensor.type}"\n`;
        });
        
        navigator.clipboard.writeText(csvContent).then(() => {
            const originalHTML = button.innerHTML;
            button.innerHTML = '✓ Copied';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }
    
    // Clear chat history
    clearHistory() {
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.innerHTML = '';
        }
        this.messages = [];
    }
}

// Create global chat manager instance
const chatManager = new ChatManager();
