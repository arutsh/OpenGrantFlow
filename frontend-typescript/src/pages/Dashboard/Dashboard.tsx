import { useAuth } from "../../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getUserProfile } from "@/api/usersApi";
import { getUserIdFromToken } from "@/utils/token";
import GranteeDashboard from "./GranteeDashboard";
import DonorDashboard from "@/pages/DonorDashboard/DonorDashboard";

type DashboardView = "grantee" | "donor";

export default function Dashboard() {
  const { token, isRegistering, isNgo, isDonor } = useAuth();
  // Greet by the first name given at sign-up; fall back to a neutral "there"
  // so the login email is never shown in the heading.
  const userId = getUserIdFromToken(token);
  const profileQuery = useQuery({
    queryKey: ["userProfile", userId],
    queryFn: () => getUserProfile(userId as string),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000,
  });
  const firstName = profileQuery.data?.first_name?.trim();
  const navigate = useNavigate();

  useEffect(() => {
    console.log("Dashboard - isRegistering:", isRegistering);
    if (isRegistering) {
      navigate("/onboarding");
    }
  }, [isRegistering]);

  // A customer can be both a grantee (owns budgets) and a donor (funds
  // others') at once — show a toggle only when both roles apply; otherwise
  // there's exactly one relevant dashboard, so skip the switcher entirely.
  const hasBothRoles = isNgo && isDonor;
  const [view, setView] = useState<DashboardView>(isDonor && !isNgo ? "donor" : "grantee");

  const activeView: DashboardView = hasBothRoles ? view : isDonor ? "donor" : "grantee";

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <div className="mb-12">
        <div className="flex items-center justify-between mb-2 flex-wrap gap-4">
          <h1 className="text-4xl font-bold text-slate-900">
            Hi {firstName || "there"} 👋
          </h1>
          {hasBothRoles && (
            <div
              role="tablist"
              aria-label="Dashboard view"
              className="inline-flex p-1 gap-0.5 bg-white border border-slate-200 rounded-xl shadow-sm"
            >
              <button
                type="button"
                role="tab"
                aria-selected={view === "grantee"}
                onClick={() => setView("grantee")}
                className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
                  view === "grantee"
                    ? "bg-slate-800 text-white"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Grantee
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={view === "donor"}
                onClick={() => setView("donor")}
                className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
                  view === "donor"
                    ? "bg-slate-800 text-white"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Donor
              </button>
            </div>
          )}
        </div>
        <p className="text-gray-600">
          {activeView === "donor"
            ? "Everything you fund, in one place."
            : "Here's what's happening with your budgets today."}
        </p>
      </div>

      {activeView === "donor" ? <DonorDashboard /> : <GranteeDashboard />}
    </div>
  );
}
