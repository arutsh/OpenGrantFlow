import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { axiosHttpError, withQueryClient } from "@/test/queryClient";
import gatewayApi from "@/api/gatewayApi";
import type { SiteAssistantAnswer } from "@/api/siteAssistantApi";
import { SiteAssistantBox } from "./SiteAssistantBox";

vi.mock("@/api/gatewayApi", () => ({ default: { post: vi.fn() } }));

const postMock = vi.mocked(gatewayApi.post);

function answerWith(data: SiteAssistantAnswer) {
  postMock.mockResolvedValue({ data });
}

function sentBody() {
  return postMock.mock.calls[0][1];
}


function renderBox(maxQuestionChars = 500) {
  return render(
    withQueryClient(
      <MemoryRouter>
        <SiteAssistantBox maxQuestionChars={maxQuestionChars} />
      </MemoryRouter>,
    ),
  );
}

async function askQuestion(text = "How do exports work?") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Your question"), text);
  await user.click(screen.getByRole("button", { name: "Ask" }));
  return user;
}

function expectBrowseLinks() {
  expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute(
    "href",
    "/how-it-works",
  );
  expect(screen.getByRole("link", { name: "Security & data" })).toHaveAttribute(
    "href",
    "/security",
  );
}

beforeEach(() => {
  postMock.mockReset();
});

describe("SiteAssistantBox", () => {
  it("shows the AI-processing notice and privacy link before any question", () => {
    renderBox();

    expect(screen.getByText(/sent to an AI provider/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "privacy policy" })).toHaveAttribute(
      "href",
      "/legal#privacy-processors",
    );
  });

  it("sends the selected persona with the question", async () => {
    answerWith({ answer: "No.", answerable: false, citations: [] });
    renderBox();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Funder" }));
    expect(screen.getByRole("button", { name: "Funder" })).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByLabelText("Your question"), "Can I see grantee reports?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(sentBody()).toEqual({
      question: "Can I see grantee reports?",
      persona: "funder",
    });
  });

  it("sends no persona when none is chosen", async () => {
    answerWith({ answer: "No.", answerable: false, citations: [] });
    renderBox();

    await askQuestion();

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(sentBody()).toEqual({ question: "How do exports work?", persona: null });
  });

  it("limits the field to the configured maximum length", async () => {
    renderBox(10);
    const field = screen.getByLabelText("Your question");

    expect(field).toHaveAttribute("maxLength", "10");
    await userEvent.setup().type(field, "this is far longer than ten");
    expect(field).toHaveValue("this is fa");
  });

  it("disables submit until the response arrives", async () => {
    let resolve: (value: { data: SiteAssistantAnswer }) => void = () => {};
    postMock.mockReturnValue(new Promise((r) => (resolve = r)));
    renderBox();

    await askQuestion();

    expect(await screen.findByRole("button", { name: "Asking…" })).toBeDisabled();
    resolve({ data: { answer: "Done.", answerable: true, citations: [] } });
    expect(await screen.findByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("shows a cited answer with one link per citation", async () => {
    answerWith({
      answer: "You can export budgets to Excel.",
      answerable: true,
      citations: [
        { content_id: "a", url: "/how-it-works#export", title: "How it works: Export" },
        { content_id: "b", url: "/guides/budgets#excel", title: "Budgets guide: Excel" },
      ],
    });
    renderBox();

    await askQuestion();

    expect(await screen.findByText("You can export budgets to Excel.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "How it works: Export" })).toHaveAttribute(
      "href",
      "/how-it-works#export",
    );
    expect(screen.getByRole("link", { name: "Budgets guide: Excel" })).toHaveAttribute(
      "href",
      "/guides/budgets#excel",
    );
  });

  it("drops citations that are not site paths", async () => {
    answerWith({
      answer: "See this.",
      answerable: true,
      citations: [
        { content_id: "a", url: "https://evil.example/x", title: "Evil" },
        { content_id: "b", url: "//evil.example/y", title: "Also evil" },
        { content_id: "d", url: "/\\evil.example/z", title: "Backslash evil" },
        { content_id: "c", url: "/about#team", title: "About: Team" },
      ],
    });
    renderBox();

    await askQuestion();

    expect(await screen.findByRole("link", { name: "About: Team" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Evil" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Also evil" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Backslash evil" })).not.toBeInTheDocument();
  });

  it("renders markup in the answer as literal text", async () => {
    const markup = '<b>bold</b><img src="x" onerror="alert(1)">';
    answerWith({ answer: markup, answerable: true, citations: [] });
    const { container } = renderBox();

    await askQuestion();

    expect(await screen.findByText(markup)).toBeInTheDocument();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("falls back to browse links for an unanswerable question", async () => {
    answerWith({ answer: "n/a", answerable: false, citations: [] });
    renderBox();

    await askQuestion();

    expect(await screen.findByText(/couldn't find that/)).toBeInTheDocument();
    expect(screen.queryByText("n/a")).not.toBeInTheDocument();
    expectBrowseLinks();
  });

  it.each([
    [429, /Try again tomorrow/],
    [503, /isn't available right now/],
    [404, /isn't available right now/],
    [500, /Something went wrong/],
  ])("falls back to browse links on a %i response", async (status, message) => {
    postMock.mockRejectedValue(axiosHttpError(status));
    renderBox();

    await askQuestion();

    expect(await screen.findByText(message)).toBeInTheDocument();
    expectBrowseLinks();
  });
});
