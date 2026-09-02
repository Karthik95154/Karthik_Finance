import "../styles/globals.css";
import React from "react";
import NetworkStatusBanner from "@/components/NetworkStatusBanner";

export const metadata = {
  title: "Sakshi Finance | Internal Finance HITL Review",
  description: "Internal Finance HITL Review Queue, Line Item Accounting, and Statutory Approval Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <NetworkStatusBanner />
        {children}
      </body>
    </html>
  );
}
