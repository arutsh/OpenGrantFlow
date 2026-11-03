import React, { useState } from "react";
import {
  X,
  Home,
  FileText,
  BarChart3,
  HeartHandshake,
  Sparkles,
  Settings,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { AIChatPanel } from "@/pages/Budgets/components/AIChatPanel";
import { useAiChat } from "@/context/AiChatContext";
import { useAuth } from "@/context/AuthContext";
import ogfIcon from "@/assets/logos/ogf-icon.svg";
import { Link, NavLink } from "react-router-dom";
import { TopBar } from "./TopBar";
import { ImpersonationBanner } from "./ImpersonationBanner";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  // Below `md:` the sidebar is an off-canvas drawer, closed by default —
  // there used to be a shared `isOpen` boolean defaulting to `true` that
  // was meant to also drive a desktop collapse-to-icons mode, but its only
  // toggle button was `md:hidden`, so that mode was never reachable and the
  // `true` default just leaked into mobile as a permanently-visible rail.
  // At `md:`+ the sidebar is simply always expanded, same as it always
  // rendered in practice.
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isGranteesExpanded, setIsGranteesExpanded] = useState(false);
  const { isAiOpen, toggleAi } = useAiChat();
  const { isDonor } = useAuth();

  return (
    <div className="flex w-full h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`
          fixed md:static top-0 left-0 h-full z-20 w-[78%] max-w-[270px] md:max-w-none md:w-64
          bg-slate-700 text-white transition-transform duration-300 flex flex-col
          ${isMobileDrawerOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0
        `}
      >
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-2 overflow-hidden">
            <img src={ogfIcon} alt="" className="h-7 w-auto flex-shrink-0" />
            <span className="font-bold text-base whitespace-nowrap">
              Open Grant <span className="text-teal-400">Flow</span>
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsMobileDrawerOpen(false)}
            aria-label="Close navigation menu"
            className="p-2 rounded-lg text-white hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-400 md:hidden"
          >
            <X size={24} />
          </button>
        </div>

        <nav className="flex-1">
          <ul className="space-y-1">
            <li>
              <Link
                to="/dashboard"
                className="flex items-center gap-3 px-4 py-2 hover:bg-blue-600/60 rounded transition-colors"
              >
                <Home size={20} />
                <span>Dashboard</span>
              </Link>
            </li>
            <li>
              <Link
                to="/budgets"
                className="flex items-center gap-3 px-4 py-2 hover:bg-blue-600/60 rounded transition-colors"
              >
                <FileText size={20} />
                <span>Budgets</span>
              </Link>
            </li>
            <li>
              <Link
                to="/reports"
                className="flex items-center gap-3 px-4 py-2 hover:bg-blue-600/60 rounded transition-colors"
              >
                <BarChart3 size={20} />
                <span>Reports</span>
              </Link>
            </li>
            {isDonor && <li className="my-2 border-t border-slate-600" />}
            {isDonor && (
              <li>
                <button
                  onClick={() => setIsGranteesExpanded(!isGranteesExpanded)}
                  className="w-full flex items-center gap-3 px-4 py-2 hover:bg-blue-600/60 rounded transition-colors"
                >
                  <HeartHandshake size={20} />
                  <span className="flex-1 text-left">Grantees</span>
                  {isGranteesExpanded ? (
                    <ChevronDown size={16} />
                  ) : (
                    <ChevronRight size={16} />
                  )}
                </button>
                {isGranteesExpanded && (
                  <ul className="mt-1 space-y-1">
                    {/* "List of Grantees" and "Budgets" are hidden until those
                        pages are built (they were non-clickable placeholders). */}
                    <li>
                      <Link
                        to="/reports/funded"
                        className="block px-4 py-2 pl-11 text-sm hover:bg-blue-600/60 rounded transition-colors"
                      >
                        Reports
                      </Link>
                    </li>
                  </ul>
                )}
              </li>
            )}
          </ul>
        </nav>

        {/* Settings link pinned above AI Mode */}
        <div className="px-3 pb-1">
          <NavLink
            to="/settings"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-600 text-slate-300 hover:text-white transition-colors"
          >
            <Settings size={20} className="flex-shrink-0" />
            <span className="text-sm font-medium">Settings</span>
          </NavLink>
        </div>

        {/* AI Mode button pinned to bottom of sidebar */}
        <div className="p-3 border-t border-slate-600">
          <button
            onClick={toggleAi}
            title="AI Mode"
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
              isAiOpen
                ? "bg-blue-600 text-white"
                : "hover:bg-slate-600 text-slate-300 hover:text-white"
            }`}
          >
            <Sparkles size={20} className="flex-shrink-0" />
            <span className="text-sm font-medium">AI Mode</span>
          </button>
        </div>
      </aside>

      {/* Scrim — mounted only while the mobile drawer is open, so it never
          outlives the drawer it's dimming for. */}
      {isMobileDrawerOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-10 md:hidden"
          onClick={() => setIsMobileDrawerOpen(false)}
        />
      )}

      {/* Main content + AI panel, with a global top bar above both */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <ImpersonationBanner />
        <TopBar onOpenMenu={() => setIsMobileDrawerOpen(true)} />
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 p-4 sm:p-8 overflow-auto bg-gray-50">{children}</main>

          {isAiOpen && <AIChatPanel />}
        </div>
      </div>
    </div>
  );
}
