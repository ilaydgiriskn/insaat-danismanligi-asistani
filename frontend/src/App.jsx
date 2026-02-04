import { useState, useRef, useEffect } from 'react';
import { chatAPI } from './services/api';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // State for Resume Modal
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [resumeSessionId, setResumeSessionId] = useState(null);

  // Initialize sessionId lazily
  const [sessionId, setSessionId] = useState(() => {
    // Check localStorage but don't set it yet if we want to show modal
    return null;
  });

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initial Load Check
  useEffect(() => {
    const checkSavedSession = async () => {
      const savedId = localStorage.getItem('chat_session_id');
      if (savedId) {
        setResumeSessionId(savedId);
        setShowResumeModal(true);
      } else {
        // No saved session -> Start new immediately
        startNewSession();
      }
    };
    checkSavedSession();
  }, []);

  const startNewSession = () => {
    const newId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newId);
    localStorage.setItem('chat_session_id', newId);
    setMessages([{
      role: 'assistant',
      content: 'Merhaba! Ben Güllüoğlu İnşaat, yapay zeka destekli kişisel emlak danışmanınızım. Size en uygun yaşam alanını bulmak için buradayım. Öncelikle tanışabilmemiz için isim ve soyisminizi öğrenebilir miyim?',
      timestamp: new Date()
    }]);
    setShowResumeModal(false);
  };

  const handleResumeSession = async () => {
    if (!resumeSessionId) return;

    try {
      setIsLoading(true);
      const res = await chatAPI.getSessionHistory(resumeSessionId);

      if (res.found && res.data.messages && res.data.messages.length > 0) {
        const restoredMessages = res.data.messages.map(msg => ({
          role: msg.role === 'ai' ? 'assistant' : msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp),
        }));
        setMessages(restoredMessages);
        setSessionId(resumeSessionId);
        // Ensure localStorage is sync (it should be already)
        localStorage.setItem('chat_session_id', resumeSessionId);
      } else {
        // Saved session invalid -> Start new
        console.warn("Saved session not found on server, starting new.");
        startNewSession();
      }
    } catch (error) {
      console.error("Resume failed:", error);
      startNewSession();
    } finally {
      setIsLoading(false);
      setShowResumeModal(false);
    }
  };

  const handleStartNew = () => {
    if (window.confirm("Eski sohbetiniz silinecek. Emin misiniz?")) {
      startNewSession();
    }
  };

  // Only for manual "New Chat" button click
  const handleManualNewChat = () => {
    if (window.confirm("Mevcut sohbeti arşivleyip yeni bir görüşme başlatmak istiyor musunuz?")) {
      startNewSession();
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();

    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await chatAPI.sendMessage(sessionId, inputMessage);

      const assistantMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        type: response.type,
        isComplete: response.is_complete
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        role: 'assistant',
        content: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.',
        timestamp: new Date(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 relative">

      {/* Resume Modal Overlay */}
      {showResumeModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full transform transition-all scale-100 animate-fade-in-up">
            <div className="text-center mb-6">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Hoş Geldiniz!</h2>
              <p className="text-gray-600">Önceki sohbetinizden devam etmek ister misiniz?</p>
            </div>

            <div className="space-y-3">
              <button
                onClick={handleResumeSession}
                disabled={isLoading}
                className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all disabled:opacity-70 flex items-center justify-center space-x-2"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Kaldığım Yerden Devam Et</span>
                  </>
                )}
              </button>

              <button
                onClick={handleStartNew}
                disabled={isLoading}
                className="w-full py-3.5 bg-white border-2 border-gray-200 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all flex items-center justify-center space-x-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                <span>Yeni Sohbet Başlat</span>
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={`container mx-auto max-w-4xl h-screen flex flex-col p-4 transition-opacity duration-300 ${showResumeModal ? 'opacity-20 pointer-events-none' : 'opacity-100'}`}>
        {/* Header */}
        <div className="bg-white rounded-t-2xl shadow-lg p-6 border-b border-gray-100 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Güllüoğlu İnşaat
              </h1>
              <p className="text-sm text-gray-500">AI Emlak Danışmanı</p>
            </div>
          </div>

          <button
            onClick={handleManualNewChat}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Yeni Sohbet</span>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 bg-white shadow-lg overflow-y-auto p-6 space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-6 py-4 ${message.role === 'user'
                  ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                  : message.isError
                    ? 'bg-red-50 text-red-800 border border-red-200'
                    : 'bg-gray-50 text-gray-800 border border-gray-200'
                  }`}
              >
                <p className="whitespace-pre-wrap text-left leading-normal">{message.content}</p>
              </div>
            </div>
          ))}
          {isLoading && !showResumeModal && (
            <div className="flex justify-start">
              <div className="bg-gray-50 rounded-2xl px-6 py-4 border border-gray-200">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white rounded-b-2xl shadow-lg p-6 border-t border-gray-100">
          <form onSubmit={handleSendMessage} className="flex space-x-4">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Mesajınızı yazın..."
              disabled={isLoading || showResumeModal}
              className="flex-1 px-6 py-4 rounded-full border-2 border-gray-200 focus:border-blue-500 focus:outline-none transition-colors disabled:bg-gray-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={isLoading || !inputMessage.trim() || showResumeModal}
              className="px-8 py-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-full font-semibold hover:shadow-lg transform hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            >
              Gönder
            </button>
          </form>
        </div>
      </div>
    </div >
  );
}

export default App;
