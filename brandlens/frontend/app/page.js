// frontend/app/page.js
// Home route: sends the visitor to /login or /dashboard depending on whether they are logged in.

"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "../lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getAuth() ? "/dashboard" : "/login");
  }, [router]);

  return <div>Loading...</div>;
}
