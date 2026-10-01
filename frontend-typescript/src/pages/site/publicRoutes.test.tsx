import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";

function makeFakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function renderAppAt(path: string) {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

function signInAsVerifiedUser() {
  localStorage.setItem(
    "token",
    makeFakeJwt({ user_id: "u1", email_verified: true }),
  );
  localStorage.setItem("username", "jane@example.com");
}

describe("public site routing", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it.each([false, true])(
    "keeps About, Contact and demo navigation public (authenticated: %s)",
    async (authenticated) => {
      if (authenticated) signInAsVerifiedUser();
      renderAppAt("/security");

      await userEvent.click(screen.getAllByRole("link", { name: "About" })[0]);
      expect(window.location.pathname).toBe("/about");
      expect(screen.getByRole("heading", { name: "Built from lived experience" })).toBeInTheDocument();

      await userEvent.click(screen.getAllByRole("link", { name: "Contact" })[0]);
      expect(window.location.pathname).toBe("/contact");
      expect(screen.getByRole("heading", { name: "Start a conversation" })).toBeInTheDocument();

      await userEvent.click(screen.getAllByRole("link", { name: "Security" })[0]);
      await userEvent.click(screen.getByRole("link", { name: "Request Demo" }));
      expect(window.location.pathname).toBe("/contact");
      expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();

      await userEvent.click(screen.getAllByRole("link", { name: "Security" })[0]);
      await userEvent.click(screen.getByRole("link", { name: "request a demo" }));
      expect(window.location.pathname).toBe("/contact");
      expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();
    },
  );

  it.each(["/", "/legal"])(
    "renders %s inside the shared public header and footer",
    async (path) => {
      renderAppAt(path);

      expect(
        await screen.findByRole("navigation", { name: "Primary" }),
      ).toBeInTheDocument();
      expect(screen.getAllByRole("banner")).toHaveLength(1);
      expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
    },
  );

  it("renders How it works directly for an anonymous visitor, with its title", async () => {
    renderAppAt("/how-it-works");

    await waitFor(() => {
      expect(
        screen.getByText("One continuous financial record, from budget to report"),
      ).toBeInTheDocument();
    });
    expect(document.title).toBe("How it works · Open Grant Flow");
  });

  it("renders How it works for an authenticated visitor without redirecting", async () => {
    signInAsVerifiedUser();

    renderAppAt("/how-it-works");

    await waitFor(() => {
      expect(
        screen.getByText("One continuous financial record, from budget to report"),
      ).toBeInTheDocument();
    });
  });

  it("renders Security & data directly for an anonymous visitor, with its title", async () => {
    renderAppAt("/security");

    await waitFor(() => {
      expect(
        screen.getByText("Handled with the care we'd want for our own data"),
      ).toBeInTheDocument();
    });
    expect(document.title).toBe("Security & data · Open Grant Flow");
  });

  it("renders Security & data for an authenticated visitor without redirecting", async () => {
    signInAsVerifiedUser();

    renderAppAt("/security");

    await waitFor(() => {
      expect(
        screen.getByText("Handled with the care we'd want for our own data"),
      ).toBeInTheDocument();
    });
  });
});
