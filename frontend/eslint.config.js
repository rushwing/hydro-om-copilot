import tseslint from "typescript-eslint";

export default tseslint.config(
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
      // Allow short-circuit side-effects (used in useSSEDiagnosis.ts)
      "@typescript-eslint/no-unused-expressions": ["error", { allowShortCircuit: true }],
    },
  },
  {
    ignores: ["dist/**", "node_modules/**"],
  },
);
