// Flat config (mandatory as of ESLint 9+; migrated from .eslintrc.json's
// "extends": "next/core-web-vitals" when Next.js bumped to 16, which
// removed the `next lint` CLI subcommand this repo's lint script used).
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  { ignores: [".next/**", "out/**", "node_modules/**"] },
  ...nextCoreWebVitals,
  {
    rules: {
      // Downgraded, not disabled: eslint-plugin-react-hooks@7 (newly
      // bundled here) errors on any synchronous setState in an effect.
      // Every hit in this codebase is "reset error/loading state before
      // a refetch" -- moving the reset into the fetch's .then() (the
      // rule's suggested fix) would let a stale error linger on screen
      // for the new fetch's duration instead of clearing immediately,
      // trading correct UX for a style preference. Kept visible as a
      // warning rather than silenced.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default eslintConfig;
