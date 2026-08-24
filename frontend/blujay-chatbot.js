/**
 * Blujay Technologies AI Chatbot Widget Loader
 * Single-file standalone embed script for any existing website.
 */
(function() {
    // 1. Detect Backend API Host Origin from script tag src
    let apiHost = 'http://localhost:5000';
    const scripts = document.getElementsByTagName('script');
    for (let i = 0; i < scripts.length; i++) {
        const s = scripts[i];
        if (s.src && (s.src.includes('blujay-chatbot.js') || s.src.includes('/static/blujay-chatbot.js'))) {
            try {
                const url = new URL(s.src);
                apiHost = url.origin;
            } catch (err) {}
            break;
        }
    }
    window.BLUJAY_API_HOST = apiHost;

    // 2. Inject Google Fonts & FontAwesome
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

    // 3. Inject Widget CSS Stylesheet
    if (!document.getElementById('blujay-chatbot-css')) {
        const cssLink = document.createElement('link');
        cssLink.id = 'blujay-chatbot-css';
        cssLink.rel = 'stylesheet';
        cssLink.href = `${apiHost}/static/styles.css`;
        document.head.appendChild(cssLink);
    }

    // 4. Inject DOM Root Container if missing
    let rootDiv = document.getElementById('react-chatbot-root');
    if (!rootDiv) {
        rootDiv = document.createElement('div');
        rootDiv.id = 'react-chatbot-root';
        document.body.appendChild(rootDiv);
    }

    // 5. Script Loader Helper
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.crossOrigin = 'anonymous';
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    // 6. Mount Widget once React/ReactDOM are loaded
    async function init() {
        try {
            if (!window.React) {
                await loadScript('https://unpkg.com/react@18/umd/react.production.min.js');
            }
            if (!window.ReactDOM) {
                await loadScript('https://unpkg.com/react-dom@18/umd/react-dom.production.min.js');
            }

            const { useState, useEffect, useRef, createElement: e } = React;

            // --- Components ---
            const SuggestedQuestions = ({ questions, onSelect, disabled }) => {
                if (!questions || questions.length === 0) return null;
                return e('div', { className: 'suggested-section', 'aria-label': 'Suggested Questions' },
                    e('span', { className: 'suggested-title' }, 'Suggested Questions:'),
                    e('div', { className: 'suggested-chips' },
                        questions.map((q, idx) =>
                            e('button', {
                                key: idx,
                                className: 'suggested-chip',
                                onClick: () => onSelect(q),
                                disabled: disabled,
                                'aria-label': `Ask suggested question: ${q}`
                            },
                                e('i', { className: 'fa-solid fa-circle-question' }),
                                e('span', null, q)
                            )
                        )
                    )
                );
            };

            const ChatMessage = ({ message }) => {
                const isUser = message.sender === 'user';
                return e('div', { className: `chat-message-row ${isUser ? 'user-row' : 'bot-row'}` },
                    e('div', { className: 'msg-avatar', 'aria-hidden': 'true' },
                        e('i', { className: isUser ? 'fa-solid fa-user' : 'fa-solid fa-robot' })
                    ),
                    e('div', {
                        className: 'msg-bubble',
                        role: 'article',
                        'aria-label': `${isUser ? 'You' : 'Blujay Assistant'} said: ${message.text}`
                    }, message.text)
                );
            };

            const TypingIndicator = () => {
                return e('div', { className: 'chat-message-row bot-row', 'aria-live': 'polite' },
                    e('div', { className: 'msg-avatar', 'aria-hidden': 'true' },
                        e('i', { className: 'fa-solid fa-robot' })
                    ),
                    e('div', { className: 'typing-container' },
                        e('div', { className: 'typing-dots' },
                            e('div', { className: 'dot' }),
                            e('div', { className: 'dot' }),
                            e('div', { className: 'dot' })
                        ),
                        e('span', { className: 'typing-text' }, 'Blujay Assistant is thinking...')
                    )
                );
            };

            const ChatHeader = ({ onClose, onClear, isExpanded, onToggleExpand }) => {
                return e('header', { className: 'blujay-chat-header' },
                    e('div', { className: 'header-brand' },
                        e('div', { className: 'header-avatar', 'aria-hidden': 'true' },
                            e('i', { className: 'fa-solid fa-robot' })
                        ),
                        e('div', { className: 'header-title-area' },
                            e('h3', null, 'Blujay Assistant'),
                            e('div', { className: 'status-online' },
                                e('span', { className: 'online-dot' }),
                                e('span', null, 'Online | Official AI')
                            )
                        )
                    ),
                    e('div', { className: 'header-controls' },
                        e('button', {
                            className: 'control-btn',
                            onClick: onToggleExpand,
                            title: isExpanded ? 'Restore Default Size' : 'Expand Chatbot Window',
                            'aria-label': isExpanded ? 'Restore default chatbot size' : 'Expand chatbot window'
                        }, e('i', { className: isExpanded ? 'fa-solid fa-compress' : 'fa-solid fa-expand' })),
                        e('button', {
                            className: 'control-btn',
                            onClick: onClear,
                            title: 'Clear Conversation',
                            'aria-label': 'Clear chat history'
                        }, e('i', { className: 'fa-solid fa-rotate-right' })),
                        e('button', {
                            className: 'control-btn',
                            onClick: onClose,
                            title: 'Close Chat Widget',
                            'aria-label': 'Close chatbot window'
                        }, e('i', { className: 'fa-solid fa-xmark' }))
                    )
                );
            };

            const ChatInput = ({ onSend, disabled }) => {
                const [input, setInput] = useState('');

                const handleSubmit = (evt) => {
                    evt.preventDefault();
                    if (input.trim() && !disabled) {
                        onSend(input.trim());
                        setInput('');
                    }
                };

                const handleKeyDown = (evt) => {
                    if (evt.key === 'Enter' && !evt.shiftKey) {
                        handleSubmit(evt);
                    }
                };

                return e('footer', { className: 'blujay-chat-footer' },
                    e('form', { className: 'chat-input-form', onSubmit: handleSubmit },
                        e('input', {
                            type: 'text',
                            className: 'chat-input-field',
                            placeholder: 'Type your question here...',
                            value: input,
                            onChange: (evt) => setInput(evt.target.value),
                            onKeyDown: handleKeyDown,
                            disabled: disabled,
                            'aria-label': 'Type your message',
                            autoComplete: 'off'
                        }),
                        e('button', {
                            type: 'submit',
                            className: 'send-button',
                            disabled: disabled || !input.trim(),
                            'aria-label': 'Send message',
                            title: 'Send Message'
                        }, e('i', { className: 'fa-solid fa-paper-plane' }))
                    ),
                    e('div', { className: 'footer-branding' },
                        'Powered by ',
                        e('a', { href: 'https://www.blujaytech.com/', target: '_blank', rel: 'noreferrer' }, 'Blujay Technologies')
                    )
                );
            };

            const FloatingButton = ({ isOpen, toggleOpen }) => {
                return e('button', {
                    className: 'blujay-chat-trigger',
                    onClick: toggleOpen,
                    'aria-label': isOpen ? 'Close Blujay Assistant Chat' : 'Open Blujay Assistant Chat',
                    'aria-expanded': isOpen,
                    title: isOpen ? 'Close Assistant' : 'Chat with Blujay Assistant'
                },
                    e('i', { className: isOpen ? 'fa-solid fa-xmark' : 'fa-solid fa-comments' }),
                    !isOpen && e('span', { className: 'blujay-unread-badge', 'aria-hidden': 'true' })
                );
            };

            const BlujayChatbotWidget = () => {
                const [isOpen, setIsOpen] = useState(false);
                const [isExpanded, setIsExpanded] = useState(false);
                const [isLoading, setIsLoading] = useState(false);

                const WELCOME_MESSAGE = {
                    id: 'welcome-msg',
                    sender: 'bot',
                    text: "Hi! 👋 I'm the Blujay Assistant. I can help you with courses, training, admissions, placement support and other Blujay-related questions."
                };

                const SUGGESTED_QUESTIONS = [
                    "What courses do you offer?",
                    "Tell me about Python Full Stack.",
                    "Do you provide placement support?",
                    "How can I contact Blujay?"
                ];

                const [messages, setMessages] = useState([WELCOME_MESSAGE]);
                const messagesEndRef = useRef(null);

                const scrollToBottom = () => {
                    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                };

                useEffect(() => {
                    if (isOpen) {
                        scrollToBottom();
                    }
                }, [messages, isLoading, isOpen]);

                const handleSend = async (userQuestion) => {
                    if (!userQuestion || isLoading) return;

                    const userMsg = {
                        id: Date.now().toString(),
                        sender: 'user',
                        text: userQuestion
                    };

                    setMessages((prev) => [...prev, userMsg]);
                    setIsLoading(true);

                    try {
                        const targetApiUrl = `${apiHost}/api/chat`;
                        const response = await fetch(targetApiUrl, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ question: userQuestion })
                        });

                        if (!response.ok) {
                            throw new Error(`HTTP Error: ${response.status}`);
                        }

                        const data = await response.json();
                        const botAnswer = data.answer || "I'm sorry, I couldn't retrieve that information right now.";

                        const botMsg = {
                            id: (Date.now() + 1).toString(),
                            sender: 'bot',
                            text: botAnswer
                        };

                        setMessages((prev) => [...prev, botMsg]);

                    } catch (err) {
                        console.error("Chat error:", err);
                        const errorMsg = {
                            id: (Date.now() + 1).toString(),
                            sender: 'bot',
                            text: "I'm sorry, I couldn't connect to the Blujay assistant server. Please check your internet connection or call Blujay admissions directly at +91 96187 21797."
                        };
                        setMessages((prev) => [...prev, errorMsg]);
                    } finally {
                        setIsLoading(false);
                    }
                };

                const handleClear = () => {
                    setMessages([WELCOME_MESSAGE]);
                };

                return e('div', { className: 'blujay-widget-container' },
                    isOpen && e('div', {
                        className: `blujay-chat-window ${isExpanded ? 'is-expanded' : ''}`,
                        role: 'dialog',
                        'aria-label': 'Blujay Assistant Chat Window'
                    },
                        e(ChatHeader, {
                            onClose: () => setIsOpen(false),
                            onClear: handleClear,
                            isExpanded: isExpanded,
                            onToggleExpand: () => setIsExpanded(!isExpanded)
                        }),
                        e('main', { className: 'blujay-chat-body', 'aria-live': 'polite' },
                            messages.map((msg) => e(ChatMessage, { key: msg.id, message: msg })),
                            messages.length === 1 && e(SuggestedQuestions, {
                                questions: SUGGESTED_QUESTIONS,
                                onSelect: handleSend,
                                disabled: isLoading
                            }),
                            isLoading && e(TypingIndicator),
                            e('div', { ref: messagesEndRef })
                        ),
                        e(ChatInput, { onSend: handleSend, disabled: isLoading })
                    ),
                    e(FloatingButton, { isOpen: isOpen, toggleOpen: () => setIsOpen(!isOpen) })
                );
            };

            const root = ReactDOM.createRoot(rootDiv);
            root.render(e(BlujayChatbotWidget));
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
