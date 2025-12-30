import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import { Bot, User, Mic, ImageIcon } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';
import { toast } from 'sonner';
import { ImageWithFallback } from './figma/ImageWithFallback';
import axios from 'axios';

// --- CONFIGURATION ---
const TEXT_CHAT_API_ENDPOINT = 'http://localhost:3001/api/chat'; 
const SESSION_ID_KEY = 'agroChatSessionId';

// --- TYPE DEFINITIONS ---
interface Message {
    id: string;
    role: 'user' | 'assistant' | 'typing'; 
    content: string;
    timestamp: Date;
    image?: string;
}

const INITIAL_WELCOME_MESSAGE: Message = {
    id: 'welcome',
    role: 'assistant',
    content: "Hello! I'm your **Smart Agro AI Assistant**. I can help you with irrigation advice, nutrient management, pest detection, and yield optimization. How can I assist you with your crops today?",
    timestamp: new Date(),
};

// --- HELPER FUNCTION: Parsing Text (Kept outside component) ---
const parseBoldText = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        return part;
    });
};

// --- HELPER COMPONENT: Formatting Message (Kept outside component) ---
interface FormattedMessageProps { content: string; isStreaming?: boolean; }
const FormattedMessage: React.FC<FormattedMessageProps> = ({ content, isStreaming }) => {
    const paragraphs = content.split(/\n+/);
    return (
        <div>
            {paragraphs.map((paragraph, index) => {
                if (paragraph.trim().startsWith('*') || paragraph.trim().startsWith('-')) {
                    return (
                        <ul key={index} className="list-disc list-inside ml-4 mb-2">
                            <li>{parseBoldText(paragraph.trim().substring(1))}</li>
                        </ul>
                    );
                }
                return <p key={index} className="mb-2">{parseBoldText(paragraph)}</p>;
            })}
            {isStreaming && <span className="blinking-cursor"></span>}
        </div>
    );
};


// --- MAIN COMPONENT ---
export function AIAssistant() {
    const { t } = useLanguage();
    
    // --- STATE & REFS ---
    const [messages, setMessages] = useState<Message[]>([INITIAL_WELCOME_MESSAGE]);
    const [input, setInput] = useState('');
    const [isListening, setIsListening] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string>('');
    const [isStreaming, setIsStreaming] = useState(false); 
    
    const fileInputRef = useRef<HTMLInputElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const recognitionRef = useRef<any>(null);


    // --- HANDLERS (Defined inside component for state access) ---
    
    const handleSend = useCallback(async (textToSend?: string) => {
        const messageContent = textToSend || input;
        if (!messageContent.trim() || !sessionId) return;

        setIsLoading(true);
        setInput('');
        
        const userMessage: Message = { id: Date.now().toString(), role: 'user', content: messageContent, timestamp: new Date() };
        const typingId = (Date.now() + 1).toString();
        const typingMessage: Message = { id: typingId, role: 'typing', content: '...', timestamp: new Date() };

        setMessages((prev) => [ ...prev, userMessage, typingMessage ]);
        setIsStreaming(true); 

        try {
            const response = await axios.post(TEXT_CHAT_API_ENDPOINT, {
                prompt: messageContent,
                sessionId: sessionId, 
            });

            setMessages(prev => prev.filter(msg => msg.id !== typingId));
            setIsStreaming(false);

            if (response.status === 200 && response.data.response) {
                const aiResponse: Message = {
                    id: (Date.now() + 2).toString(),
                    role: 'assistant',
                    content: response.data.response,
                    timestamp: new Date(),
                };
                setMessages(prev => [...prev, aiResponse]);
            } else {
                const errorMessage: Message = { id: (Date.now() + 2).toString(), role: 'assistant', content: response.data.error || "Received empty or error response from AI.", timestamp: new Date() };
                setMessages(prev => [...prev, errorMessage]);
                toast.error("AI returned an error.");
            }

        } catch (error) {
            console.error('API connection failed:', error);
            toast.error('Connection to the backend failed (port 3001).');
            
            setMessages(prev => prev.filter(msg => msg.id !== typingId));
            setIsStreaming(false);
            
            const networkError: Message = { id: (Date.now() + 2).toString(), role: 'assistant', content: "Network error: Could not reach the Smart Agro AI server.", timestamp: new Date() };
            setMessages(prev => [...prev, networkError]);

        } finally {
            setIsLoading(false);
        }
    }, [input, sessionId]); 


    const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsLoading(true);
        toast.info('📷 Analyzing image...');
        
        const initialPrompt = 'Analyze this image of my crop and identify any potential issues.';

        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onloadend = () => {
            const userMessage: Message = { id: Date.now().toString(), role: 'user', content: initialPrompt, timestamp: new Date(), image: reader.result as string };
            setMessages((prev) => [...prev, userMessage]);
        };
        
        const typingId = (Date.now() + 1).toString();
        setMessages(prev => [...prev, { id: typingId, role: 'typing', content: '...', timestamp: new Date() }]);
        setIsStreaming(true);

        const formData = new FormData();
        formData.append('image', file);
        formData.append('prompt', initialPrompt);
        formData.append('sessionId', sessionId); 

        try {
            const response = await axios.post(TEXT_CHAT_API_ENDPOINT, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            
            setMessages(prev => prev.filter(msg => msg.id !== typingId));
            setIsStreaming(false);

            const aiResponse: Message = { id: (Date.now() + 2).toString(), role: 'assistant', content: response.data.response, timestamp: new Date() };
            setMessages((prev) => [...prev, aiResponse]);

        } catch (error) {
            console.error("Error connecting to vision backend:", error);
            setMessages(prev => prev.filter(msg => msg.id !== typingId));
            setIsStreaming(false);
            const errorMessage: Message = { id: (Date.now() + 2).toString(), role: 'assistant', content: "Sorry, I couldn't analyze the image or reach the server.", timestamp: new Date() };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleVoiceToggle = () => {
        if (isListening) {
            recognitionRef.current?.stop();
            setIsListening(false);
        } else {
            recognitionRef.current?.start();
            setIsListening(true);
            toast.info('🎤 Listening...');
        }
    };


    // --- EFFECTS ---
    const initializeSession = () => {
        let id = localStorage.getItem(SESSION_ID_KEY);
        if (!id) {
            id = 'user_' + Date.now().toString(); 
            localStorage.setItem(SESSION_ID_KEY, id);
        }
        setSessionId(id);
    };

    // 1. Initialize Session ID
    useEffect(() => {
        initializeSession();
    }, []);
    
    // 2. Auto-scroll to bottom (TypeScript fix applied)
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);


    // 3. Setup Speech Recognition (Safely references handleSend)
    useEffect(() => {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US';
            recognition.interimResults = false;

            recognition.onresult = (event: any) => {
                const transcript = event.results[0][0].transcript;
                handleSend(transcript); 
            };
            recognition.onerror = (event: any) => {
                console.error('Speech recognition error:', event.error);
                toast.error('Voice recognition failed. Please try again.');
            };
            recognition.onend = () => {
                setIsListening(false);
            };
            recognitionRef.current = recognition;
        } else {
            toast.warning("Your browser doesn't support voice recognition.");
        }
    }, [handleSend]); 

    
    // --- RENDER ---
    return (
        <div className="p-6 h-[calc(100vh-80px)]">
            <Card className="h-[calc(100%-120px)] flex flex-col">
                <ScrollArea className="flex-1 p-6">
                    <AnimatePresence>
                        {messages.map((message, index) => (
                            <motion.div
                                key={message.id}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -20 }}
                                className={`mb-4 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div className={`flex gap-3 max-w-[80%] ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                                    <div className={`p-2 rounded-full h-10 w-10 flex items-center justify-center ${
                                        message.role === 'user' ? 'bg-blue-500' : 'bg-green-500'
                                    }`}>
                                        {message.role === 'user' ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
                                    </div>
                                    <div className={`p-4 rounded-2xl ${
                                        message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-muted'
                                    }`}>
                                        {message.image && (
                                            <ImageWithFallback
                                                src={message.image}
                                                alt="Uploaded"
                                                className="rounded-lg mb-2 max-w-[200px]"
                                            />
                                        )}
                                        
                                        <FormattedMessage
                                            content={message.content}
                                            isStreaming={isStreaming && index === messages.length - 1 && message.role === 'typing'}
                                        />

                                        <p className={`text-xs mt-2 ${
                                            message.role === 'user' ? 'text-blue-100' : 'text-muted-foreground'
                                        }`}>
                                            {message.timestamp.toLocaleTimeString()}
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                    <div ref={messagesEndRef} />
                </ScrollArea>

                {/* --- INPUT SECTION WITH BUTTONS --- */}
                <div className="p-4 border-t">
                    <div className="flex items-center gap-2">
                        {/* Hidden file input for image upload */}
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            accept="image/*"
                            onChange={handleImageUpload}
                            aria-label={t('uploadImageForAnalysis') || 'Upload Image for Analysis'}
                            title={t('uploadImageForAnalysis') || 'Upload Image for Analysis'}
                        />
                        
                        {/* Image Upload Button (A11y fix applied) */}
                        <Button
                            variant="outline"
                            size="icon"
                            className="shrink-0"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isLoading}
                            aria-label={t('uploadImageForAnalysis') || 'Upload Image for Analysis'}
                        >
                            <ImageIcon className="h-5 w-5" />
                        </Button>
                        
                        {/* Voice Toggle Button (A11y fix applied) */}
                        <Button
                            variant="outline"
                            size="icon"
                            className={`shrink-0 ${isListening ? 'bg-red-500 text-white hover:bg-red-600' : ''}`}
                            onClick={handleVoiceToggle}
                            disabled={isLoading}
                            aria-label={t('voiceInputToggle') || 'Toggle Voice Input'}
                        >
                            <Mic className="h-5 w-5" />
                        </Button>
                        
                        {/* Single Input Field (A11y fix applied) */}
                        <Input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && !isLoading && handleSend()}
                            placeholder={t('askQuestion')}
                            disabled={isLoading}
                            aria-label={t('askQuestion')} 
                        />
                        
                        {/* Send Button */}
                        <Button onClick={() => handleSend()} disabled={!input.trim() || isLoading}>
                            Send
                        </Button>
                    </div>
                </div>
            </Card>
        </div>
    );
}