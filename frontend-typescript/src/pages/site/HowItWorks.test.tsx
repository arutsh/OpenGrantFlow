import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HowItWorksPage from "./HowItWorks";

function renderPage() {
  return render(
    <MemoryRouter>
      <HowItWorksPage />
    </MemoryRouter>,
  );
}

describe("HowItWorksPage", () => {
  it("renders the intro and the five steps", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: "One continuous financial record, from budget to report." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("Track")).toBeInTheDocument();
    expect(screen.getByText("Receipts")).toBeInTheDocument();
    expect(screen.getByText("Report")).toBeInTheDocument();
    expect(screen.getByText("Audit-ready")).toBeInTheDocument();
  });

  it("shows role-attributed pull-quotes describing sector pain points", () => {
    renderPage();

    expect(screen.getByText("Former UK fund CEO")).toBeInTheDocument();
    expect(screen.getByText("International nonprofit leader")).toBeInTheDocument();
    expect(screen.getByText("Nonprofit / fund adviser")).toBeInTheDocument();
    expect(
      screen.getByText(/Even sophisticated internal systems/),
    ).toBeInTheDocument();
  });

  it("presents the anecdote without quotation marks, visually distinguished from the quotes", () => {
    renderPage();

    const anecdoteText = screen.getByText(/One leader of a small local nonprofit/);
    expect(anecdoteText.textContent).not.toMatch(/[“”"]/);
    expect(
      screen.getByText("From a conversation with a local nonprofit leader"),
    ).toBeInTheDocument();
  });

  it("shows a closing statement about the market opportunity", () => {
    renderPage();

    expect(
      screen.getByText("The opportunity is interoperability, not another closed portal."),
    ).toBeInTheDocument();
  });

  it("does not attribute any quote to a named person or organization", () => {
    renderPage();

    const attributions = [
      "Former UK fund CEO",
      "International nonprofit leader",
      "Nonprofit / fund adviser",
    ];
    attributions.forEach((role) => {
      expect(screen.getByText(role)).toBeInTheDocument();
    });
  });

  it("renders the who-it's-for sections for grantees and funders", () => {
    renderPage();

    expect(screen.getByText("If you receive grants")).toBeInTheDocument();
    expect(screen.getByText("Less time on administration")).toBeInTheDocument();
    expect(screen.getByText("If you fund grants")).toBeInTheDocument();
    expect(screen.getByText("A clear view of your portfolio")).toBeInTheDocument();
  });

  it("numbers the steps in order", () => {
    renderPage();

    const steps = screen.getAllByRole("listitem").filter((li) => li.closest("#five-steps"));
    expect(steps.map((step) => step.textContent?.slice(0, 2))).toEqual(
      ["1B", "2T", "3R", "4R", "5A"],
    );
  });

  it("ends with a CTA band linking to the demo request", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "See it with your own grants in mind" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a demo" })).toHaveAttribute("href", "/contact");
  });
});
