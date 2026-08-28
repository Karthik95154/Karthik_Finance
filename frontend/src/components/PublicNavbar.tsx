"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, ShieldCheck, Menu, X } from "lucide-react";

export default function PublicNavbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 100,
        background: "rgba(255, 255, 255, 0.92)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--border-subtle)",
        transition: "all 0.2s ease",
      }}
    >
      <div
        className="container"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "64px",
        }}
      >
        {/* Brand */}
        <Link
          href="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            textDecoration: "none",
          }}
        >
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              boxShadow: "0 2px 8px rgba(0, 113, 227, 0.3)",
            }}
          >
            <ShieldCheck size={18} />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
            <span
              style={{
                fontSize: "19px",
                fontWeight: "700",
                letterSpacing: "-0.03em",
                color: "var(--text-primary)",
              }}
            >
              Finance
            </span>
            <span
              style={{
                fontSize: "10px",
                fontWeight: "600",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                padding: "2px 6px",
                borderRadius: "4px",
                background: "rgba(0, 113, 227, 0.08)",
                color: "var(--accent)",
              }}
            >
              Autonomous AP
            </span>
          </div>
        </Link>

        {/* Desktop Nav Links */}
        <nav
          style={{
            display: "none",
            alignItems: "center",
            gap: "28px",
            fontSize: "14px",
            fontWeight: "500",
            color: "var(--text-secondary)",
          }}
          className="desktop-nav"
        >
          <a
            href="/#how-it-works"
            style={{
              color: "var(--text-secondary)",
              transition: "color 0.15s ease",
            }}
            onMouseOver={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseOut={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            How It Works
          </a>
          <a
            href="/#capabilities"
            style={{
              color: "var(--text-secondary)",
              transition: "color 0.15s ease",
            }}
            onMouseOver={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseOut={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            Capabilities
          </a>
          <a
            href="/#workflow"
            style={{
              color: "var(--text-secondary)",
              transition: "color 0.15s ease",
            }}
            onMouseOver={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseOut={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            Finance Workflow
          </a>
        </nav>

        {/* Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Link
            href="/sign-in"
            className="btn btn-secondary"
            style={{
              padding: "7px 16px",
              fontSize: "13px",
              fontWeight: "600",
            }}
          >
            Sign In
          </Link>

          <Link
            href="/sign-up"
            className="btn btn-primary"
            style={{
              padding: "7px 18px",
              fontSize: "13px",
              fontWeight: "600",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span>Get Started</span>
            <ArrowRight size={14} />
          </Link>

          {/* Mobile Menu Toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{
              display: "none",
              padding: "6px",
              color: "var(--text-primary)",
            }}
            className="mobile-toggle"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown */}
      {mobileMenuOpen && (
        <div
          style={{
            padding: "16px 24px 20px",
            background: "#ffffff",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            fontSize: "14px",
            fontWeight: "500",
          }}
        >
          <a
            href="/#how-it-works"
            onClick={() => setMobileMenuOpen(false)}
            style={{ color: "var(--text-primary)" }}
          >
            How It Works
          </a>
          <a
            href="/#capabilities"
            onClick={() => setMobileMenuOpen(false)}
            style={{ color: "var(--text-primary)" }}
          >
            Capabilities
          </a>
          <a
            href="/#workflow"
            onClick={() => setMobileMenuOpen(false)}
            style={{ color: "var(--text-primary)" }}
          >
            Finance Workflow
          </a>
          <hr style={{ border: "none", borderTop: "1px solid var(--border-subtle)" }} />
          <Link
            href="/sign-in"
            onClick={() => setMobileMenuOpen(false)}
            style={{ color: "var(--text-primary)" }}
          >
            Sign In
          </Link>
          <Link
            href="/sign-up"
            onClick={() => setMobileMenuOpen(false)}
            style={{ color: "var(--accent)", fontWeight: "600" }}
          >
            Get Started →
          </Link>
        </div>
      )}

      <style jsx>{`
        @media (min-width: 768px) {
          .desktop-nav {
            display: flex !important;
          }
          .mobile-toggle {
            display: none !important;
          }
        }
        @media (max-width: 767px) {
          .mobile-toggle {
            display: block !important;
          }
        }
      `}</style>
    </header>
  );
}
