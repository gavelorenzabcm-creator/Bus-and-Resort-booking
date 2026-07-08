/**
 * Page Loader - Prevents freezing during navigation
 * Handles loading states and prevents duplicate requests
 */
(function() {
    'use strict';

    window.PageLoader = {
        // Track if we're currently navigating
        isNavigating: false,
        
        // Initialize page loader
        init: function() {
            console.log('[PageLoader] Initializing...');
            this.setupNavigationProtection();
            this.setupLoadingIndicator();
            this.forceClearLoading(); // Aggressive clearing on init
        },

        // Force clear any stuck loading states
        forceClearLoading: function() {
            console.log('[PageLoader] Force clearing loading state');
            this.isNavigating = false;
            this.hideLoading();
            
            // Also clear any existing page-loader elements
            const existingLoader = document.getElementById('page-loader-overlay');
            if (existingLoader) {
                existingLoader.style.display = 'none';
            }
            
            // Multiple failsafes
            setTimeout(() => this.hideLoading(), 100);
            setTimeout(() => this.hideLoading(), 500);
            setTimeout(() => this.hideLoading(), 1000);
            setTimeout(() => this.hideLoading(), 2000);
        },

        // Prevent multiple rapid clicks on navigation
        setupNavigationProtection: function() {
            const sidebar = document.querySelector('.admin-sidebar');
            if (!sidebar) {
                console.log('[PageLoader] No sidebar found - skipping nav protection');
                return;
            }

            const links = sidebar.querySelectorAll('a');
            
            links.forEach(link => {
                link.addEventListener('click', (e) => {
                    // If already navigating, prevent the click
                    if (this.isNavigating) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Navigation already in progress, blocking duplicate click');
                        return;
                    }

                    // Mark as navigating
                    this.isNavigating = true;
                    
                    // Show loading state
                    this.showLoading();
                    
                    // Visual feedback on the clicked link
                    link.style.opacity = '0.6';
                    link.style.pointerEvents = 'none';
                    
                    // Reset after 3 seconds (reduced from 5)
                    setTimeout(() => {
                        this.isNavigating = false;
                        link.style.opacity = '';
                        link.style.pointerEvents = '';
                        this.hideLoading();
                    }, 3000);
                });
            });

            // Reset navigation state on both DOMContentLoaded and load
            document.addEventListener('DOMContentLoaded', () => {
                console.log('[PageLoader] DOM ready - clearing loading');
                this.forceClearLoading();
            });

            window.addEventListener('load', () => {
                console.log('[PageLoader] Window loaded - clearing loading');
                this.forceClearLoading();
            });

            // Also reset on beforeunload
            window.addEventListener('beforeunload', () => {
                this.showLoading();
            });
        },

        // Setup loading indicator overlay
        setupLoadingIndicator: function() {
            // Check if loader already exists
            if (document.getElementById('page-loader-overlay')) return;

            const loader = document.createElement('div');
            loader.id = 'page-loader-overlay';
            loader.innerHTML = `
                <div class="page-loader-content">
                    <i class="fas fa-spinner fa-spin fa-2x"></i>
                    <p>Loading...</p>
                </div>
            `;
            loader.style.cssText = `
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 255, 255, 0.9);
                z-index: 9999;
                justify-content: center;
                align-items: center;
                flex-direction: column;
            `;
            
            const style = document.createElement('style');
            style.textContent = `
                #page-loader-overlay .page-loader-content {
                    text-align: center;
                    color: #2563EB;
                }
                #page-loader-overlay .page-loader-content i {
                    margin-bottom: 10px;
                }
                #page-loader-overlay .page-loader-content p {
                    margin: 0;
                    font-size: 14px;
                }
            `;
            document.head.appendChild(style);
            document.body.appendChild(loader);
        },

        // Show loading overlay
        showLoading: function() {
            const loader = document.getElementById('page-loader-overlay');
            if (loader) {
                loader.style.display = 'flex';
            }
        },

        // Hide loading overlay
        hideLoading: function() {
            const loader = document.getElementById('page-loader-overlay');
            if (loader) {
                loader.style.display = 'none';
            }
        }
    };

    // Auto-init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.PageLoader.init());
    } else {
        window.PageLoader.init();
    }
})();
