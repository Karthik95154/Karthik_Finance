import "../styles/globals.css";
import React from "react";

export const metadata = {
  title: "Finance Module | Autonomous Accounts Payable & Accounting",
  description: "AI-powered invoice extraction, deterministic GST & ITC, TDS analysis, and balanced double-entry accounting engine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
