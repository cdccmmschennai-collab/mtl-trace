import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BRAND } from "./brand";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="app-brand" aria-label={`${BRAND.product} home`}>
            <img className="app-logo" src={BRAND.logoSrc} alt={BRAND.logoAlt} width={37} height={32} />
            <span className="app-brand-text">
              <span className="app-product">{BRAND.product}</span>
              <span className="app-tagline">{BRAND.tagline}</span>
            </span>
          </Link>
        </div>
      </header>
      <div id="main" tabIndex={-1} className="app-main">
        {children}
      </div>
    </>
  );
}
