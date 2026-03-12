import React, { useState, useEffect, useRef } from 'react';
import './Chatbot.css';
import { FaCommentDots, FaTimes, FaUtensils, FaExpand, FaCompress } from 'react-icons/fa';

const SERVER_URL = import.meta.env.VITE_SERVER_URL || import.meta.env.VITE_NODE_URL || 'http://localhost:5000';
const AI_URL = import.meta.env.VITE_SERVER_URL || import.meta.env.VITE_AI_URL || 'http://127.0.0.1:8000';

const Chatbot = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [sessionId, setSessionId] = useState('');
    const [messages, setMessages] = useState([]);
    const [inputText, setInputText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [cart, setCart] = useState([]);
    const [currentStep, setCurrentStep] = useState(1); // 1: Selection, 2: Identity, 3: Payment
    const [isLarge, setIsLarge] = useState(false);
    const messagesEndRef = useRef(null);

    const toggleSize = () => setIsLarge(!isLarge);

    const chips = [
        { label: "Menu", message: "show menu" },
    ];

    useEffect(() => {
        setSessionId(`session-${Date.now()}`);
        setMessages([
            text: "Welcome to NoHunger AI! Try: show menu, I recommend our Chicken Biryani or Margherita Pizza. Just share your address to start checkout.",
        ]);
    }, []);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const toggleChat = () => setIsOpen(!isOpen);

    const sendMessage = async (messageText) => {
        const text = typeof messageText === 'string' ? messageText : inputText;
        if (!text.trim() || !sessionId) return;

        const newMessages = [...messages, { text: text.trim(), role: 'user' }];
        setMessages(newMessages);
        setInputText('');
        setIsLoading(true);

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes timeout for LLM
            const response = await fetch(`${AI_URL}/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: text.trim(),
                }),
                signal: controller.signal,
            });
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errBody = await response.text();
                setMessages([...newMessages, { text: `Request failed (${response.status}). ${errBody}`, role: 'bot' }]);
                return;
            }

            const payload = await response.json();
            const model = payload.used_model || "unknown";

            // Sync cart from session state
            if (payload.session_state && payload.session_state.cart) {
                setCart(payload.session_state.cart);

                // Update Step
                const state = payload.session_state;
                if (state.cart && state.cart.length > 0) {
                    const hasIdentity = state.customer_name && state.customer_email && state.customer_phone && state.delivery_address;
                    if (hasIdentity) {
                        setCurrentStep(3);
                    } else if (state.customer_name || state.pending_slot?.startsWith("customer_") || state.delivery_address || state.pending_slot === "delivery_address") {
                        setCurrentStep(2);
                    } else {
                        setCurrentStep(1);
                    }
                } else {
                    setCurrentStep(1);
                }
            }

            setMessages([...newMessages, { text: payload.reply || "No reply from assistant.", role: 'bot', meta: "Bhadawar AI" }]);
        } catch (error) {
            setMessages([...newMessages, { text: `Network error: ${error.message}`, role: 'bot' }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleFormSubmit = (e) => {
        e.preventDefault();
        sendMessage();
    };

    return (
        <div className="chatbot-wrapper">
            {isOpen ? (
                <div className={`chatbot-panel rise ${isLarge ? 'large' : ''}`}>
                    <header className="chatbot-header">
                        <div className="chatbot-header-content">
                            <div className="chatbot-header-text">
                                <p className="kicker">Conversational POS</p>
                                <h2>AI Assistant</h2>
                            </div>
                        </div>
                        <div className="header-actions">
                            <button onClick={toggleSize} className="expand-btn" title="Toggle Size">
                                {isLarge ? <FaCompress size={12} /> : <FaExpand size={12} />}
                            </button>
                            <button onClick={toggleChat} className="close-btn"><FaTimes /></button>
                        </div>
                    </header>

                    <div className="chatbot-steps">
                        <div className={`step ${currentStep >= 1 ? 'active' : ''}`}>Selection</div>
                        <div className="step-arrow">→</div>
                        <div className={`step ${currentStep >= 2 ? 'active' : ''}`}>Identity</div>
                        <div className="step-arrow">→</div>
                        <div className={`step ${currentStep >= 3 ? 'active' : ''}`}>Payment</div>
                    </div>

                    <div className="chatbot-controls">
                        <div className="quick-actions">
                            {chips.map((chip, idx) => (
                                <button
                                    key={idx}
                                    type="button"
                                    className="quick-chip"
                                    onClick={() => sendMessage(chip.message)}
                                >
                                    {chip.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="chatbot-messages">
                        {messages.map((msg, idx) => (
                            <article key={idx} className={`msg ${msg.role}`}>
                                {msg.text}
                                {msg.meta && <div className="meta">{msg.meta}</div>}
                            </article>
                        ))}
                        {isLoading && (
                            <article className="msg bot">
                                <div className="typing-indicator">
                                    <span></span><span></span><span></span>
                                </div>
                            </article>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {cart.length > 0 && (
                        <div className="chatbot-cart-preview">
                            <div className="cart-items">
                                {cart.map((item, idx) => (
                                    <div key={idx} className="cart-item">
                                        <div className="item-info">
                                            {item.image && <img src={`${SERVER_URL}/${item.image}`} alt={item.item_name} className="item-thumb" />}
                                            <span className="item-name">{item.item_name}</span>
                                        </div>
                                        <div className="item-controls">
                                            <button onClick={() => sendMessage(`remove 1 ${item.item_name}`)}>-</button>
                                            <span className="item-qty">{item.quantity}</span>
                                            <button onClick={() => sendMessage(`add 1 ${item.item_name}`)}>+</button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <form onSubmit={handleFormSubmit} className="chatbot-composer">
                        <input
                            type="text"
                            placeholder="Type a message..."
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            disabled={isLoading}
                            autoComplete="off"
                        />
                        <button type="submit" disabled={isLoading || !inputText.trim()}>
                            Send
                        </button>
                    </form>
                </div>
            ) : (
                <button className="chatbot-toggle-btn" onClick={toggleChat}>
                    <FaCommentDots size={24} />
                </button>
            )}
        </div>
    );
};

export default Chatbot;
