interface Window {
  ng: any;
}

interface ImportMeta {
  env: {
    NG_APP_SUPABASE_URL: string;
    NG_APP_SUPABASE_ANON_KEY: string;
    [key: string]: any;
  };
}