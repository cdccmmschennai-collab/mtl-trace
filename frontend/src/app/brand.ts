import cdcLogo from "../assets/cdc-logo.png";

/**
 * Visible branding, in one place. Replacing the logo means replacing `src/assets/cdc-logo.png` (also used as the
 * favicon in index.html) or pointing `logoSrc` at a new asset. Internal identifiers keep their existing names.
 */
export const BRAND = {
  product: "MTL Trace",
  tagline: "Engineering Data Traceability",
  logoSrc: cdcLogo,
  logoAlt: "CDC Construction Development Company",
} as const;
