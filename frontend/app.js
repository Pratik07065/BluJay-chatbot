const { useState, useEffect, useRef } = React;

// 1. Reusable Suggested Questions Component
const SuggestedQuestions = ({ questions, onSelect, disabled }) => {
    if (!questions || questions.length === 0) return null;

    return (
        <div class="suggested-section" aria-label="Suggested Questions">
            <span class="suggested-title">Suggested Questions:</span>
            <div class="suggested-chips">
                {questions.map((q, idx) => (
                    <button
                        key={idx}
                        class="suggested-chip"
                        onClick={() => onSelect(q)}
                        disabled={disabled}
                        aria-label={`Ask suggested question: ${q}`}
                    >
                        <i class="fa-solid fa-circle-question"></i>
                        <span>{q}</span>
                    </button>
                ))}
            </div>
        </div>
    );
};

// 2. Reusable Message Component
const ChatMessage = ({ message }) => {
    const isUser = message.sender === 'user';

    return (
        <div class={`chat-message-row ${isUser ? 'user-row' : 'bot-row'}`}>
            <div class="msg-avatar" aria-hidden="true">
                <i class={isUser ? "fa-solid fa-user" : "fa-solid fa-robot"}></i>
            </div>
            <div 
                class="msg-bubble" 
                role="article" 
                aria-label={`${isUser ? 'You' : 'Blujay Assistant'} said: ${message.text}`}
            >
                {message.text}
            </div>
        </div>
    );
};

// 3. Reusable Typing Indicator Component
const TypingIndicator = () => {
    return (
        <div class="chat-message-row bot-row" aria-live="polite" aria-label="Blujay Assistant is typing">
            <div class="msg-avatar" aria-hidden="true">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="typing-container">
                <div class="typing-dots">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
                <span class="typing-text">Blujay Assistant is thinking...</span>
            </div>
        </div>
    );
};

// 4. Reusable Chat Header Component
const ChatHeader = ({ onClose, onClear }) => {
    return (
        <header class="blujay-chat-header">
            <div class="header-brand">
                <div class="header-avatar" aria-hidden="true">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <div class="header-title-area">
                    <h3>Blujay Assistant</h3>
                    <div class="status-online">
                        <span class="online-dot"></span>
                        <span>Online | Official AI</span>
                    </div>
                </div>
            </div>
            <div class="header-controls">
                <button 
                    class="control-btn" 
                    onClick={onClear} 
                    title="Clear Conversation" 
                    aria-label="Clear chat history"
                >
                    <i class="fa-solid fa-rotate-right"></i>
                </button>
                <button 
                    class="control-btn" 
                    onClick={onClose} 
                    title="Close Chat Widget" 
                    aria-label="Close chatbot window"
                >
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        </header>
    );
};

// 5. Reusable Chat Input Form Component
const ChatInput = ({ onSend, disabled }) => {
    const [input, setInput] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (input.trim() && !disabled) {
            onSend(input.trim());
            setInput('');
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            handleSubmit(e);
        }
    };

    return (
        <footer class="blujay-chat-footer">
            <form class="chat-input-form" onSubmit={handleSubmit}>
                <input
                    type="text"
                    class="chat-input-field"
                    placeholder="Type your question here..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={disabled}
                    aria-label="Type your message"
                    autoComplete="off"
                />
                <button
                    type="submit"
                    class="send-button"
                    disabled={disabled || !input.trim()}
                    aria-label="Send message"
                    title="Send Message"
                >
                    <i class="fa-solid fa-paper-plane"></i>
                </button>
            </form>
            <div class="footer-branding">
                Powered by <a href="https://www.blujaytech.com/" target="_blank" rel="noreferrer">Blujay Technologies</a>
            </div>
        </footer>
    );
};

// 6. Floating Action Button Component
const FloatingButton = ({ isOpen, toggleOpen }) => {
    return (
        <button
            class="blujay-chat-trigger"
            onClick={toggleOpen}
            aria-label={isOpen ? "Close Blujay Assistant Chat" : "Open Blujay Assistant Chat"}
            aria-expanded={isOpen}
            title={isOpen ? "Close Assistant" : "Chat with Blujay Assistant"}
        >
            <i class={isOpen ? "fa-solid fa-xmark" : "fa-solid fa-comments"}></i>
            {!isOpen && <span class="blujay-unread-badge" aria-hidden="true"></span>}
        </button>
    );
};

// Main Chatbot Widget Orchestrator Component
const BlujayChatbotWidget = () => {
    const [isOpen, setIsOpen] = useState(false);
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
            const response = await fetch('/api/chat', {
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

    return (
        <div class="blujay-widget-container">
            {isOpen && (
                <div class="blujay-chat-window" role="dialog" aria-label="Blujay Assistant Chat Window">
                    <ChatHeader 
                        onClose={() => setIsOpen(false)} 
                        onClear={handleClear} 
                    />

                    <main class="blujay-chat-body" aria-live="polite">
                        {messages.map((msg) => (
                            <ChatMessage key={msg.id} message={msg} />
                        ))}

                        {/* Show suggested questions after welcome message if no user messages sent yet */}
                        {messages.length === 1 && (
                            <SuggestedQuestions 
                                questions={SUGGESTED_QUESTIONS} 
                                onSelect={handleSend} 
                                disabled={isLoading}
                            />
                        )}

                        {isLoading && <TypingIndicator />}
                        <div ref={messagesEndRef} />
                    </main>

                    <ChatInput onSend={handleSend} disabled={isLoading} />
                </div>
            )}

            <FloatingButton isOpen={isOpen} toggleOpen={() => setIsOpen(!isOpen)} />
        </div>
    );
};

// Render React Chatbot Widget into DOM root
const rootElement = document.getElementById('react-chatbot-root');
if (rootElement) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(<BlujayChatbotWidget />);
}
