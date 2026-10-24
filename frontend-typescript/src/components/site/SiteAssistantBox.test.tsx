import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { axiosHttpError, withQueryClient } from "@/test/queryClient";
import gatewayApi from "@/api/gatewayApi";
import type { SiteAssistantAnswer } from "@/api/siteAssistantApi";
import { assistantSuggestions } from "@/lib/assistantSuggestions";
import { SiteAssistantBox } from "./SiteAssistantBox";

vi.mock("@/api/gatewayApi", () => ({ default: { post: vi.fn() } }));

const postMock = vi.mocked(gatewayApi.post);
const FIELD = "Ask a question about Open Grant Flow";

function answerWith(data: SiteAssistantAnswer) {
  postMock.mockResolvedValue({ data });
}

function sentBody(call = 0) {
  return postMock.mock.calls[call][1];
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
  await user.type(screen.getByLabelText(FIELD), text);
  await user.click(screen.getByRole("button", { name: "Ask" }));
  return user;
}

function suggestionButtons() {
  const list = screen.getByRole("list", { name: "Suggested questions" });
  return within(list).getAllByRole("button").map((b) => b.textContent);
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

  it("titles the box as an h2, so the answer h3 doesn't skip a level", () => {
    renderBox();

    expect(
      screen.getByRole("heading", { level: 2, name: "Ask about Open Grant Flow" }),
    ).toBeInTheDocument();
  });

  it("offers the persona labels with Anyone selected", () => {
    renderBox();

    expect(screen.getByRole("button", { name: "Anyone" })).toHaveAttribute("aria-pressed", "true");
    for (const name of ["I receive grants", "I fund grants", "I'm technical"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("aria-pressed", "false");
    }
  });

  it("returns to Anyone when it is activated after a persona", async () => {
    renderBox();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "I fund grants" }));
    await user.click(screen.getByRole("button", { name: "Anyone" }));

    expect(screen.getByRole("button", { name: "Anyone" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "I fund grants" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(suggestionButtons()).toEqual(assistantSuggestions.default);
  });

  it("sends the selected persona with the question", async () => {
    answerWith({ answer: "No.", answerable: false, citations: [] });
    renderBox();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "I fund grants" }));
    expect(screen.getByRole("button", { name: "I fund grants" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.type(screen.getByLabelText(FIELD), "Can I see grantee reports?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(sentBody()).toEqual({ question: "Can I see grantee reports?", persona: "funder" });
  });

  it("clears the persona when the selected one is activated again", async () => {
    answerWith({ answer: "No.", answerable: false, citations: [] });
    renderBox();
    const user = userEvent.setup();
    const funder = screen.getByRole("button", { name: "I fund grants" });

    await user.click(funder);
    await user.click(funder);
    expect(funder).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Anyone" })).toHaveAttribute("aria-pressed", "true");
    await askQuestion();

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(sentBody()).toEqual({ question: "How do exports work?", persona: null });
  });

  it("shows the default suggestions, and the persona's set once one is selected", async () => {
    renderBox();

    expect(suggestionButtons()).toEqual(assistantSuggestions.default);
    await userEvent.setup().click(screen.getByRole("button", { name: "I'm technical" }));
    expect(suggestionButtons()).toEqual(assistantSuggestions.technical);
  });

  it("sends a suggested question's text with the selected persona", async () => {
    answerWith({ answer: "From the assistant.", answerable: true, citations: [] });
    renderBox();
    const user = userEvent.setup();
    const question = assistantSuggestions.grantee[0];

    await user.click(screen.getByRole("button", { name: "I receive grants" }));
    await user.click(screen.getByRole("button", { name: question }));

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(sentBody()).toEqual({ question, persona: "grantee" });
    expect(await screen.findByText("From the assistant.")).toBeInTheDocument();
    expect(screen.getByLabelText(FIELD)).toHaveValue(question);
    expect(screen.getByLabelText(FIELD)).toHaveFocus();
  });

  it("limits the single-line field to the configured maximum length", async () => {
    renderBox(10);
    const field = screen.getByLabelText(FIELD);

    expect(field.tagName).toBe("INPUT");
    expect(field).toHaveAttribute("maxLength", "10");
    await userEvent.setup().type(field, "this is far longer than ten");
    expect(field).toHaveValue("this is fa");
  });

  it("shows the character counter only near the limit", async () => {
    renderBox(10);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(FIELD), "1234567");
    expect(screen.queryByText("7/10")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(FIELD), "8");
    expect(screen.getByText("8/10")).toBeInTheDocument();
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

  it("shows the answer block in order, replacing the suggestions", async () => {
    answerWith({
      answer: "You can export budgets to Excel.",
      answerable: true,
      citations: [
        { content_id: "a", url: "/how-it-works#export", title: "How it works: Export" },
        { content_id: "b", url: "/guides/budgets#excel", title: "Budgets guide: Excel" },
      ],
    });
    renderBox();
    await userEvent.setup().click(screen.getByRole("button", { name: "I fund grants" }));

    await askQuestion();

    const heading = await screen.findByRole("heading", { name: "How do exports work?" });
    const block = heading.parentElement as HTMLElement;
    const order = [
      within(block).getByText("Answer for funders"),
      heading,
      within(block).getByText("You can export budgets to Excel."),
      within(block).getByText(/Answered from:/),
      within(block).getByRole("link", { name: "Request a demo" }),
      within(block).getByRole("button", { name: "Ask something else" }),
    ];
    order.slice(1).forEach((el, i) => {
      expect(order[i].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
    expect(screen.getByRole("link", { name: "How it works: Export" })).toHaveAttribute(
      "href",
      "/how-it-works#export",
    );
    expect(screen.getByRole("link", { name: "Budgets guide: Excel" })).toHaveAttribute(
      "href",
      "/guides/budgets#excel",
    );
    expect(screen.getByRole("link", { name: "Request a demo" })).toHaveAttribute(
      "href",
      "/contact",
    );
    expect(screen.queryByRole("list", { name: "Suggested questions" })).not.toBeInTheDocument();
  });

  it("uses a generic label when no persona was selected", async () => {
    answerWith({ answer: "Yes.", answerable: true, citations: [] });
    renderBox();

    await askQuestion();

    expect(await screen.findByText("Answer")).toBeInTheDocument();
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

  it("renders markup in the answer and the question heading as literal text", async () => {
    const markup = '<b>bold</b><img src="x" onerror="alert(1)">';
    answerWith({ answer: markup, answerable: true, citations: [] });
    const { container } = renderBox();

    await askQuestion("<i>why</i>?");

    expect(await screen.findByText(markup)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "<i>why</i>?" })).toBeInTheDocument();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("i")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("resets to an empty, focused field and the suggestions on Ask something else", async () => {
    answerWith({ answer: "Yes.", answerable: true, citations: [] });
    renderBox();

    const user = await askQuestion();
    await user.click(await screen.findByRole("button", { name: "Ask something else" }));

    expect(screen.queryByText("Yes.")).not.toBeInTheDocument();
    expect(screen.getByLabelText(FIELD)).toHaveValue("");
    expect(screen.getByLabelText(FIELD)).toHaveFocus();
    expect(suggestionButtons()).toEqual(assistantSuggestions.default);
  });

  it("falls back to browse links with the reset action for an unanswerable question", async () => {
    answerWith({ answer: "n/a", answerable: false, citations: [] });
    renderBox();

    const user = await askQuestion();

    expect(await screen.findByText(/couldn't find that/)).toBeInTheDocument();
    expect(screen.queryByText("n/a")).not.toBeInTheDocument();
    expectBrowseLinks();
    await user.click(screen.getByRole("button", { name: "Ask something else" }));
    expect(screen.queryByText(/couldn't find that/)).not.toBeInTheDocument();
    expect(suggestionButtons()).toEqual(assistantSuggestions.default);
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
    expect(screen.getByRole("button", { name: "Ask something else" })).toBeInTheDocument();
  });
});
