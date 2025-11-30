import { defineStore } from 'pinia';
import api from '../api';
import router from '../router';

export const useAuthStore = defineStore('auth', {
    state: () => ({
        token: localStorage.getItem('token') || null,
        user: null,
        isAuthenticated: !!localStorage.getItem('token'),
    }),
    actions: {
        async login(username, password) {
            try {
                const formData = new FormData();
                formData.append('username', username);
                formData.append('password', password);

                const response = await api.post('/auth/login', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });

                this.token = response.data.access_token;
                this.isAuthenticated = true;
                localStorage.setItem('token', this.token);

                // Fetch user details? For now just redirect
                router.push('/');
                return true;
            } catch (error) {
                console.error('Login failed:', error);
                throw error;
            }
        },
        logout() {
            this.token = null;
            this.user = null;
            this.isAuthenticated = false;
            localStorage.removeItem('token');
            router.push('/login');
        }
    },
});
