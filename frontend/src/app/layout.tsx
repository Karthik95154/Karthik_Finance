import "../styles/globals.css";
import React from "react";

export const metadata = {
  title: "Finance Invoice Application",
  description: "Clean, minimalist invoice processing and double-entry accounting engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="navbar">
          <div className="container navbar-inner">
            <div className="brand">
              <a href="/finance/upload" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "19px", fontWeight: "700", letterSpacing: "-0.03em" }}>Finance</span>
                <span className="brand-badge">Stage 1 Foundation</span>
              </a>
            </div>
            <nav style={{ display: "flex", gap: "10px" }}>
              <a href="/finance/integrations" className="btn btn-secondary" style={{ padding: "6px 12px", fontSize: "13px" }}>
                Integrations
              </a>
              <a href="/finance/inbox" className="btn btn-secondary" style={{ padding: "6px 12px", fontSize: "13px" }}>
                Staging Queue
              </a>
              <a href="/finance/upload" className="btn btn-secondary" style={{ padding: "6px 12px", fontSize: "13px" }}>
                Upload Invoice
              </a>
            </nav>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
