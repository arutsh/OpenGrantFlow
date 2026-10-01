import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ContactPage from "./Contact";

function renderPage() {
  return render(
    <MemoryRouter>
      <ContactPage />
    </MemoryRouter>,
  );
}

async function fillRequiredFields({ email = "jane@example.org" } = {}) {
  await userEvent.type(screen.getByLabelText("Name"), "Jane Doe");
  if (email) await userEvent.type(screen.getByLabelText("Work email"), email);
  await userEvent.type(screen.getByLabelText("Organisation"), "Acme Foundation");
  await userEvent.selectOptions(screen.getByLabelText("Organisation type"), "Foundation");
}

describe("ContactPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("renders the demo request intro, pilot programme and FAQ", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Start a conversation" }),
    ).toBeInTheDocument();
    expect(document.getElementById("pilot")).toHaveTextContent("Become a Pilot Partner");
    expect(screen.getByText("What you receive")).toBeInTheDocument();
    expect(screen.getByText("What we ask")).toBeInTheDocument();
    expect(screen.getByText("Is Open Grant Flow free?")).toBeInTheDocument();
  });

  it("links the form to the privacy policy", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "privacy policy" })).toHaveAttribute(
      "href",
      "/legal#privacy",
    );
  });

  it("sends a complete demo request, including organisation type and pilot interest", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));
    renderPage();

    await fillRequiredFields();
    await userEvent.type(
      screen.getByLabelText(/How long does a donor report take/),
      "About two weeks",
    );
    await userEvent.click(
      screen.getByLabelText("I'm interested in becoming a Pilot Partner"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Request a demo" }));

    expect(await screen.findByText(/we've received your request/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.web3forms.com/submit",
      expect.objectContaining({ method: "POST" }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
    expect(body).toMatchObject({
      name: "Jane Doe",
      email: "jane@example.org",
      organisation: "Acme Foundation",
      organisation_type: "Foundation",
      reporting_time: "About two weeks",
      pilot_interest: true,
    });
  });

  it("does not send the request and flags the field when the work email is missing", async () => {
    const fetchMock = vi.spyOn(global, "fetch");
    renderPage();

    await fillRequiredFields({ email: "" });
    await userEvent.click(screen.getByRole("button", { name: "Request a demo" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Work email")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows an error message when the submission fails", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("network error"));
    renderPage();

    await fillRequiredFields();
    await userEvent.click(screen.getByRole("button", { name: "Request a demo" }));

    expect(
      await screen.findByText(/something went wrong sending your request/i),
    ).toBeInTheDocument();
  });

  it("hides the draft pilot details and time-expectations answer in production", () => {
    vi.stubEnv("PROD", true);

    renderPage();

    expect(screen.queryByText("How the pilot runs")).not.toBeInTheDocument();
    expect(screen.queryByText("How much time does a pilot take?")).not.toBeInTheDocument();
    expect(screen.queryByText("TBC")).not.toBeInTheDocument();
  });
});
