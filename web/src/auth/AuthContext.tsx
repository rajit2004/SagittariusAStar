import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient, setUnauthorizedHandler } from '../api/client';
import { clearAllHistories, clearLegacyHistory } from '../lib/chatHistory';
import { AuthContext, type User } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      
      clearAllHistories();
      navigate('/login', { replace: true });
    });
  }, [navigate]);

  useEffect(() => {
    clearLegacyHistory();
  }, []);

  useEffect(() => {
    const validate = async () => {
      try {
        const response = await apiClient.get('/auth/me');
        setUser(response.data);
      } catch {
        
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    validate();
  }, []);

  const login = async (username: string, password: string) => {
    await apiClient.post('/auth/login', { email: username, password });
    
    const me = await apiClient.get('/auth/me');
    setUser(me.data);
  };

  const register = async (
    username: string,
    email: string,
    password: string,
    fullName?: string,
    role?: string,
    specialty?: string,
    licenseNumber?: string,
  ) => {
    const body: Record<string, unknown> = {
      username,
      email,
      password,
      full_name: fullName || null,
    };
    if (role) body.role = role;
    if (specialty) body.specialty = specialty;
    if (licenseNumber) body.license_number = licenseNumber;
    await apiClient.post('/auth/register', body);
  };

  const loginProvider = async (email: string, password: string) => {
    await apiClient.post('/provider/login', { email, password });
    
    const me = await apiClient.get('/auth/me');
    setUser(me.data);
  };

  const registerProvider = async (
    email: string,
    password: string,
    fullName?: string,
    specialty?: string,
    licenseNumber?: string,
  ) => {
    await apiClient.post('/provider/register', {
      email,
      password,
      full_name: fullName || null,
      specialty: specialty || null,
      license_number: licenseNumber || null,
    });
  };

  const logout = async (redirectTo = '/login') => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      
    } finally {
      setUser(null);
      
      clearAllHistories();
      navigate(redirectTo, { replace: true });
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, loginProvider, registerProvider, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
