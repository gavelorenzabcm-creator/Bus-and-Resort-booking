(function() {
    'use strict';

    // Fetch timeout wrapper
    async function fetchWithTimeout(url, options = {}, timeout = 10000) {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(id);
            return response;
        } catch (error) {
            clearTimeout(id);
            throw error;
        }
    }

    window.NotificationManager = {
        unreadCount: 0,
        notifications: [],
        pollInterval: null,
        isDropdownOpen: false,
        lastFetchTime: 0,
        isFetching: false,
        consecutiveErrors: 0,
        maxConsecutiveErrors: 5,

        // DOM element references
        getElements: function() {
            return {
                bell: document.getElementById('notification-bell'),
                dropdown: document.getElementById('notification-dropdown'),
                badge: document.getElementById('notification-badge'),
                dropdownCount: document.getElementById('dropdown-count'),
                list: document.getElementById('notification-list'),
                markAllBtn: document.getElementById('mark-all-read')
            };
        },

        // Fetch notifications from backend with timeout
        fetchNotifications: async function() {
            // Prevent concurrent fetches
            if (this.isFetching) return;
            
            // Don't fetch too frequently (min 3 seconds between requests)
            const now = Date.now();
            if (now - this.lastFetchTime < 3000) return;
            
            this.isFetching = true;
            this.lastFetchTime = now;
            
            try {
                const response = await fetchWithTimeout('/api/admin/notifications', {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }, 10000); // 10 second timeout
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                this.notifications = data.notifications || [];
                this.unreadCount = data.unread_count || 0;
                this.consecutiveErrors = 0; // Reset error count on success
                this.updateBadge();
                if (this.isDropdownOpen) {
                    this.loadNotifications();
                }
            } catch (err) {
                this.consecutiveErrors++;
                console.warn(`Failed to fetch notifications (${this.consecutiveErrors}/${this.maxConsecutiveErrors}):`, err.message);
                
                // Stop polling after too many consecutive errors
                if (this.consecutiveErrors >= this.maxConsecutiveErrors) {
                    console.error('Too many consecutive errors, stopping notification polling');
                    this.stopPolling();
                    this.showErrorState();
                }
            } finally {
                this.isFetching = false;
            }
        },

        // Show error state in UI
        showErrorState: function() {
            const els = this.getElements();
            if (els.badge) {
                els.badge.textContent = '!';
                els.badge.classList.remove('hidden');
                els.badge.classList.add('bg-gray-500');
            }
        },

        // Update badge visibility and count
        updateBadge: function() {
            const els = this.getElements();
            if (els.badge) {
                if (this.unreadCount > 0) {
                    els.badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
                    els.badge.classList.remove('hidden');
                } else {
                    els.badge.classList.add('hidden');
                }
            }
            if (els.dropdownCount) {
                els.dropdownCount.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
            }
        },

        // Render notification list into dropdown
        loadNotifications: function() {
            const els = this.getElements();
            if (!els.list) return;

            if (this.notifications.length === 0) {
                els.list.innerHTML = `
                    <div class="p-8 text-center text-gray-500">
                        <i class="fas fa-bell-slash text-4xl mb-3 opacity-60 block mx-auto"></i>
                        <p class="text-sm font-medium">No notifications</p>
                        <p class="text-xs mt-1">Bookings and feedback will appear here</p>
                    </div>
                `;
                return;
            }

            els.list.innerHTML = this.notifications.map(n => {
                const time = n.date_created ? n.date_created.slice(0, 16).replace('T', ' ') : 'Just now';
                const message = this.escapeHtml(n.message || 'Notification');
                const redirectUrl = n.redirect_url || '/dashboard';
                const icon = n.type === 'booking_bus' ? 'fa-bus' : 
                             n.type === 'booking_resort' ? 'fa-bed' : 
                             n.type === 'cancel_bus' ? 'fa-ban' :
                             n.type === 'cancel_resort' ? 'fa-ban' : 'fa-star';
                const iconColor = n.type === 'booking_bus' ? 'text-blue-600' : 
                                  n.type === 'booking_resort' ? 'text-green-600' : 
                                  n.type === 'cancel_bus' ? 'text-red-600' :
                                  n.type === 'cancel_resort' ? 'text-red-600' : 'text-yellow-500';
                const isUnread = !n.is_read;
                const unreadBg = isUnread ? 'bg-blue-50/70 border-l-4 border-blue-500' : 'hover:bg-gray-50';
                const titleWeight = isUnread ? 'font-bold' : 'font-semibold';
                const unreadDot = isUnread ? '<span class="ml-2 w-2 h-2 bg-blue-500 rounded-full inline-block flex-shrink-0" title="Unread"></span>' : '';
                return `
                    <div class="group p-4 border-b border-gray-100 ${unreadBg} transition-all duration-150 cursor-pointer" data-notif-id="${n.id}" data-redirect-url="${redirectUrl}">
                        <div class="flex items-start gap-3">
                            <div class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center ${iconColor} mt-0.5">
                                <i class="fas ${icon} text-sm"></i>
                            </div>
                            <div class="flex-1 min-w-0 pr-2">
                                <div class="flex items-center">
                                    <p class="${titleWeight} text-gray-900 text-sm leading-tight">${message}</p>
                                    ${unreadDot}
                                </div>
                                <p class="text-xs text-gray-500 mt-1">${time}</p>
                            </div>
                            <div class="flex flex-col gap-1 items-center">
                                <button type="button" class="mark-read-btn flex-shrink-0 text-gray-400 hover:text-blue-600 transition-colors" data-notif-id="${n.id}" title="Mark as read">
                                    <i class="fas fa-check-circle"></i>
                                </button>
                                <button type="button" class="delete-btn flex-shrink-0 text-gray-400 hover:text-red-600 transition-colors" data-notif-id="${n.id}" title="Delete">
                                    <i class="fas fa-trash-alt text-xs"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Attach click handlers to mark-read buttons
            els.list.querySelectorAll('.mark-read-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const notifId = btn.dataset.notifId;
                    this.markRead(notifId);
                });
            });

            // Attach click handlers to delete buttons
            els.list.querySelectorAll('.delete-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const notifId = btn.dataset.notifId;
                    this.deleteNotification(notifId);
                });
            });

            // Attach click handlers to notification items for navigation
            els.list.querySelectorAll('[data-notif-id]').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.mark-read-btn') || e.target.closest('.delete-btn')) return;
                    const redirectUrl = item.dataset.redirectUrl;
                    this.markAllRead().then(() => {
                        if (redirectUrl && redirectUrl !== '#') {
                            window.location.href = redirectUrl;
                        }
                    });
                });
            });
        },

        // Mark single notification as read
        markRead: async function(notifId) {
            try {
                const response = await fetchWithTimeout(`/admin/notifications/mark-read/${notifId}`, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }, 10000);
                if (response.ok) {
                    const notif = this.notifications.find(n => n.id == notifId);
                    if (notif && !notif.is_read) {
                        notif.is_read = 1;
                        this.unreadCount = Math.max(0, this.unreadCount - 1);
                        this.updateBadge();
                        this.loadNotifications();
                    }
                }
            } catch (err) {
                console.error('Mark read failed:', err);
            }
        },

        // Delete notification permanently
        deleteNotification: async function(notifId) {
            try {
                const response = await fetchWithTimeout(`/api/admin/notifications/${notifId}`, {
                    method: 'DELETE',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }, 10000);
                if (response.ok) {
                    const notif = this.notifications.find(n => n.id == notifId);
                    this.notifications = this.notifications.filter(n => n.id != notifId);
                    if (notif && !notif.is_read) {
                        this.unreadCount = Math.max(0, this.unreadCount - 1);
                    }
                    this.updateBadge();
                    this.loadNotifications();
                }
            } catch (err) {
                console.error('Delete notification failed:', err);
            }
        },

        // Mark all notifications as read
        markAllRead: async function() {
            try {
                const response = await fetchWithTimeout('/api/admin/notifications/mark-all-read', {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }, 10000);
                if (response.ok) {
                    this.notifications.forEach(n => n.is_read = 1);
                    this.unreadCount = 0;
                    this.updateBadge();
                    this.loadNotifications();
                }
            } catch (err) {
                console.error('Mark all read failed:', err);
            }
        },

        // Toggle dropdown visibility (with animation classes)
        toggleDropdown: function() {
            const els = this.getElements();
            if (!els.dropdown) return;

            const isOpen = els.dropdown.classList.contains('open');
            if (isOpen) {
                els.dropdown.classList.remove('open');
                els.dropdown.classList.add('hidden');
                this.isDropdownOpen = false;
            } else {
                els.dropdown.classList.remove('hidden');
                els.dropdown.classList.add('open');
                this.isDropdownOpen = true;
                this.loadNotifications();
            }
        },

        // Close dropdown when clicking outside
        closeDropdown: function(e) {
            const els = this.getElements();
            if (!els.dropdown || !els.bell) return;
            if (!els.dropdown.contains(e.target) && !els.bell.contains(e.target)) {
                els.dropdown.classList.remove('open');
                els.dropdown.classList.add('hidden');
                this.isDropdownOpen = false;
            }
        },


        // Start polling for new notifications
        startPolling: function() {
            // Clear any existing interval first
            this.stopPolling();
            // Initial fetch
            this.fetchNotifications();
            // Set up polling with longer interval (10 seconds)
            this.pollInterval = setInterval(() => {
                this.fetchNotifications();
            }, 10000); // Poll every 10 seconds (reduced from 5)
        },

        // Stop polling
        stopPolling: function() {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }
        },

        // Escape HTML to prevent XSS
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        // Initialize the notification system
        init: function() {
            const els = this.getElements();
            if (!els.bell || !els.dropdown) {
                console.warn('Notification elements not found');
                return;
            }

            // Bell click handler
            els.bell.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDropdown();
            });

            // Mark all as read button
            if (els.markAllBtn) {
                els.markAllBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.markAllRead();
                });
            }

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                this.closeDropdown(e);
            });

            // Start polling
            this.startPolling();
        }
    };

    // Auto-init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.NotificationManager.init());
    } else {
        window.NotificationManager.init();
    }
})();

