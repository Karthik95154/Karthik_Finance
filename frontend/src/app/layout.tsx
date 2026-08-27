import "../styles/globals.css";
import React from "react";

export const metadata = {
  title: "Sakshi Finance | AI Accounting & Zoho Books Engine",
  description: "Autonomous invoice extraction, Indian GST/TDS accounting, and Zoho Books synchronization",
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
                <span style={{ fontSize: "19px", fontWeight: "700", letterSpacing: "-0.03em" }}>Sakshi Finance</span>
                <span className="brand-badge">2.0</span>
              </a>
            </div>
            <nav style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <a
                href="/finance/settings"
                className="btn btn-secondary"
                style={{ padding: "6px 14px", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}
              >
                <span>Zoho Books</span>
              </a>
              <a
                href="/finance/upload"
                className="btn btn-primary"
                style={{ padding: "6px 14px", fontSize: "13px" }}
              >
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
