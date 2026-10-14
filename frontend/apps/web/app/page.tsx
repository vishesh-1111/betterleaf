"use client";

import { LandingPage } from "@/components/landing-page";

/**
 * The routing gate is handled server-side in `proxy.ts`: users who are logged
 * in or already have a workspace are redirected to `/workspace` before this
 * page renders, so a brand-new guest (no workspace) always lands here.
 */
export default function Home() {
  return <LandingPage />;
}
