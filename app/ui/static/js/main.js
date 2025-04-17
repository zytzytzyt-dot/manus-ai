document.addEventListener('DOMContentLoaded', function() {
    // Navigation
    const navLinks = document.querySelectorAll('nav ul li a');
    const panels = document.querySelectorAll('.panel');
    
    // Initialize the application
    init();
    
    // Add navigation event listeners
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Update active state
            navLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            // Show corresponding panel
            const targetId = this.id.replace('nav-', '') + '-panel';
            panels.forEach(panel => {
                panel.classList.add('hidden');
                if (panel.id === targetId) {
                    panel.classList.remove('hidden');
                }
            });
            
            // Load panel data
            if (targetId === 'tasks-panel') {
                loadTasks();
            } else if (targetId === 'agents-panel') {
                loadAgents();
            } else if (targetId === 'tools-panel') {
                loadTools();
            } else if (targetId === 'settings-panel') {
                loadSettings();
            } else if (targetId === 'dashboard-panel') {
                updateDashboard();
            }
        });
    });
    
    // Task submission
    document.getElementById('submit-task').addEventListener('click', function() {
        const taskDescription = document.getElementById('task-description').value.trim();
        if (taskDescription) {
            createTask(taskDescription);
        } else {
            alert('Please enter a task description');
        }
    });
    
    // Task filters
    document.getElementById('apply-filters').addEventListener('click', function() {
        loadTasks();
    });
    
    // Pagination
    document.getElementById('prev-page').addEventListener('click', function() {
        if (currentPage > 1) {
            currentPage--;
            loadTasks();
        }
    });
    
    document.getElementById('next-page').addEventListener('click', function() {
        if (currentPage < totalPages) {
            currentPage++;
            loadTasks();
        }
    });
    
    // Back button in task detail
    document.getElementById('back-to-tasks').addEventListener('click', function() {
        document.getElementById('task-detail-panel').classList.add('hidden');
        document.getElementById('tasks-panel').classList.remove('hidden');
    });
    
    // Settings save
    document.getElementById('save-settings').addEventListener('click', function() {
        saveSettings();
    });
    
    // Global state
    let currentPage = 1;
    let totalPages = 1;
    
    // Initialize the application
    function init() {
        updateDashboard();
    }
    
    // Dashboard update
    function updateDashboard() {
        // Update statistics
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                document.getElementById('stat-system-status').textContent = data.status;
            })
            .catch(error => console.error('Error fetching status:', error));
        
        // Get task counts
        fetch('/api/tasks?limit=0')
            .then(response => response.json())
            .then(data => {
                const activeCount = data.tasks.filter(task => 
                    task.metadata.status === 'pending' || task.metadata.status === 'processing'
                ).length;
                
                const completedCount = data.tasks.filter(task => 
                    task.metadata.status === 'completed'
                ).length;
                
                const successRate = data.tasks.length > 0 
                    ? Math.round((completedCount / data.tasks.length) * 100) 
                    : 0;
                
                document.getElementById('stat-active-tasks').textContent = activeCount;
                document.getElementById('stat-completed-tasks').textContent = completedCount;
                document.getElementById('stat-success-rate').textContent = `${successRate}%`;
                
                // Load recent tasks
                loadRecentTasks(data.tasks.slice(0, 5));
            })
            .catch(error => console.error('Error fetching tasks:', error));
    }
    
    // Load recent tasks for dashboard
    function loadRecentTasks(tasks) {
        const tasksContainer = document.getElementById('recent-tasks-list');
        tasksContainer.innerHTML = '';
        
        if (tasks.length === 0) {
            tasksContainer.innerHTML = '<p class="empty-list">No tasks found</p>';
            return;
        }
        
        tasks.forEach(task => {
            const taskElement = createTaskElement(task);
            tasksContainer.appendChild(taskElement);
        });
    }
    
    // Load all tasks with filtering
    function loadTasks() {
        const statusFilter = document.getElementById('filter-status').value;
        const tagFilter = document.getElementById('filter-tag').value;
        
        const limit = 10;
        const offset = (currentPage - 1) * limit;
        
        let url = `/api/tasks?limit=${limit}&offset=${offset}`;
        
        if (statusFilter !== 'all') {
            url += `&status=${statusFilter}`;
        }
        
        if (tagFilter) {
            url += `&tag=${tagFilter}`;
        }
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                const tasksContainer = document.getElementById('tasks-list');
                tasksContainer.innerHTML = '';
                
                if (data.tasks.length === 0) {
                    tasksContainer.innerHTML = '<p class="empty-list">No tasks found</p>';
                    return;
                }
                
                data.tasks.forEach(task => {
                    const taskElement = createTaskElement(task);
                    tasksContainer.appendChild(taskElement);
                });
                
                // Update pagination
                totalPages = Math.ceil(data.total / limit);
                document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
                
                // Update button states
                document.getElementById('prev-page').disabled = currentPage <= 1;
                document.getElementById('next-page').disabled = currentPage >= totalPages;
            })
            .catch(error => console.error('Error fetching tasks:', error));
    }
    
    // Create a task element
    function createTaskElement(task) {
        const taskItem = document.createElement('div');
        taskItem.className = 'task-item';
        taskItem.dataset.id = task.id;
        
        const statusClass = task.metadata.status || 'pending';
        
        taskItem.innerHTML = `
            <div class="task-info">
                <h4>${truncateText(task.description, 60)}</h4>
                <div class="task-meta">
                    <span>Created: ${formatDate(task.created_at)}</span>
                    <span>Priority: ${task.priority}</span>
                </div>
            </div>
            <div class="task-status ${statusClass}">${statusClass}</div>
        `;
        
        // Add click event to show task details
        taskItem.addEventListener('click', function() {
            showTaskDetails(task.id);
        });
        
        return taskItem;
    }
    
    // Show task details
    function showTaskDetails(taskId) {
        fetch(`/api/tasks/${taskId}`)
            .then(response => response.json())
            .then(task => {
                // Fill task details
                document.getElementById('detail-description').textContent = task.description;
                document.getElementById('detail-status').textContent = task.metadata.status || 'pending';
                document.getElementById('detail-created').textContent = formatDate(task.created_at);
                document.getElementById('detail-priority').textContent = task.priority;
                document.getElementById('detail-tags').textContent = task.tags.join(', ') || 'None';
                
                // Get task results
                fetch(`/api/tasks/${taskId}/results`)
                    .then(response => response.json())
                    .then(resultsData => {
                        // Show execution steps
                        const stepsContainer = document.getElementById('execution-steps');
                        stepsContainer.innerHTML = '';
                        
                        // Process execution steps from metadata if available
                        const steps = task.metadata.steps || [];
                        steps.forEach((step, index) => {
                            const stepElement = document.createElement('div');
                            stepElement.className = 'execution-step';
                            stepElement.innerHTML = `
                                <div class="step-header">
                                    <span>Step ${index + 1}: ${step.name || 'Execution'}</span>
                                    <span class="step-status ${step.status || 'pending'}">${step.status || 'pending'}</span>
                                </div>
                                <div class="step-content">${step.description || 'No details available'}</div>
                            `;
                            stepsContainer.appendChild(stepElement);
                        });
                        
                        // Show results
                        const resultsContainer = document.getElementById('task-results');
                        if (resultsData.results && resultsData.results.length > 0) {
                            resultsContainer.textContent = resultsData.results[0].content;
                        } else {
                            resultsContainer.textContent = 'No results available yet';
                        }
                        
                        // Show task detail panel
                        document.getElementById('tasks-panel').classList.add('hidden');
                        document.getElementById('task-detail-panel').classList.remove('hidden');
                    })
                    .catch(error => console.error('Error fetching results:', error));
            })
            .catch(error => console.error('Error fetching task details:', error));
    }
    
    // Create a new task
    function createTask(description) {
        const taskData = {
            description: description,
            priority: 0,
            tags: []
        };
        
        fetch('/api/tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(taskData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.task_id) {
                // Clear input
                document.getElementById('task-description').value = '';
                
                // Show success message
                alert('Task created successfully!');
                
                // Update dashboard
                updateDashboard();
            } else {
                alert('Failed to create task: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error creating task:', error);
            alert('Failed to create task: ' + error.message);
        });
    }
    
    // Load agents
    function loadAgents() {
        fetch('/api/agents')
            .then(response => response.json())
            .then(data => {
                const agentsContainer = document.getElementById('agents-list');
                agentsContainer.innerHTML = '';
                
                if (!data.agents || data.agents.length === 0) {
                    agentsContainer.innerHTML = '<p class="empty-list">No agents found</p>';
                    return;
                }
                
                data.agents.forEach(agent => {
                    const agentElement = document.createElement('div');
                    agentElement.className = 'agent-card';
                    agentElement.innerHTML = `
                        <h3>${agent.name}</h3>
                        <p>${agent.description || 'No description available'}</p>
                    `;
                    agentsContainer.appendChild(agentElement);
                });
            })
            .catch(error => console.error('Error fetching agents:', error));
    }
    
    // Load tools
    function loadTools() {
        fetch('/api/tools')
            .then(response => response.json())
            .then(data => {
                const toolsContainer = document.getElementById('tools-list');
                toolsContainer.innerHTML = '';
                
                if (!data.tools || data.tools.length === 0) {
                    toolsContainer.innerHTML = '<p class="empty-list">No tools found</p>';
                    return;
                }
                
                data.tools.forEach(tool => {
                    const toolElement = document.createElement('div');
                    toolElement.className = 'tool-card';
                    toolElement.innerHTML = `
                        <h3>${tool.name}</h3>
                        <p>${tool.description || 'No description available'}</p>
                    `;
                    toolsContainer.appendChild(toolElement);
                });
            })
            .catch(error => console.error('Error fetching tools:', error));
    }
    
    // Load settings
    function loadSettings() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                // For demonstration, we're using status endpoint
                document.getElementById('setting-workspace').value = '/app/workspace';
                document.getElementById('setting-debug').checked = data.debug || false;
                document.getElementById('setting-llm-model').value = 'gpt-4o';
                document.getElementById('setting-llm-temperature').value = '0.0';
            })
            .catch(error => console.error('Error fetching settings:', error));
    }
    
    // Save settings
    function saveSettings() {
        // In a real implementation, this would send the settings to the server
        alert('Settings saved!');
    }
    
    // Helper functions
    function formatDate(dateString) {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-US', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    }
    
    function truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
});