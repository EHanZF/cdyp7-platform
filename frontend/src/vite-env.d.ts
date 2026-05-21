/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DASHBOARD_STATE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
