/**
 * NEWAY SECURITY CCTV CLOCKING SYSTEM
 * Dashboard Utilities
 * 
 * This file contains utility functions for the dashboard interface.
 */

// Namespace for dashboard utilities
const NewaySecurity = {
    // Configuration
    config: {
        refreshInterval: 30000, // 30 seconds
        statusCheckInterval: 60000, // 1 minute
        reconnectAttempts: 3,
        timeoutDelay: 2000
    },
    
    // Cache for DOM elements
    elements: {},
    
    // System state
    state: {
        cameraConnected: false,
        systemActive: false,
        lastUpdate: null,
        recognizedFaces: {},
        recentEvents: []
    },
    
    /**
     * Initialize the dashboard
     */
    init: function() {
        console.log("Initializing NEWAY SECURITY dashboard utilities...");
        
        // Cache DOM elements
        this.cacheElements();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Initialize status indicators
        this.StatusManager.init();
        
        // Start refresh timers
        this.startRefreshTimers();
        
        // Initialize tooltips and popovers
        this.initBootstrapComponents();
        
        console.log("Dashboard utilities initialized");
    },
    
    /**
     * Cache commonly used DOM elements
     */
    cacheElements: function() {
        // Video feed elements
        this.elements.videoFeed = document.getElementById('video-stream');
        this.elements.videoContainer = document.getElementById('video-container');
        this.elements.videoStatus = document.querySelector('.video-status');
        
        // Recent events elements
        this.elements.recentEvents = document.getElementById('recent-events');
        
        // Status indicators
        this.elements.cameraStatus = document.querySelector('.camera-status');
        this.elements.systemStatus = document.querySelector('.system-status');
        
        // Statistics elements
        this.elements.recognitionCount = document.getElementById('total-recognitions');
        this.elements.employeeCount = document.getElementById('employee-count');
    },
    
    /**
     * Set up event listeners
     */
    setupEventListeners: function() {
        // Video feed error handling
        if (this.elements.videoFeed) {
            this.elements.videoFeed.addEventListener('error', this.handleVideoError.bind(this));
            this.elements.videoFeed.addEventListener('load', this.handleVideoLoad.bind(this));
        }
        
        // Employee management events
        this.EmployeeManager.setupEventListeners();
        
        // Dashboard tab switching
        const tabButtons = document.querySelectorAll('[data-bs-toggle="tab"]');
        if (tabButtons.length > 0) {
            tabButtons.forEach(button => {
                button.addEventListener('shown.bs.tab', this.handleTabChange.bind(this));
            });
        }
        
        // Handle window resize
        window.addEventListener('resize', this.handleResize.bind(this));
        
        // Handle visibility change (tab switching)
        document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));
    },
    
    /**
     * Start refresh timers for data updates
     */
    startRefreshTimers: function() {
        // Refresh recent events
        setInterval(() => {
            this.refreshRecentEvents();
        }, this.config.refreshInterval);
        
        // Check system status
        setInterval(() => {
            this.StatusManager.checkStatus();
        }, this.config.statusCheckInterval);
    },
    
    /**
     * Initialize Bootstrap components
     */
    initBootstrapComponents: function() {
        // Initialize tooltips
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        if (tooltips.length > 0) {
            tooltips.forEach(tooltip => {
                new bootstrap.Tooltip(tooltip);
            });
        }
        
        // Initialize popovers
        const popovers = document.querySelectorAll('[data-bs-toggle="popover"]');
        if (popovers.length > 0) {
            popovers.forEach(popover => {
                new bootstrap.Popover(popover);
            });
        }
    },
    
    /**
     * Handle video feed error
     */
    handleVideoError: function(e) {
        console.error("Video feed error:", e);
        this.state.cameraConnected = false;
        this.StatusManager.updateCameraStatus(false);
        
        // Attempt to reconnect
        this.attemptReconnect();
    },
    
    /**
     * Handle video feed load success
     */
    handleVideoLoad: function() {
        console.log("Video feed loaded successfully");
        this.state.cameraConnected = true;
        this.StatusManager.updateCameraStatus(true);
    },
    
    /**
     * Handle tab change
     */
    handleTabChange: function(e) {
        const tabId = e.target.getAttribute('aria-controls');
        console.log(`Tab changed to: ${tabId}`);
        
        // Refresh data based on active tab
        switch (tabId) {
            case 'logs':
                this.DataManager.refreshLogsData();
                break;
            case 'employees':
                this.EmployeeManager.refreshEmployeeList();
                break;
        }
    },
    
    /**
     * Handle window resize
     */
    handleResize: function() {
        // Adjust video container size if needed
        if (this.elements.videoContainer) {
            // Any resize-specific adjustments
        }
    },
    
    /**
     * Handle visibility change (tab switching)
     */
    handleVisibilityChange: function() {
        if (!document.hidden) {
            // Tab is visible again, refresh data
            this.refreshRecentEvents();
            this.StatusManager.checkStatus();
        }
    },
    
    /**
     * Attempt to reconnect to video feed
     */
    attemptReconnect: function() {
        let attempts = 0;
        
        const tryReconnect = () => {
            if (attempts >= this.config.reconnectAttempts) {
                console.error("Failed to reconnect after multiple attempts");
                return;
            }
            
            attempts++;
            console.log(`Attempting to reconnect (${attempts}/${this.config.reconnectAttempts})...`);
            
            // Update status indicator
            if (this.elements.videoStatus) {
                this.elements.videoStatus.innerHTML = `<i class="fas fa-sync fa-spin"></i> Reconnecting (${attempts}/${this.config.reconnectAttempts})...`;
            }
            
            // Reload the video stream with a new timestamp to bypass cache
            if (this.elements.videoFeed) {
                const currentSrc = this.elements.videoFeed.src.split('?')[0];
                this.elements.videoFeed.src = `${currentSrc}?t=${Date.now()}`;
            }
            
            // Check again after delay
            setTimeout(() => {
                if (!this.state.cameraConnected) {
                    tryReconnect();
                }
            }, this.config.timeoutDelay * attempts); // Increasing delay
        };
        
        // Start reconnection attempts
        tryReconnect();
    },
    
    /**
     * Refresh recent events display
     */
    refreshRecentEvents: function() {
        if (!this.elements.recentEvents) return;
        
        // Fetch latest events
        fetch('/api/logs?limit=10')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update state
                    this.state.recentEvents = data.events;
                    
                    // Update display
                    this.updateRecentEventsDisplay(data.events);
                }
            })
            .catch(error => {
                console.error("Error fetching recent events:", error);
            });
    },
    
    /**
     * Update the recent events display
     */
    updateRecentEventsDisplay: function(events) {
        if (!this.elements.recentEvents || !events || !events.length) return;
        
        // Clear current content
        this.elements.recentEvents.innerHTML = '';
        
        // Add events
        events.forEach(event => {
            const eventItem = document.createElement('div');
            eventItem.className = 'recent-event-item';
            
            // Format time (Today or date)
            const eventDate = new Date(`${event.Date} ${event.Time}`);
            const now = new Date();
            const isToday = eventDate.toDateString() === now.toDateString();
            const timeStr = isToday ? 
                `Today, ${eventDate.toLocaleTimeString()}` : 
                eventDate.toLocaleString();
            
            // Set content
            eventItem.innerHTML = `
                <div class="recent-event-time">${timeStr}</div>
                <div class="recent-event-name">${event.Name}</div>
                <div class="recent-event-type">
                    <span class="badge ${event.Event === 'IN' ? 'bg-success' : 'bg-secondary'}">
                        ${event.Event === 'IN' ? 'Clock In' : 'Clock Out'}
                    </span>
                </div>
            `;
            
            // Add to container
            this.elements.recentEvents.appendChild(eventItem);
        });
        
        // Update statistics if available
        if (this.elements.recognitionCount) {
            this.elements.recognitionCount.textContent = events.length;
        }
    },
    
    /**
     * Status Management Submodule
     */
    StatusManager: {
        // Reference to parent
        parent: null,
        
        // Status indicators
        indicators: {},
        
        /**
         * Initialize status manager
         */
        init: function() {
            // Set parent reference
            this.parent = NewaySecurity;
            
            // Find status indicators
            this.indicators = {
                camera: document.querySelector('.status-indicator.camera-status'),
                system: document.querySelector('.status-indicator.system-status'),
                network: document.querySelector('.status-indicator.network-status')
            };
            
            // Initial status check
            this.checkStatus();
        },
        
        /**
         * Check all system statuses
         */
        checkStatus: function() {
            // Check camera status
            this.updateCameraStatus(this.parent.state.cameraConnected);
            
            // Check system status via API
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        this.updateSystemStatus(data.status);
                        this.updateNetworkStatus(data.network);
                    }
                })
                .catch(error => {
                    console.error("Error checking system status:", error);
                    this.updateSystemStatus(false);
                    this.updateNetworkStatus(false);
                });
        },
        
        /**
         * Update camera status indicator
         */
        updateCameraStatus: function(isConnected) {
            if (!this.indicators.camera) return;
            
            if (isConnected) {
                this.indicators.camera.classList.remove('status-offline');
                this.indicators.camera.classList.add('status-online');
                this.indicators.camera.setAttribute('title', 'Camera Connected');
            } else {
                this.indicators.camera.classList.remove('status-online');
                this.indicators.camera.classList.add('status-offline');
                this.indicators.camera.setAttribute('title', 'Camera Disconnected');
            }
        },
        
        /**
         * Update system status indicator
         */
        updateSystemStatus: function(status) {
            if (!this.indicators.system) return;
            
            this.indicators.system.classList.remove('status-online', 'status-offline', 'status-warning');
            
            switch (status) {
                case 'online':
                    this.indicators.system.classList.add('status-online');
                    this.indicators.system.setAttribute('title', 'System Online');
                    break;
                case 'warning':
                    this.indicators.system.classList.add('status-warning');
                    this.indicators.system.setAttribute('title', 'System Warning');
                    break;
                case 'offline':
                    this.indicators.system.classList.add('status-offline');
                    this.indicators.system.setAttribute('title', 'System Offline');
                    break;
            }
        },
        
        /**
         * Update network status indicator
         */
        updateNetworkStatus: function(status) {
            if (!this.indicators.network) return;
            
            if (status) {
                this.indicators.network.classList.remove('status-offline');
                this.indicators.network.classList.add('status-online');
                this.indicators.network.setAttribute('title', 'Network Connected');
            } else {
                this.indicators.network.classList.remove('status-online');
                this.indicators.network.classList.add('status-offline');
                this.indicators.network.setAttribute('title', 'Network Disconnected');
            }
        }
    },
    
    /**
     * Employee Management Submodule
     */
    EmployeeManager: {
        // Reference to parent
        parent: null,
        
        /**
         * Set up event listeners for employee management
         */
        setupEventListeners: function() {
            // Set parent reference
            this.parent = NewaySecurity;
            
            // Add employee form
            const addEmployeeForm = document.getElementById('add-employee-form');
            if (addEmployeeForm) {
                addEmployeeForm.addEventListener('submit', this.handleAddEmployee.bind(this));
            }
            
            // Update employee form
            const updateEmployeeForm = document.getElementById('update-employee-form');
            if (updateEmployeeForm) {
                updateEmployeeForm.addEventListener('submit', this.handleUpdateEmployee.bind(this));
            }
            
            // Delete employee buttons
            const deleteButtons = document.querySelectorAll('.delete-employee');
            if (deleteButtons.length > 0) {
                deleteButtons.forEach(button => {
                    button.addEventListener('click', this.handleDeleteEmployee.bind(this));
                });
            }
            
            // Image preview on file selection
            const fileInputs = document.querySelectorAll('input[type="file"]');
            if (fileInputs.length > 0) {
                fileInputs.forEach(input => {
                    input.addEventListener('change', this.handleFileSelection.bind(this));
                });
            }
        },
        
        /**
         * Handle adding a new employee
         */
        handleAddEmployee: function(e) {
            e.preventDefault();
            const form = e.target;
            
            // Form validation
            if (!form.checkValidity()) {
                form.classList.add('was-validated');
                return;
            }
            
            // Get form data
            const formData = new FormData(form);
            
            // Show loading state
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
            submitButton.disabled = true;
            
            // Submit form
            fetch('/api/add_employee', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message
                    this.showNotification('success', `Employee ${formData.get('name')} added successfully!`);
                    
                    // Close modal and reset form
                    const modal = bootstrap.Modal.getInstance(document.getElementById('addEmployeeModal'));
                    if (modal) {
                        modal.hide();
                    }
                    form.reset();
                    
                    // Refresh employee list
                    this.refreshEmployeeList();
                } else {
                    // Show error message
                    this.showNotification('danger', `Error: ${data.error}`);
                }
            })
            .catch(error => {
                console.error("Error adding employee:", error);
                this.showNotification('danger', "An error occurred while adding the employee");
            })
            .finally(() => {
                // Restore button
                submitButton.innerHTML = originalText;
                submitButton.disabled = false;
            });
        },
        
        /**
         * Handle updating an employee
         */
        handleUpdateEmployee: function(e) {
            e.preventDefault();
            const form = e.target;
            
            // Similar to add employee but with update logic
            // ...
        },
        
        /**
         * Handle deleting an employee
         */
        handleDeleteEmployee: function(e) {
            const button = e.target.closest('.delete-employee');
            const name = button.dataset.name;
            
            if (confirm(`Are you sure you want to delete ${name}? This action cannot be undone.`)) {
                // Show loading state
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                button.disabled = true;
                
                // Submit delete request
                fetch('/api/delete_employee', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ name })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success message
                        this.showNotification('success', `Employee ${name} deleted successfully!`);
                        
                        // Remove employee card
                        const employeeCard = button.closest('.employee-card').parentElement;
                        employeeCard.remove();
                    } else {
                        // Show error message
                        this.showNotification('danger', `Error: ${data.error}`);
                        
                        // Restore button
                        button.innerHTML = '<i class="fas fa-trash-alt"></i> Delete';
                        button.disabled = false;
                    }
                })
                .catch(error => {
                    console.error("Error deleting employee:", error);
                    this.showNotification('danger', "An error occurred while deleting the employee");
                    
                    // Restore button
                    button.innerHTML = '<i class="fas fa-trash-alt"></i> Delete';
                    button.disabled = false;
                });
            }
        },
        
        /**
         * Handle file selection for image preview
         */
        handleFileSelection: function(e) {
            const input = e.target;
            const previewContainer = document.getElementById('preview-container');
            
            if (!previewContainer) return;
            
            // Clear preview container
            previewContainer.innerHTML = '';
            
            // Create preview for each selected file
            for (let i = 0; i < input.files.length; i++) {
                const file = input.files[i];
                
                // Only process image files
                if (!file.type.match('image.*')) continue;
                
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    const preview = document.createElement('div');
                    preview.className = 'image-preview';
                    preview.innerHTML = `
                        <img src="${e.target.result}" class="preview-image" alt="Preview">
                        <div class="image-name">${file.name}</div>
                    `;
                    previewContainer.appendChild(preview);
                };
                
                reader.readAsDataURL(file);
            }
        },
        
        /**
         * Refresh the employee list
         */
        refreshEmployeeList: function() {
            // This would typically reload the page or fetch updated employee data
            // For simplicity, we'll just reload the page
            window.location.reload();
        },
        
        /**
         * Show a notification message
         */
        showNotification: function(type, message) {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `alert alert-${type} alert-dismissible fade show`;
            notification.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            
            // Add to page
            document.querySelector('.main-content').prepend(notification);
            
            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                const alert = bootstrap.Alert.getInstance(notification);
                if (alert) {
                    alert.close();
                } else {
                    notification.remove();
                }
            }, 5000);
        }
    },
    
    /**
     * Data Management Submodule
     */
    DataManager: {
        // Reference to parent
        parent: null,
        
        // Data tables
        tables: {},
        
        /**
         * Initialize data tables
         */
        initDataTables: function() {
            // Set parent reference
            this.parent = NewaySecurity;
            
            // Initialize logs table
            const logsTable = document.getElementById('logs-table');
            if (logsTable) {
                this.tables.logs = new DataTable(logsTable, {
                    responsive: true,
                    order: [[1, 'desc'], [2, 'desc']]
                });
            }
            
            // Initialize summary table
            const summaryTable = document.getElementById('summary-table');
            if (summaryTable) {
                this.tables.summary = new DataTable(summaryTable, {
                    responsive: true
                });
            }
        },
        
        /**
         * Refresh logs data
         */
        refreshLogsData: function() {
            // Get filter values
            const startDate = document.getElementById('date-range-start')?.value;
            const endDate = document.getElementById('date-range-end')?.value;
            const employee = document.getElementById('employee-filter')?.value;
            
            // Build query parameters
            const params = new URLSearchParams();
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            if (employee) params.append('name', employee);
            
            // Fetch logs data
            fetch(`/api/logs?${params.toString()}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && this.tables.logs) {
                        // Clear existing data
                        this.tables.logs.clear();
                        
                        // Add new data
                        if (data.events.length > 0) {
                            this.tables.logs.rows.add(data.events).draw();
                        } else {
                            this.tables.logs.draw();
                        }
                    }
                })
                .catch(error => {
                    console.error("Error fetching logs data:", error);
                });
        },
        
        /**
         * Refresh summary data
         */
        refreshSummaryData: function() {
            // Get date parameter
            const date = document.getElementById('summary-date')?.value || new Date().toISOString().split('T')[0];
            
            // Fetch summary data
            fetch(`/api/daily_summary?date=${date}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && this.tables.summary) {
                        // Clear existing data
                        this.tables.summary.clear();
                        
                        // Add new data
                        if (data.summary.length > 0) {
                            this.tables.summary.rows.add(data.summary).draw();
                        } else {
                            this.tables.summary.draw();
                        }
                    }
                })
                .catch(error => {
                    console.error("Error fetching summary data:", error);
                });
        },
        
        /**
         * Export data to CSV
         */
        exportToCSV: function(tableId, filename) {
            const table = document.getElementById(tableId);
            if (!table) return;
            
            // Get headers
            const headers = [];
            table.querySelectorAll('thead th').forEach(th => {
                headers.push(th.textContent);
            });
            
            // Get rows
            const rows = [];
            table.querySelectorAll('tbody tr').forEach(tr => {
                const row = [];
                tr.querySelectorAll('td').forEach(td => {
                    row.push(td.textContent);
                });
                rows.push(row);
            });
            
            // Combine headers and rows
            const csvContent = [
                headers.join(','),
                ...rows.map(row => row.join(','))
            ].join('\n');
            
            // Create download link
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', filename || 'export.csv');
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }
};

// Initialize on document ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard utilities
    NewaySecurity.init();
    
    // Initialize data tables if available
    if (typeof DataTable !== 'undefined') {
        NewaySecurity.DataManager.initDataTables();
    }
});

