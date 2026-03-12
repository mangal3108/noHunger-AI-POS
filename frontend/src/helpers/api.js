import axios from "axios";

const isLocal = typeof window !== 'undefined' && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

const rawServer = import.meta.env.VITE_SERVER_URL || import.meta.env.VITE_NODE_URL || (!isLocal ? "https://nohunger-ai-pos.onrender.com" : "http://localhost:5000");
// Clean trailing slash and ensure https for production
export const server = rawServer.endsWith('/') ? rawServer.slice(0, -1) : rawServer;

export const api = axios.create({
    baseURL: `${server}/api`,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Token expired or invalid
            localStorage.removeItem("token");
            localStorage.removeItem("user");

            // Only redirect if not already on login page to avoid loops if login page itself makes 401 calls (unlikely)
            if (!window.location.pathname.includes("/admin-secret-login")) {
                window.location.href = "/admin-secret-login";
            }
        }
        return Promise.reject(error);
    }
);
