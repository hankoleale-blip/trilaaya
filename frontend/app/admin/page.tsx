"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowUpRight, LockKeyhole, ShieldCheck } from "lucide-react";
import { Brand } from "../components";
import { PageEntrance } from "../motion";

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        cache: "no-store",
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to sign in. Check your credentials and try again.");
      router.replace("/admin/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The Admin service is unavailable. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageEntrance>
      <main className="grid min-h-screen bg-trikaaya-cream lg:grid-cols-[1.02fr_.98fr]">
        <aside className="sport-panel relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex xl:p-16">
          <Brand light />
          <div className="pointer-events-none absolute -right-24 top-1/4 h-96 w-96 rounded-full border border-white/10" />
          <div className="pointer-events-none absolute -right-8 top-[34%] h-64 w-64 rounded-full border border-trikaaya-lemon/30" />
          <div className="relative max-w-xl">
            <p className="text-xs font-black uppercase tracking-[.3em] text-trikaaya-lemon">TRI · FORM · BODY / CONTROL CENTRE</p>
            <h1 className="mt-7 text-6xl font-black leading-[.96] tracking-[-.065em] xl:text-7xl">LEAD THE<br />NEXT <span className="text-trikaaya-lemon">MOVE.</span></h1>
            <p className="mt-7 max-w-md text-base leading-8 text-white/65">A private workspace for Trikaaya Sports administration. Sign in with your provisioned administrator account.</p>
          </div>
          <p className="text-[10px] font-extrabold tracking-[.25em] text-white/35">PRIVATE ADMINISTRATOR ACCESS</p>
        </aside>

        <section className="flex items-center justify-center px-5 py-12 md:px-10">
          <div className="w-full max-w-md">
            <div className="mb-12 lg:hidden"><Brand /></div>
            <Link href="/" className="inline-flex items-center gap-2 text-sm font-bold text-trikaaya-slate transition hover:text-trikaaya-dark"><ArrowLeft size={16} /> Back to website</Link>
            <div className="mt-9 rounded-[1.75rem] border border-slate-200 bg-white p-7 shadow-[0_28px_80px_rgba(16,27,45,.09)] md:p-9">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-trikaaya-lemon text-trikaaya-dark"><ShieldCheck size={27} /></div>
              <p className="mt-8 text-[10px] font-black uppercase tracking-[.28em] text-trikaaya-olive">Restricted area</p>
              <h2 className="mt-2 text-3xl font-black tracking-[-.05em]">Admin sign in<span className="text-trikaaya-olive">.</span></h2>
              <p className="mt-3 text-sm leading-6 text-trikaaya-slate">Use the credentials created through the private backend bootstrap process.</p>

              <form onSubmit={submit} className="mt-8 space-y-5">
                <label className="block text-sm font-extrabold text-trikaaya-dark">Admin email
                  <input autoComplete="username" required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-trikaaya-cream px-4 py-3.5 outline-none transition focus:border-trikaaya-olive focus:bg-white" placeholder="admin@example.com" />
                </label>
                <label className="block text-sm font-extrabold text-trikaaya-dark">Password
                  <input autoComplete="current-password" required type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-trikaaya-cream px-4 py-3.5 outline-none transition focus:border-trikaaya-olive focus:bg-white" placeholder="Enter your password" />
                </label>
                {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</p>}
                <button type="submit" disabled={submitting} className="button-primary flex w-full items-center justify-center gap-3 rounded-full bg-trikaaya-dark px-5 py-4 text-sm font-black text-white disabled:cursor-wait disabled:opacity-60">
                  {submitting ? "VERIFYING ACCESS…" : "SIGN IN SECURELY"} {!submitting && <ArrowUpRight size={17} />}
                </button>
              </form>
              <div className="mt-6 flex items-start gap-3 rounded-xl bg-[#F0F4FA] p-4"><LockKeyhole size={17} className="mt-0.5 shrink-0 text-trikaaya-olive" /><p className="text-xs leading-6 text-trikaaya-slate">Admin accounts are provisioned privately. There is no public Admin registration or password reset flow in this phase.</p></div>
            </div>
            <p className="mt-6 text-center text-[10px] font-bold uppercase tracking-[.2em] text-trikaaya-slate/70">Trikaaya Sports · Secure access</p>
          </div>
        </section>
      </main>
    </PageEntrance>
  );
}
