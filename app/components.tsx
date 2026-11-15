"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" aria-label="Trikaaya Sports home" className="brand-link flex items-center gap-3">
      <Image src="/trikaaya-logo.jpg" alt="Trikaaya logo" width={180} height={180} className="h-12 w-12 rounded-full object-cover" priority />
      <span className={`text-xl font-extrabold tracking-tight ${light ? "text-white" : "text-trikaaya-dark"}`}>
        trikaaya<span className="block text-[9px] font-extrabold tracking-[.3em] text-trikaaya-lemon">TRI · FORM · BODY</span>
      </span>
    </Link>
  );
}

export function Header() {
  const [open, setOpen] = useState(false);
  const links = [{ href: "/#about", label: "About" }, { href: "/#program", label: "Taekwondo" }, { href: "/#contact", label: "Contact" }];
  return (
    <header className="relative z-30 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 md:px-8">
      <Brand light />
      <nav aria-label="Main navigation" className="hidden items-center gap-8 text-sm font-bold md:flex">
        {links.map((item) => <Link key={item.href} href={item.href} className="nav-link text-white/80 hover:text-white">{item.label}</Link>)}
        <Link href="/signin" className="button-outline rounded-full border border-white/30 px-5 py-3 text-white">Sign in</Link>
      </nav>
      <button type="button" className="menu-toggle rounded-full border border-white/30 px-4 py-2 text-sm font-bold text-white md:hidden" aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen((v) => !v)}>
        {open ? "Close" : "Menu"}
      </button>
      {open && (
        <nav id="mobile-navigation" aria-label="Mobile navigation" className="mobile-nav absolute left-5 right-5 top-[calc(100%-4px)] flex flex-col gap-1 rounded-2xl border border-white/10 bg-trikaaya-dark text-white p-3 shadow-xl md:hidden">
          {links.map((item) => <Link key={item.href} href={item.href} onClick={() => setOpen(false)} className="rounded-xl px-4 py-3 text-sm font-bold transition-colors hover:bg-white/10">{item.label}</Link>)}
          <Link href="/signin" onClick={() => setOpen(false)} className="mt-1 rounded-xl bg-trikaaya-lemon px-4 py-3 text-sm font-bold text-trikaaya-dark">Sign in</Link>
        </nav>
      )}
    </header>
  );
}
