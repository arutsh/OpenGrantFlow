import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import PublicLayout from "@/components/site/PublicLayout";
import LandingPage from "./LandingPage";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<LandingPage />} />
          </Route>
          <Route path="/dashboard" element={<div>Dashboard Page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LandingPage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders the mission-driven content when unauthenticated", () => {
    renderAt("/");

    expect(
      screen.getByText("Grant management without spreadsheets."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Become a Founding Design Partner" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Become a Founding Design Partner" }),
    ).toBeInTheDocument();
  });

  it("offers a Request Demo CTA in the shared nav that points to the contact page", () => {
    renderAt("/");

    const requestDemoLinks = screen.getAllByRole("link", {
      name: "Request Demo",
    });
    expect(requestDemoLinks.length).toBeGreaterThan(0);
    expect(requestDemoLinks[0]).toHaveAttribute("href", "/contact");
  });

  it("renders the product demo embed", () => {
    renderAt("/");

    const demoFrame = screen.getByTitle(
      "OpenGrantFlow - Grant Management Without Spreadsheets",
    );
    expect(demoFrame.tagName).toBe("IFRAME");
    expect(demoFrame).toHaveAttribute(
      "src",
      expect.stringContaining(
        "https://demo.arcade.software/video/bJX6Bh5bfgTZU5E2pUSK",
      ),
    );
    expect(demoFrame).toHaveAttribute("loading", "lazy");
  });

  it("does not offer login/sign-up/get-started anywhere on the page", () => {
    renderAt("/");

    expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^log in$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/get started/i)).not.toBeInTheDocument();
  });

  it("renders the contact form and submits to Web3Forms", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));

    renderAt("/");

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Organisation")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
    expect(
      screen.getByLabelText("I'd like to request a demo"),
    ).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Name"), "Jane Doe");
    await userEvent.type(
      screen.getByLabelText("Organisation"),
      "Acme Foundation",
    );
    await userEvent.type(screen.getByLabelText("Email"), "jane@example.org");
    await userEvent.selectOptions(screen.getByLabelText("Role"), "Foundation");
    await userEvent.type(
      screen.getByLabelText("Message"),
      "We'd love to talk.",
    );
    await userEvent.click(screen.getByLabelText("I'd like to request a demo"));
    await userEvent.click(
      screen.getByRole("button", { name: "Let's Start a Conversation" }),
    );

    expect(
      await screen.findByText(/we've received your message/i),
    ).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.web3forms.com/submit",
      expect.objectContaining({ method: "POST" }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
    expect(body).toMatchObject({
      name: "Jane Doe",
      organisation: "Acme Foundation",
      email: "jane@example.org",
      role: "Foundation",
      message: "We'd love to talk.",
      request_demo: true,
    });

    fetchMock.mockRestore();
  });

  it("shows an error message when the contact form submission fails", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockRejectedValue(new Error("network error"));

    renderAt("/");

    await userEvent.type(screen.getByLabelText("Name"), "Jane Doe");
    await userEvent.type(
      screen.getByLabelText("Organisation"),
      "Acme Foundation",
    );
    await userEvent.type(screen.getByLabelText("Email"), "jane@example.org");
    await userEvent.selectOptions(screen.getByLabelText("Role"), "Foundation");
    await userEvent.type(
      screen.getByLabelText("Message"),
      "We'd love to talk.",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Let's Start a Conversation" }),
    );

    expect(
      await screen.findByText(/something went wrong sending your message/i),
    ).toBeInTheDocument();

    fetchMock.mockRestore();
  });

  it("redirects to /dashboard when authenticated", () => {
    localStorage.setItem("token", "fake-token");
    localStorage.setItem("username", "john");

    renderAt("/");

    expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    expect(
      screen.queryByText("Grant management without spreadsheets."),
    ).not.toBeInTheDocument();
  });
});
