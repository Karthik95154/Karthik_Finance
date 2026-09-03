"use client";

import React, { useState, useEffect } from "react";
import { WifiOff, Wifi, AlertTriangle, X, RefreshCw } from "lucide-react";
import { getHealth } from "@/lib/api";

export default function NetworkStatusBanner() {
  const [isBrowserOnline, setIsBrowserOnline] = useState<boolean>(true);
  const [isServerReachable, setIsServerReachable] = useState<boolean>(true);
  const [showRestoredMessage, setShowRestoredMessage] = useState<boolean>(false);
  const [dismissed, setDismissed] = useState<boolean>(false);

  useEffect(() => {
    // Initial browser state
    if (typeof window !== "undefined") {
      setIsBrowserOnline(navigator.onLine);

      const handleOnline = () => {
        setIsBrowserOnline(true);
        setDismissed(false);
        setShowRestoredMessage(true);
        setTimeout(() => setShowRestoredMessage(false), 4000);
      };

      const handleOffline = () => {
        setIsBrowserOnline(false);
        setDismissed(false);
      };

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      // Periodically check server reachability
      const checkServer = async () => {
        try {
          await getHealth();
          if (!isServerReachable) {
            setIsServerReachable(true);
            setShowRestoredMessage(true);
            setTimeout(() => setShowRestoredMessage(false), 4000);
          }
        } catch {
          setIsServerReachable(false);
        }
      };

      checkServer();
      const interval = setInterval(checkServer, 15000);

      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
        clearInterval(interval);
      };
    }
  }, [isServerReachable]);

  const isOffline = !isBrowserOnline || !isServerReachable;

  if (dismissed && !showRestoredMessage) return null;

  if (showRestoredMessage) {
    return (
      <div
        style={{
          position: "fixed",
          top: "16px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 99999,
          backgroundColor: "#166534",
          color: "#ffffff",
          padding: "10px 20px",
          borderRadius: "30px",
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.2)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          fontSize: "13px",
          fontWeight: "600",
          animation: "slideDown 0.3s ease-out",
        }}
      >
        <Wifi size={16} />
        <span>You are back online. All finance services restored.</span>
      </div>
    );
  }

  if (isOffline) {
    return (
      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 99999,
          backgroundColor: "#b91c1c",
          color: "#ffffff",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: "0 2px 10px rgba(0, 0, 0, 0.15)",
          fontSize: "13px",
          fontWeight: "500",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", margin: "0 auto" }}>
          <WifiOff size={18} />
          <span>
            {!isBrowserOnline
              ? "You are currently offline. Please check your internet connection."
              : "Unable to connect to the finance server. Attempting to reconnect..."}
          </span>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              marginLeft: "12px",
              padding: "3px 10px",
              backgroundColor: "#ffffff",
              color: "#b91c1c",
              border: "none",
              borderRadius: "4px",
              fontSize: "12px",
              fontWeight: "700",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <RefreshCw size={12} />
            <span>Retry</span>
          </button>
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          style={{
            background: "transparent",
            border: "none",
            color: "rgba(255,255,255,0.8)",
            cursor: "pointer",
            padding: "4px",
            display: "flex",
            alignItems: "center",
          }}
          title="Dismiss warning"
        >
          <X size={16} />
        </button>
      </div>
    );
  }

  return null;
}
