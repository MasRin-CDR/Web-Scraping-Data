"""
utils/stealth.py — Advanced Stealth & Anti-Detection Utilities

Kumpulan script JavaScript untuk menghilangkan semua indikator otomasi Playwright/Chromium:
- webdriver flag
- HeadlessChrome UA fingerprint
- navigator.plugins (kosong di headless)
- navigator.permissions
- WebGL renderer
- AudioContext fingerprint
- Screen resolution spoofing
- chrome.runtime injection
"""

from __future__ import annotations

import random
from typing import Optional


# ─── Core Stealth Script (injected via add_init_script) ──────────────────────

STEALTH_INIT_SCRIPT = """
// ── 1. Remove webdriver flag ────────────────────────────────────────────────
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});

// ── 2. Realistic plugins ─────────────────────────────────────────────────────
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const makePlugin = (name, desc, filename, mimeTypes) => {
            const plugin = Object.create(Plugin.prototype);
            Object.defineProperties(plugin, {
                name:     { value: name,     enumerable: true },
                description: { value: desc,  enumerable: true },
                filename: { value: filename, enumerable: true },
                length:   { value: mimeTypes.length, enumerable: true },
            });
            mimeTypes.forEach((mt, i) => {
                const mimeType = Object.create(MimeType.prototype);
                Object.defineProperties(mimeType, {
                    type:        { value: mt.type, enumerable: true },
                    description: { value: mt.desc, enumerable: true },
                    suffixes:    { value: mt.suffixes || '', enumerable: true },
                });
                plugin[i] = mimeType;
                plugin[mt.type] = mimeType;
            });
            return plugin;
        };

        const plugins = [
            makePlugin(
                'PDF Viewer', 'Portable Document Format',
                'internal-pdf-viewer',
                [{ type: 'application/pdf', desc: 'Portable Document Format', suffixes: 'pdf' },
                 { type: 'text/pdf', desc: 'Portable Document Format', suffixes: 'pdf' }]
            ),
            makePlugin(
                'Chrome PDF Viewer', 'Portable Document Format',
                'internal-pdf-viewer',
                [{ type: 'application/pdf', desc: 'Portable Document Format', suffixes: 'pdf' }]
            ),
            makePlugin(
                'Chromium PDF Viewer', 'Portable Document Format',
                'internal-pdf-viewer',
                [{ type: 'application/pdf', desc: 'Portable Document Format', suffixes: 'pdf' }]
            ),
            makePlugin(
                'Microsoft Edge PDF Viewer', 'Portable Document Format',
                'internal-pdf-viewer',
                [{ type: 'application/pdf', desc: 'Portable Document Format', suffixes: 'pdf' }]
            ),
            makePlugin(
                'WebKit built-in PDF', 'Portable Document Format',
                'internal-pdf-viewer',
                [{ type: 'application/pdf', desc: 'Portable Document Format', suffixes: 'pdf' }]
            ),
        ];

        const pluginArray = Object.create(PluginArray.prototype);
        plugins.forEach((p, i) => {
            pluginArray[i] = p;
            pluginArray[p.name] = p;
        });
        Object.defineProperty(pluginArray, 'length', { value: plugins.length });
        pluginArray.item      = (i) => plugins[i];
        pluginArray.namedItem = (n) => plugins.find(p => p.name === n) || null;
        pluginArray.refresh   = () => {};
        return pluginArray;
    },
    enumerable: true,
    configurable: true,
});

// ── 3. Realistic MIME types ──────────────────────────────────────────────────
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const types = [
            { type: 'application/pdf', description: 'Portable Document Format', suffixes: 'pdf' },
            { type: 'text/pdf', description: 'Portable Document Format', suffixes: 'pdf' },
        ];
        const mimeArray = Object.create(MimeTypeArray.prototype);
        types.forEach((t, i) => {
            const mt = Object.create(MimeType.prototype);
            Object.assign(mt, t);
            mimeArray[i] = mt;
            mimeArray[t.type] = mt;
        });
        Object.defineProperty(mimeArray, 'length', { value: types.length });
        return mimeArray;
    },
    enumerable: true,
    configurable: true,
});

// ── 4. Languages ─────────────────────────────────────────────────────────────
Object.defineProperty(navigator, 'languages', {
    get: () => ['id-ID', 'id', 'en-US', 'en'],
    enumerable: true,
    configurable: true,
});

// ── 5. Permissions override ──────────────────────────────────────────────────
const _origPermQuery = window.navigator.permissions.query.bind(navigator.permissions);
window.navigator.permissions.query = (params) => {
    if (params.name === 'notifications') {
        return Promise.resolve({ state: Notification.permission, onchange: null });
    }
    return _origPermQuery(params);
};

// ── 6. chrome.runtime injection ──────────────────────────────────────────────
if (!window.chrome) {
    window.chrome = {
        runtime: {
            connect:          () => {},
            sendMessage:      () => {},
            onMessage:        { addListener: () => {}, removeListener: () => {} },
            id:               undefined,
            lastError:        undefined,
        },
        loadTimes: () => ({
            firstPaintTime: Math.random() * 2,
            requestTime:    Date.now() / 1000 - Math.random(),
            startLoadTime:  Date.now() / 1000 - Math.random() * 2,
        }),
        csi: () => ({
            startE:     Date.now() - Math.floor(Math.random() * 3000),
            onloadT:    Date.now() - Math.floor(Math.random() * 1000),
            pageT:      Math.random() * 3000,
            tran:       15,
        }),
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
        },
    };
}

// ── 7. WebGL Vendor/Renderer spoofing ────────────────────────────────────────
const getParameter_orig = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Google Inc. (Intel)';
    if (parameter === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    return getParameter_orig.call(this, parameter);
};

const getParameter2_orig = WebGL2RenderingContext.prototype.getParameter;
WebGL2RenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Google Inc. (Intel)';
    if (parameter === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    return getParameter2_orig.call(this, parameter);
};

// ── 8. Remove HeadlessChrome from UA (belt-and-suspenders) ──────────────────
Object.defineProperty(navigator, 'userAgent', {
    get: () => navigator.userAgent.replace('HeadlessChrome', 'Chrome'),
    configurable: true,
});

// ── 9. Hardware concurrency (realistic) ──────────────────────────────────────
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: true,
});

// ── 10. Device memory (realistic) ────────────────────────────────────────────
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: true,
});

// ── 11. Connection (realistic) ────────────────────────────────────────────────
if (navigator.connection) {
    Object.defineProperties(navigator.connection, {
        effectiveType: { get: () => '4g', configurable: true },
        downlink:      { get: () => 10,  configurable: true },
        rtt:           { get: () => 50,  configurable: true },
        saveData:      { get: () => false, configurable: true },
    });
}

// ── 12. window.outerHeight/outerWidth ────────────────────────────────────────
if (window.outerHeight === 0) {
    Object.defineProperty(window, 'outerHeight', {
        get: () => window.innerHeight + 88,
        configurable: true,
    });
}
if (window.outerWidth === 0) {
    Object.defineProperty(window, 'outerWidth', {
        get: () => window.innerWidth,
        configurable: true,
    });
}
"""


# ─── Extra Evasion Script (optional, inject post-load) ───────────────────────

STEALTH_POST_LOAD_SCRIPT = """
// Realistic mouse movement simulation flag
window._hasRealMouseMovement = true;
window._isHumanLike = true;

// Touch events (some CF checks test for touch)
if (!window.ontouchstart) {
    window.ontouchstart = null;
}
"""


def get_random_viewport() -> dict:
    """Return realistic viewport dimensions."""
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1680, "height": 1050},
        {"width": 1440, "height": 900},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1280, "height": 800},
    ]
    return random.choice(viewports)


def get_random_timezone() -> str:
    """Return realistic Indonesian timezone."""
    return random.choice([
        "Asia/Jakarta",
        "Asia/Makassar",
        "Asia/Jayapura",
    ])


def get_random_locale() -> str:
    """Return realistic locale."""
    return random.choice(["id-ID", "id"])


async def apply_stealth(context) -> None:
    """
    Terapkan semua stealth scripts ke Playwright BrowserContext.
    Dipanggil sekali saat context dibuat.
    """
    await context.add_init_script(STEALTH_INIT_SCRIPT)


async def apply_stealth_to_page(page) -> None:
    """
    Inject stealth post-load script ke page yang sudah ada.
    Opsional — untuk page yang sudah terbuka.
    """
    try:
        await page.evaluate(STEALTH_POST_LOAD_SCRIPT)
    except Exception:
        pass  # Page mungkin sudah closed


def get_extra_http_headers(user_agent: Optional[str] = None) -> dict:
    """Return HTTP headers yang realistis."""
    return {
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-CH-UA": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    }
