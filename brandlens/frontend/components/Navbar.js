"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getAuth, clearAuth } from "../lib/auth";

const LINKS = {
  creator: [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/upload", label: "New Content" },
  ],
  manager: [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/rulebook", label: "Rule Book" },
  ],
  reviewer: [{ href: "/dashboard", label: "Review Queue" }],
};

export default function Navbar() {
  const [auth, setAuth] = useState(null);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    setAuth(getAuth());
  }, [pathname]);

  function logout() {
    clearAuth();
    setAuth(null);
    router.push("/login");
  }

  const links = auth ? LINKS[auth.role] || [] : [];

  return (
    <nav className="navbar">
      <Link href="/" className="logo">BrandLens</Link>
      {links.map((l) => (
        <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
          {l.label}
        </Link>
      ))}
      {auth && (
        <>
          <span className="role">{auth.role}</span>
          <button onClick={logout}>Logout</button>
        </>
      )}
    </nav>
  );
}