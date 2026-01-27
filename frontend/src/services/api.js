import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export const chatAPI = {
    sendMessage: async (sessionId, message) => {
        const response = await axios.post(`${API_BASE_URL}/chat/message`, {
            session_id: sessionId,
            message: message
        });
        return response.data;
    },

    checkHealth: async () => {
        const response = await axios.get(`${API_BASE_URL}/health`);
        return response.data;
    }
};
