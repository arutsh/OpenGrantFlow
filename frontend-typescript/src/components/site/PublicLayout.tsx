import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Menu, X, Github, Linkedin } from "lucide-react";
import ogfIcon from "@/assets/logos/ogf-icon.svg";

const NAV_LINKS = [
  { to: "/how-it-works", label: "How it works" },
  { to: "/security", label: "Security" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

const FOOTER_LINKS = [
  { to: "/", label: "Home" },
  { to: "/how-it-works", label: "How it works" },
  { to: "/security", label: "Security" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

function useHashScroll() {
  const location = useLocation();

  useEffect(() => {
    if (!location.hash) return;
    const id = location.hash.slice(1);
    document.getElementById(id)?.scrollIntoView();
  }, [location.pathname, location.hash]);
}

function RequestDemoButton({ className = "" }: { className?: string }) {
  return (
    <Link
      to="/contact"
      className={`rounded-lg px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium text-white transition-opacity hover:opacity-90 whitespace-nowrap bg-brand-navy ${className}`}
    >
      Request Demo
    </Link>
  );
}

function PublicHeader() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="border-b border-slate-200">
      <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-5">
        <Link to="/" className="flex items-center gap-2">
          <img src={ogfIcon} alt="" className="h-8 w-auto shrink-0" />
          <span
            className="text-lg sm:text-xl font-bold whitespace-nowrap text-brand-slate"
          >
            Open Grant <span className="text-brand-teal">Flow</span>
          </span>
        </Link>
        <div className="flex items-center gap-3 sm:gap-6">
          <nav aria-label="Primary" className="hidden sm:flex gap-6">
            {NAV_LINKS.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className="text-sm font-medium hover:opacity-70 text-brand-slate"
              >
                {label}
              </Link>
            ))}
          </nav>
          <RequestDemoButton className="hidden sm:inline-block" />
          <button
            type="button"
            className="sm:hidden"
            aria-label="Toggle navigation menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? (
              <X size={22} className="text-brand-slate" />
            ) : (
              <Menu size={22} className="text-brand-slate" />
            )}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <nav
          aria-label="Mobile"
          className="sm:hidden flex flex-col gap-1 px-6 pb-4"
        >
          {NAV_LINKS.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className="py-2 text-sm font-medium text-brand-slate"
              onClick={() => setMobileOpen(false)}
            >
              {label}
            </Link>
          ))}
          <RequestDemoButton className="mt-2 text-center" />
        </nav>
      )}
    </header>
  );
}

function PublicFooter() {
  return (
    <footer className="border-t border-slate-200 px-6 py-10">
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between gap-6">
        <div>
          <p className="font-bold text-brand-slate">
            Open Grant Flow
          </p>
          <p className="text-sm text-slate-500">
            Open-source grant financial management platform.
          </p>
        </div>
        <div className="flex flex-col sm:items-end gap-3">
          <nav
            className="flex flex-wrap gap-4 text-sm text-brand-slate"
          >
            {FOOTER_LINKS.map(({ to, label }) => (
              <Link key={to} to={to} className="hover:opacity-70">
                {label}
              </Link>
            ))}
          </nav>
          <div className="flex gap-4">
            <a
              href="https://github.com/arutsh/OpenGrantFlow"
              className="text-slate-500 hover:opacity-70"
              aria-label="GitHub"
            >
              <Github size={20} />
            </a>
            <a
              href="https://www.linkedin.com/in/norair-arutshyan"
              className="text-slate-500 hover:opacity-70"
              aria-label="LinkedIn"
            >
              <Linkedin size={20} />
            </a>
          </div>
          <div className="flex gap-4 text-sm text-slate-500">
            <Link to="/legal#privacy" className="hover:opacity-70">
              Privacy Policy
            </Link>
            <Link to="/legal#terms" className="hover:opacity-70">
              Terms
            </Link>
          </div>
          <p className="text-xs text-slate-400">
            © {new Date().getFullYear()} Open Grant Flow
          </p>
        </div>
      </div>
    </footer>
  );
}

export default function PublicLayout() {
  useHashScroll();

  return (
    <div className="min-h-screen bg-brand-off-white">
      <PublicHeader />
      <Outlet />
      <PublicFooter />
    </div>
  );
}
