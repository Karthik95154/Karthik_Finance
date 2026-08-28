"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Redirects old /finance/integrations route → /integrations (sidebar) */
export default function IntegrationsRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/integrations"); }, [router]);
  return null;
}
