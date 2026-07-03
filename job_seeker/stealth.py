"""
Browser stealth configuration to avoid bot detection.
Provides realistic browser fingerprints for Playwright.
"""
import os

STEALTH_SCRIPT = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Override chrome
window.chrome = { runtime: {} };

// Override permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Override plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5].map(() => ({ name: 'Chrome PDF Plugin' })),
});

// Override languages
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

// Override platform
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

// Override hardwareConcurrency
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

// Override deviceMemory
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// WebGL vendor
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter(parameter);
};
"""


def get_browser_config():
    """Return common browser launch and context arguments."""
    return {
        "launch_args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            f"--window-size=1920,1080",
        ],
        "context_args": {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "geolocation": {"latitude": 39.9042, "longitude": 116.4074},
            "permissions": ["geolocation"],
        },
        "stealth_script": STEALTH_SCRIPT,
    }
