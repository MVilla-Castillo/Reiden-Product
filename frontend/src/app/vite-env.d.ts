/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly NG_APP_SUPABASE_URL: string;
  readonly NG_APP_SUPABASE_ANON_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '@supabase/supabase-js';
declare module '@supabase/supabase-js' {
  interface AuthSession {
    access_token: string;
    user: { email: string | null };
  }
  interface Session {
    access_token: string;
    user: { email: string | null };
  }
  interface AuthError {
    message: string;
  }
  export function createClient(supabaseUrl: string, supabaseKey: string: any): any;
}