interface ImportMetaEnv {
  readonly VITE_OWNER: string;
  readonly VITE_REPO: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}