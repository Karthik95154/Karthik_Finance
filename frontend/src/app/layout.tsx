import "../styles/globals.css";
import React from "react";
import NetworkStatusBanner from "@/components/NetworkStatusBanner";

export const metadata = {
  title: "Sakshi Finance | Autonomous AI Accounting & AP Automation",
  description: "AI-powered invoice extraction, deterministic GST & ITC, TDS analysis, and balanced double-entry accounting engine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <NetworkStatusBanner />
        {children}
      </body>
    </html>
  );
}
