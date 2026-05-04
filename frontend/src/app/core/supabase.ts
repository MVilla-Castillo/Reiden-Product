import { environment } from '../../environments/environment';

const supabaseUrl = environment.supabaseUrl;

interface SupabaseAuth {
  getSession(): Promise<{ data: { session: { access_token: string; user: { id: string; email: string } } | null } }>;
  signInWithOAuth(options: { provider: string; options: { redirectTo: string } }): Promise<{ error: null }>;
  signInWithPassword(options: { email: string; password: string }): Promise<{ error: { message: string } | null }>;
  signOut(): Promise<{ error: null }>;
  onAuthStateChange(callback: (event: string, session: { access_token: string; user: {} } | null) => void): { data: { subscription: { unsubscribe: () => void } } };
}

interface SupabaseClient {
  auth: SupabaseAuth;
}

export const supabase: SupabaseClient = {
  auth: {
    getSession: async () => {
      const token = localStorage.getItem('supabase_token');
      const email = localStorage.getItem('user_id');
      return {
        data: {
          session: token
            ? { access_token: token, user: { id: '', email: email || '' } }
            : null
        }
      };
    },
    signInWithOAuth: async (options: { provider: string; options: { redirectTo: string } }) => {
      const redirectUrl = options.options.redirectTo;
      const googleAuthUrl = `${supabaseUrl}/auth/v1/authorize?provider=${options.provider}&redirect_to=${encodeURIComponent(redirectUrl)}`;
      window.location.href = googleAuthUrl;
      return { error: null };
    },
    signInWithPassword: async (options: { email: string; password: string }) => {
      const mockToken = 'demo_token_' + Date.now();
      localStorage.setItem('supabase_token', mockToken);
      localStorage.setItem('user_id', options.email);
      window.dispatchEvent(new StorageEvent('storage', { key: 'supabase_token', newValue: mockToken }));
      return { error: null };
    },
    signOut: async () => {
      localStorage.removeItem('supabase_token');
      localStorage.removeItem('user_id');
      window.dispatchEvent(new StorageEvent('storage', { key: 'supabase_token', newValue: null }));
      return { error: null };
    },
    onAuthStateChange: (callback: (event: string, session: { access_token: string; user: {} } | null) => void) => {
      const handler = (e: StorageEvent) => {
        if (e.key === 'supabase_token') {
          const token = e.newValue;
          callback(token ? 'TOKEN_REFRESHED' : 'SIGNED_OUT', token ? { access_token: token, user: {} } : null);
        }
      };
      window.addEventListener('storage', handler);
      return { data: { subscription: { unsubscribe: () => window.removeEventListener('storage', handler) } } };
    }
  }
};