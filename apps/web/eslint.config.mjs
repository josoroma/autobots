import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const SOURCE = [
  "app/**/*.{ts,tsx}",
  "components/**/*.{ts,tsx}",
  "lib/**/*.{ts,tsx}",
];
const SPECS = ["tests/**/*.ts"];

const config = [
  { ignores: [".next/**", "next-env.d.ts"] },
  ...nextCoreWebVitals,
  ...nextTypescript,
  // R-06: size, complexity and cycles (STD-05, STD-07). Today's violations are recorded in
  // eslint-suppressions.json, which only shrinks: a fixed one must be pruned, a new one fails.
  {
    files: [...SOURCE, ...SPECS],
    rules: {
      complexity: ["error", 15],
      "max-depth": ["error", 4],
      "max-lines-per-function": [
        "error",
        { max: 150, skipBlankLines: true, skipComments: true },
      ],
      "max-lines": [
        "error",
        { max: 400, skipBlankLines: true, skipComments: true },
      ],
      "import/no-cycle": "error",
    },
  },
  // R-06: replies are parsed, never asserted (STD-10).
  {
    files: ["components/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/consistent-type-assertions": [
        "error",
        { assertionStyle: "never" },
      ],
    },
  },
  // US-11.11: a form control comes from the shared components.
  {
    files: ["app/**/*.tsx", "components/**/*.tsx"],
    ignores: ["components/ui/field.tsx"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXOpeningElement[name.name=/^(input|select|textarea)$/]",
          message:
            "Use Input, Select or Textarea from components/ui/field.tsx.",
        },
      ],
    },
  },
  // R-58, TWEB-06: a browser spec waits on a condition, a response or page.clock. The fixed sleeps
  // left are negative observations, each with a comment saying why, and eslint-suppressions.json
  // records them, so a new one fails.
  {
    files: ["tests/browser/**/*.ts"],
    rules: {
      "no-restricted-properties": [
        "error",
        {
          property: "waitForTimeout",
          message:
            "Wait on a condition, a response or page.clock, not a fixed time.",
        },
      ],
    },
  },
];

export default config;
