// Modal functions - defined at global scope
async function openSubscriptionModal(subId, titleKeyword, bodyKeyword, group) {
    const isEditMode = !!subId;
    const modal = document.getElementById('subscriptionModal');
    const form = document.getElementById('subscriptionModalForm');
    const title = document.getElementById('subscriptionModalTitle');
    const submitBtn = document.getElementById('subscriptionSubmitBtn');
    const groupsHint = document.getElementById('groupsHint');

    const groups = await fetchAvailableGroups();
    populateGroupsCheckboxes(groups);

    // Uncheck all checkboxes first
    document.querySelectorAll('.group-checkbox').forEach(cb => {
        cb.checked = false;
    });

    if (isEditMode) {
        title.textContent = 'Edit Subscription';
        submitBtn.textContent = 'Update Subscription';
        groupsHint.textContent = 'Change the group for this subscription';
        // Check the current group's checkbox
        const checkbox = document.querySelector(`[value="${group}"]`);
        if (checkbox) {
            checkbox.checked = true;
        }
    } else {
        title.textContent = 'Create Subscription';
        submitBtn.textContent = 'Create Subscription';
        groupsHint.textContent = 'Select one or more groups';
    }

    document.getElementById('subscription-id').value = subId || '';
    document.getElementById('keyword-title').value = titleKeyword || '';
    document.getElementById('keyword-body').value = bodyKeyword || '';
    document.getElementById('subscriptionModalStatus').style.display = 'none';
    modal.classList.add('active');
}

function closeSubscriptionModal() {
    const modal = document.getElementById('subscriptionModal');
    const form = document.getElementById('subscriptionModalForm');
    modal.classList.remove('active');
    form.reset();
    document.getElementById('subscription-id').value = '';
    document.getElementById('subscriptionModalStatus').style.display = 'none';
}

function editSubscription(subId, titleKeyword, bodyKeyword, group) {
    openSubscriptionModal(subId, titleKeyword, bodyKeyword, group);
}

function openCreateModal() {
    openSubscriptionModal();
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tab switching
    initializeTabSwitching();

    // Load available groups and user profile data
    loadProfileData();

    // Load profile form
    document.getElementById('profileForm').addEventListener('submit', async function(e) {
        e.preventDefault();

        const phoneNumber = document.getElementById('phone_number').value.trim();
        const defaultGroup = document.getElementById('default_group').value.trim();
        const statusMessage = document.getElementById('statusMessage');

        try {
            const response = await fetch('/api/user/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    phone_number: phoneNumber || null,
                    default_group: defaultGroup || null
                })
            });

            const data = await response.json();

            if (response.ok) {
                statusMessage.textContent = '✓ Profile updated successfully';
                statusMessage.className = 'status-message success';
                statusMessage.style.display = 'block';
                setTimeout(() => {
                    statusMessage.style.display = 'none';
                }, 3000);
            } else {
                statusMessage.textContent = '✗ Error: ' + data.error;
                statusMessage.className = 'status-message error';
                statusMessage.style.display = 'block';
            }
        } catch (error) {
            statusMessage.textContent = '✗ Error updating profile: ' + error.message;
            statusMessage.className = 'status-message error';
            statusMessage.style.display = 'block';
        }
    });

    // Load notifications
    loadUserNotifications();

    // Toggle for expired notifications
    document.getElementById('expiredToggle').addEventListener('click', function(e) {
        e.preventDefault();
        this.classList.toggle('active');
        this.querySelector('.toggle-slider').classList.toggle('active');
        loadUserNotifications();
    });

    // Subscription modal form submission (handles both create and edit)
    const subscriptionForm = document.getElementById('subscriptionModalForm');
    const subscriptionModal = document.getElementById('subscriptionModal');
    const modalClose = subscriptionModal.querySelector('.modal-close');
    const modalCancel = document.getElementById('subscriptionModalCancelBtn');

    modalClose.addEventListener('click', closeSubscriptionModal);
    modalCancel.addEventListener('click', closeSubscriptionModal);

    if (subscriptionForm) {
        subscriptionForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const subId = document.getElementById('subscription-id').value;
            const keywordTitle = document.getElementById('keyword-title').value.trim();
            const keywordBody = document.getElementById('keyword-body').value.trim();
            const statusDiv = document.getElementById('subscriptionModalStatus');
            const isEditMode = !!subId;

            if (!keywordTitle && !keywordBody) {
                statusDiv.textContent = '✗ Please enter at least one keyword';
                statusDiv.className = 'status-message error';
                statusDiv.style.display = 'block';
                return;
            }

            // Build payload
            const payload = {
                title_keyword: keywordTitle || null,
                body_keyword: keywordBody || null
            };

            // Validate and add mode-specific fields
            let url, method, successMessage;

            const checkedBoxes = document.querySelectorAll('.group-checkbox:checked');
            const selectedGroups = Array.from(checkedBoxes).map(cb => cb.value);

            if (!selectedGroups.length) {
                statusDiv.textContent = '✗ Please select at least one group';
                statusDiv.className = 'status-message error';
                statusDiv.style.display = 'block';
                return;
            }

            if (!isEditMode) {
                // Create mode - send all selected groups
                payload.groups = selectedGroups;
                url = '/api/subscriptions';
                method = 'POST';
                successMessage = '✓ Subscription created successfully';
            } else {
                // Edit mode - send just the first selected group
                payload.group = selectedGroups[0];
                url = `/api/subscriptions/${subId}`;
                method = 'PUT';
                successMessage = '✓ Subscription updated successfully';
            }

            try {
                const response = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    statusDiv.textContent = successMessage;
                    statusDiv.className = 'status-message success';
                    statusDiv.style.display = 'block';
                    loadUserSubscriptions();
                    setTimeout(() => {
                        closeSubscriptionModal();
                    }, 1500);
                } else {
                    const data = await response.json();
                    statusDiv.textContent = '✗ Error: ' + (data.error || 'Unknown error');
                    statusDiv.className = 'status-message error';
                    statusDiv.style.display = 'block';
                }
            } catch (error) {
                statusDiv.textContent = '✗ Error: ' + error.message;
                statusDiv.className = 'status-message error';
                statusDiv.style.display = 'block';
            }
        });
    }

    // Load available groups for subscriptions form
    loadAvailableGroups();
});

function initializeTabSwitching() {
    const tabButtons = document.querySelectorAll('.profile-tab');
    const tabs = document.querySelectorAll('.tab-content');
    const sidebar = document.querySelector('.sidebar');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            switchTab(tabName, tabButtons, tabs, sidebar);
        });
    });

    // Set initial tab state on sidebar
    sidebar.className = sidebar.className.replace(/is-tab-\w+/g, '');
    sidebar.classList.add('is-tab-profile');

    // Load initial notifications
    loadUserNotifications();
}

function switchTab(tabName, tabButtons, tabs, sidebar) {
    try {
        // Update active tab button
        tabButtons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            }
        });

        // Update active tab content
        tabs.forEach(tab => {
            tab.classList.remove('active');
            if (tab.id === tabName) {
                tab.classList.add('active');
            }
        });

        // Update sidebar state for conditional visibility
        sidebar.className = sidebar.className.replace(/is-tab-\w+/g, '');
        sidebar.classList.add(`is-tab-${tabName}`);

        // Load tab content
        if (tabName === 'notifications') {
            loadUserNotifications();
        } else if (tabName === 'subscriptions-list') {
            loadUserSubscriptions();
        }
        // Profile tab has no async loading needed
    } catch (error) {
        console.error('Error switching tab:', error);
        const errorDiv = document.getElementById(tabName + 'TabError');
        if (errorDiv) {
            errorDiv.textContent = 'Error loading tab: ' + error.message;
            errorDiv.style.display = 'block';
        }
    }
}

function loadUserSubscriptions() {
    const subscriptionsList = document.getElementById('subscriptionsList');
    const errorDiv = document.getElementById('subscriptionsListTabError');

    // Reset error message
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }

    fetch('/api/subscriptions')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!subscriptionsList) {
                console.error('subscriptionsList element not found');
                return;
            }
            displaySubscriptions(data.subscriptions || [], subscriptionsList);
        })
        .catch(error => {
            console.error('Error loading subscriptions:', error);
            if (errorDiv) {
                errorDiv.textContent = 'Failed to load subscriptions: ' + error.message;
                errorDiv.style.display = 'block';
            }
            if (subscriptionsList) {
                subscriptionsList.innerHTML = '<p class="error">Failed to load subscriptions</p>';
            }
        });
}

function displaySubscriptions(subscriptions, container) {
    if (!subscriptions || subscriptions.length === 0) {
        container.innerHTML = '<p class="no-subscriptions">No subscriptions yet</p>';
        return;
    }

    let html = '<div class="subscription-items">';
    subscriptions.forEach(sub => {
        const statusClass = `subscription-status ${sub.status}`;
        const keywordDisplay = buildKeywordDisplay(sub.title_keyword, sub.body_keyword);
        html += `
            <div class="subscription-item" data-subscription-id="${sub.id}" data-title-keyword="${escapeHtml(sub.title_keyword || '')}" data-body-keyword="${escapeHtml(sub.body_keyword || '')}" data-group="${escapeHtml(sub.group)}">
                <div class="subscription-item-info">
                    <div class="subscription-keyword">${keywordDisplay}</div>
                    <div class="subscription-group">${escapeHtml(sub.group)}</div>
                    <span class="${statusClass}">${escapeHtml(sub.status)}</span>
                </div>
                <div class="subscription-item-actions">
                    <button class="btn-edit-subscription" data-subscription-id="${sub.id}">Edit</button>
                    <button class="btn-delete-subscription" data-subscription-id="${sub.id}">Delete</button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;

    // Add event listeners for edit and delete buttons
    container.querySelectorAll('.btn-delete-subscription').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const subId = this.dataset.subscriptionId;
            if (confirm('Are you sure you want to delete this subscription?')) {
                deleteSubscription(subId);
            }
        });
    });

    container.querySelectorAll('.btn-edit-subscription').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const subId = this.dataset.subscriptionId;
            const item = container.querySelector(`[data-subscription-id="${subId}"]`);
            const titleKeyword = item.dataset.titleKeyword;
            const bodyKeyword = item.dataset.bodyKeyword;
            const group = item.dataset.group;
            editSubscription(subId, titleKeyword, bodyKeyword, group);
        });
    });
}

function buildKeywordDisplay(titleKeyword, bodyKeyword) {
    const lines = [];
    if (titleKeyword && titleKeyword.trim()) {
        lines.push(`Title: ${escapeHtml(titleKeyword)}`);
    }
    if (bodyKeyword && bodyKeyword.trim()) {
        lines.push(`Body: ${escapeHtml(bodyKeyword)}`);
    }
    return lines.length > 0 ? lines.join('<br>') : '(no keywords)';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function deleteSubscription(subId) {
    fetch(`/api/subscriptions/${subId}`, { method: 'DELETE' })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            loadUserSubscriptions();
        })
        .catch(error => {
            console.error('Error deleting subscription:', error);
            alert('Failed to delete subscription: ' + error.message);
        });
}

function loadUserNotifications() {
    const notificationsList = document.getElementById('notificationsList');
    const expiredToggle = document.getElementById('expiredToggle');
    const includeExpired = expiredToggle.classList.contains('active');
    const url = `/api/user/notifications?include_expired=${includeExpired}`;

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            displayNotifications(data.notifications, notificationsList);
        })
        .catch(error => {
            console.error('Error loading notifications:', error);
            notificationsList.innerHTML = '<p class="error">Failed to load notifications</p>';
        });
}

function displayNotifications(notifications, container) {
    const expiredToggle = document.getElementById('expiredToggle');
    const includeExpired = expiredToggle.classList.contains('active');

    if (!notifications || notifications.length === 0) {
        container.innerHTML = '<p class="no-notifications">No active notifications</p>';
        return;
    }

    // Filter notifications based on expired toggle
    let filteredNotifications = notifications;
    if (includeExpired) {
        // Show only expired (non-pending)
        filteredNotifications = notifications.filter(notif => notif.status !== 'pending');
    } else {
        // Show only pending
        filteredNotifications = notifications.filter(notif => notif.status === 'pending');
    }

    if (!filteredNotifications || filteredNotifications.length === 0) {
        container.innerHTML = '<p class="no-notifications">No active notifications</p>';
        return;
    }

    let html = '<div class="notification-items">';
    filteredNotifications.forEach(notif => {
        const statusClass = `notification-status notification-status-${notif.status}`;

        html += `
            <div class="notification-item" data-event-id="${notif.event_id}">
                <div class="notification-summary">
                    <div class="notification-title-and-date">
                        <div class="notification-title-link" role="button" tabindex="0" data-event-id="${notif.event_id}">
                            ${notif.event_title}
                        </div>
                        <span class="notification-datetime">
                            ${notif.event_date}${notif.event_time ? ' at ' + notif.event_time : ''}
                        </span>
                    </div>
                    <div class="notification-actions-row">
                        <div class="notification-delta-and-status">
                            <span class="notification-label">Notification: ${notif.send_at}</span>
                            <span class="${statusClass}">${notif.status}</span>
                        </div>
                        ${notif.status === 'pending' ? `<button class="btn-remove-notification" data-notification-id="${notif.notification_id}" data-event-id="${notif.event_id}">Remove</button>` : ''}
                    </div>
                </div>
                <div class="notification-details" style="display: none;">
                    <div class="details-content">
                        <div class="loading">Loading event details...</div>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;

    // Add event listeners to notification items for expansion
    container.querySelectorAll('.notification-title-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const eventId = this.dataset.eventId;
            toggleNotificationDetails(eventId, container);
        });

        link.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const eventId = this.dataset.eventId;
                toggleNotificationDetails(eventId, container);
            }
        });
    });

    // Add event listeners to remove buttons
    container.querySelectorAll('.btn-remove-notification').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const eventId = this.dataset.eventId;
            removeNotification(eventId, container);
        });
    });
}

function toggleNotificationDetails(eventId, container) {
    const notifItem = container.querySelector(`[data-event-id="${eventId}"]`);
    const detailsDiv = notifItem.querySelector('.notification-details');
    const detailsContent = notifItem.querySelector('.details-content');

    if (detailsDiv.style.display === 'block') {
        detailsDiv.style.display = 'none';
    } else {
        detailsDiv.style.display = 'block';

        // Load details if not already loaded
        if (!detailsContent.dataset.loaded) {
            loadNotificationDetails(eventId, detailsContent);
        }
    }
}

function loadNotificationDetails(eventId, detailsContent) {
    fetch(`/api/event/${eventId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            displayEventDetails(detailsContent, data);
            detailsContent.dataset.loaded = 'true';
        })
        .catch(error => {
            console.error('Error loading event details:', error);
            detailsContent.innerHTML = `<div class="error">Failed to load details: ${error.message}</div>`;
        });
}

function displayEventDetails(container, data) {
    let html = '<div class="event-detail-content">';

    if (data.categories && data.categories.length > 0) {
        html += `<div class="categories">Categories: ${data.categories.join(', ')}</div>`;
    }

    if (data.location) {
        html += `<div class="location">Location: ${data.location}</div>`;
    }

    if (data.latitude && data.longitude) {
        html += `<div class="coordinates">Coordinates: ${data.latitude}, ${data.longitude}</div>`;
    }

    if (data.description) {
        html += `<div class="description">${data.description}</div>`;
    }

    if (data.detail_url) {
        html += `<div class="detail-link"><a href="${data.detail_url}" target="_blank" rel="noopener">View original event →</a></div>`;
    }

    html += '</div>';
    container.innerHTML = html;
}

function removeNotification(eventId, container) {
    fetch(`/api/events/${eventId}/notifications`, { method: 'DELETE' })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            // Reload notifications after successful removal
            loadUserNotifications();
        })
        .catch(error => {
            console.error('Error removing notification:', error);
            alert('Failed to remove notification');
        });
}

function formatSentAt(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return isoString;
    }
}

async function fetchAvailableGroups() {
    try {
        const response = await fetch('/api/groups');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        return data.groups || [];
    } catch (error) {
        console.error('Error fetching groups:', error);
        return [];
    }
}

function populateGroupsCheckboxes(groups) {
    const groupsContainer = document.getElementById('groups');
    if (!groups || groups.length === 0) {
        groupsContainer.innerHTML = '<p class="error">No groups available</p>';
        return;
    }

    let html = '';
    groups.forEach(group => {
        html += `
            <label>
                <input type="checkbox" class="group-checkbox" value="${group}">
                ${group.charAt(0).toUpperCase() + group.slice(1)}
            </label>
        `;
    });
    groupsContainer.innerHTML = html;
}

function loadAvailableGroups() {
    fetchAvailableGroups().then(groups => {
        populateGroupsCheckboxes(groups);
    });
}

async function loadProfileData() {
    try {
        // Load available groups for the dropdown
        const groups = await fetchAvailableGroups();
        populateDefaultGroupDropdown(groups);

        // Load current user data to pre-select default_group
        const response = await fetch('/api/user');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const userData = await response.json();

        // Pre-select the current default_group if set
        if (userData.default_group) {
            document.getElementById('default_group').value = userData.default_group;
        }
    } catch (error) {
        console.error('Error loading profile data:', error);
    }
}

function populateDefaultGroupDropdown(groups) {
    const dropdown = document.getElementById('default_group');
    if (!dropdown) return;

    // Keep the first option (Choose a group...)
    const firstOption = dropdown.querySelector('option:first-child');

    // Add group options
    groups.forEach(group => {
        const option = document.createElement('option');
        option.value = group;
        option.textContent = group.charAt(0).toUpperCase() + group.slice(1);
        dropdown.appendChild(option);
    });
}
