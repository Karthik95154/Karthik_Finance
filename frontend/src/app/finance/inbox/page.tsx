"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Redirects old /finance/inbox route → /inbox (sidebar) */
export default function InboxRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/inbox"); }, [router]);
  return null;
}
