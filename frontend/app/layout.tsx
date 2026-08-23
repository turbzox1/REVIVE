import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "REVIVE — Revenue Recovery & Decision Engine",
  description: "Don't just detect lost revenue. Decide how to recover it.",
};

const nav = [
  { href: "/", label: "Command Center" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/evaluation", label: "Evaluation" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
          <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-4">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-xl font-bold tracking-tight text-emerald-400">REVIVE</span>
              <span className="hidden text-xs text-slate-500 md:inline">
                Autonomous Revenue Recovery & Decision Engine
              </span>
            </Link>
            <nav className="ml-auto flex gap-1 text-sm">
              {nav.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="rounded-md px-3 py-1.5 text-slate-300 transition hover:bg-slate-800 hover:text-white"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-7xl px-6 pb-10 pt-4 text-xs text-slate-600">
          Razorpay Buildathon prototype · Test Mode execution is real API calls; actions labelled
          &quot;Simulated&quot; use the synthetic outcome engine.
        </footer>
      </body>
    </html>
  );
}
