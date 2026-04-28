declare module '@supabase/supabase-js' {
  export function createClient(supabaseUrl: string, supabaseKey: string): SupabaseClient;

  export interface SupabaseClient {
    auth: {
      getSession(): Promise<{ data: { session: Session | null } }>;
      signInWithOAuth(options: { provider: string; options: { redirectTo: string } }): Promise<{ error: Error | null }>;
      signInWithPassword(options: { email: string; password: string }): Promise<{ error: Error | null }>;
      signOut(): Promise<{ error: Error | null }>;
      onAuthStateChange(callback: (event: string, session: Session | null) => void): { data: { subscription: { unsubscribe: () => void } } };
    };
  }

  export interface Session {
    access_token: string;
    user: {
      id: string;
      email: string | null;
    };
  }

  export interface Error {
    message: string;
    name?: string;
    status?: number;
  }
}