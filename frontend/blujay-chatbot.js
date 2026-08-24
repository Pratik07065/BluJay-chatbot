/**
 * Blujay Technologies AI Chatbot Widget Loader
 * Single-file embed script for any existing website.
 */
(function() {
    // 1. Detect API Host Origin from script src
    const scripts = document.getElementsByTagName('script');
    let apiHost = 'http://localhost:5000';
    for (let s of scripts) {
        if (s.src && s.src.includes('blujay-chatbot.js')) {
            const url = new URL(s.src);
            apiHost = url.origin;
            break;
        }
    }

    // 2. Inject Google Fonts & FontAwesome if missing
    if (!document.getElementById('blujay-fonts')) {
        const fontLink = document.createElement('link');
        fontLink.id = 'blujay-fonts';
        fontLink.rel = 'stylesheet';
        fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap';
        document.head.appendChild(fontLink);
    }

    if (!document.getElementById('blujay-fa')) {
        const faLink = document.createElement('link');
        faLink.id = 'blujay-fa';
        faLink.rel = 'stylesheet';
        faLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';
        document.head.appendChild(faLink);
    }

    // 3. Inject Chatbot CSS
    if (!document.getElementById('blujay-chatbot-css')) {
        const cssLink = document.createElement('link');
        cssLink.id = 'blujay-chatbot-css';
        cssLink.rel = 'stylesheet';
        cssLink.href = `${apiHost}/static/styles.css`;
        document.head.appendChild(cssLink);
    }

    // 4. Inject Container if missing
    if (!document.getElementById('react-chatbot-root')) {
        const rootDiv = document.createElement('div');
        rootDiv.id = 'react-chatbot-root';
        document.body.appendChild(rootDiv);
    }

    // 5. Load React & Chatbot Script
    function loadScript(src, isBabel) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            if (isBabel) s.type = 'text/babel';
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    async function init() {
        try {
            if (!window.React) {
                await loadScript('https://unpkg.com/react@18/umd/react.production.min.js');
            }
            if (!window.ReactDOM) {
                await loadScript('https://unpkg.com/react-dom@18/umd/react-dom.production.min.js');
            }
            if (!window.Babel) {
                await loadScript('https://unpkg.com/@babel/standalone/babel.min.js');
            }
            await loadScript(`${apiHost}/static/app.js`, true);
            console.log('Blujay AI Chatbot Widget initialized successfully.');
        } catch (e) {
            console.error('Failed to load Blujay AI Chatbot:', e);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
