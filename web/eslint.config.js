import js from "@eslint/js";
import svelte from "eslint-plugin-svelte";
import {
    defineConfig,
    globalIgnores,
} from "eslint/config";
import globals from "globals";
import ts from "typescript-eslint";

export default defineConfig(
    globalIgnores(["build/", ".svelte-kit/", "node_modules/", "src/lib/api/schema.d.ts"]),
    js.configs.recommended,
    ts.configs.recommended,
    svelte.configs.recommended,
    {
        languageOptions: { globals: { ...globals.browser, ...globals.node } },
        rules: {
            // TypeScript already reports undefined names, and knows about ambient types.
            "no-undef": "off",
        },
    },
    {
        files: ["src/**/*.ts", "src/**/*.svelte"],
        languageOptions: {
            parserOptions: {
                projectService: true,
                tsconfigRootDir: import.meta.dirname,
                parser: ts.parser,
                extraFileExtensions: [".svelte"],
            },
        },
        // Only the promise rules from the type-checked set: the `no-unsafe-*` rules fire on the
        // `any`s svelte2tsx emits for template bindings.
        rules: {
            "@typescript-eslint/await-thenable": "error",
            "@typescript-eslint/no-floating-promises": "error",
            "@typescript-eslint/no-misused-promises": "error",
        },
    },
);
