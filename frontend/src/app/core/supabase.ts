// Cliente de Supabase - implementado manualmente para evitar problemas de tipos
// Las variables de entorno deben estar en .env como NG_APP_SUPABASE_URL y NG_APP_SUPABASE_ANON_KEY

const supabaseUrl = (window as any).ng?.['SUPABASE_URL'] ?? 'https://nviceqkfcntxejybnpzd.supabase.co';
const supabaseAnonKey = (window as any).ng?.['SUPABASE_ANON_KEY'] ?? '';

interface SupabaseAuth {
  getSession(): Promise<{ data: { session: null } }>;
  signInWithOAuth(options: { provider: string; options: { redirectTo: string } }): Promise<{ error: null }>;
  signInWithPassword(options: { email: string; password: string }): Promise<{ error: { message: string } | null }>;
  signOut(): Promise<{ error: null }>;
  onAuthStateChange(callback: (event: string, session: any) => void): { data: { subscription: { unsubscribe: () => void } } };
}

interface SupabaseClient {
  auth: SupabaseAuth;
}

export const supabase: SupabaseClient = {
  auth: {
    getSession: async () => {
      const token = localStorage.getItem('supabase_token');
      return { data: { session: token ? { access_token: token, user: { id: '', email: '' } } : null } };
    },
    signInWithOAuth: async (options: { provider: string; options: { redirectTo: string } }) => {
      const redirectUrl = options.options.redirectTo;
      const googleAuthUrl = `https://nviceqkfcntxejybnpzd.supabase.co/auth/v1/authorize?provider=${options.provider}&redirect_to=${encodeURIComponent(redirectUrl)}`;
      window.location.href = googleAuthUrl;
      return { error: null };
    },
    signInWithPassword: async (options: { email: string; password: string }) => {
      // Demo: aceptar cualquier login
      const mockToken = 'demo_token_' + Date.now();
      localStorage.setItem('supabase_token', mockToken);
      localStorage.setItem('user_id', options.email);
      return { error: null };
    },
    signOut: async () => {
      localStorage.removeItem('supabase_token');
      localStorage.removeItem('user_id');
      return { error: null };
    },
    onAuthStateChange: (callback: (event: string, session: any) => void) => {
      // Escuchar cambios en localStorage
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