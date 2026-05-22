import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: ["node_modules", "dist", ".env"], // ✅ replaces .eslintignore
  },

  js.configs.recommended,

  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.node, // ✅ FIXES process, console, etc.
      },
    },
    rules: {
      "no-unused-vars": "warn",
      "no-console": "off",
    },
  },
];