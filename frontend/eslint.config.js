import js from "@eslint/js";
import noUnsanitized from "eslint-plugin-no-unsanitized";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import security from "eslint-plugin-security";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
      globals: { window: "readonly", document: "readonly", console: "readonly", fetch: "readonly" },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      security,
      "no-unsanitized": noUnsanitized,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],

      // eslint-plugin-security's recommended config sets every rule to `warn`, so a bare
      // `eslint .` reports them and still exits 0. These are set to error deliberately.
      "security/detect-eval-with-expression": "error",
      "security/detect-non-literal-require": "error",
      "security/detect-unsafe-regex": "error",
      "security/detect-buffer-noassert": "error",
      "security/detect-child-process": "error",
      "security/detect-new-buffer": "error",
      "security/detect-pseudoRandomBytes": "error",

      // no-unsanitized covers the DOM sinks; neither plugin covers React's own prop.
      "no-unsanitized/method": "error",
      "no-unsanitized/property": "error",
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML is banned; React's escaping is the XSS defence here.",
        },
        {
          selector: "NewExpression[callee.name='Function']",
          message: "new Function is banned.",
        },
      ],

      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
  {
    files: ["tests/**/*.{ts,tsx}"],
    rules: { "@typescript-eslint/no-non-null-assertion": "off" },
  },
);
