import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, type Mock } from "vitest";
import { AiIntegrationsSection } from "./AiIntegrationsSection";
import * as aiSettingsApi from "@/api/aiSettingsApi";
import * as authContext from "@/context/AuthContext";

vi.mock("@/api/aiSettingsApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/aiSettingsApi")>();
  return {
    ...actual,
    getAiSettings: vi.fn(),
    createAiKey: vi.fn(),
  };
});

vi.mock("@/context/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/context/AuthContext")>();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

const getAiSettingsMock = aiSettingsApi.getAiSettings as unknown as Mock;
const createAiKeyMock = aiSettingsApi.createAiKey as unknown as Mock;
const useAuthMock = authContext.useAuth as unknown as Mock;

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AiIntegrationsSection />
    </QueryClientProvider>,
  );
}

async function openAddKeyModalOnOllama() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add key" }));
  await user.click(screen.getByRole("button", { name: "Ollama (Local)" }));
  return user;
}

function submitButton() {
  return screen.getAllByRole("button", { name: "Add key" })[1];
}

describe("AiIntegrationsSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ isSuperuser: false });
    createAiKeyMock.mockResolvedValue({
      configs: [],
      platform_fallback_enabled: false,
      approved_endpoints: [],
    });
  });

  it("offers the approved endpoints as a picker instead of a free-text URL", async () => {
    getAiSettingsMock.mockResolvedValue({
      configs: [],
      platform_fallback_enabled: false,
      approved_endpoints: [
        { origin: "http://ollama:11434", label: "Local Ollama" },
        {
          origin: "http://host.docker.internal:11434",
          label: "http://host.docker.internal:11434",
        },
      ],
    });
    renderSection();

    await openAddKeyModalOnOllama();

    expect(screen.queryByPlaceholderText("http://localhost:11434")).not.toBeInTheDocument();
    expect(screen.getByText("Local Ollama", { selector: "option" })).toBeInTheDocument();
    expect(
      screen.getByText("http://host.docker.internal:11434", { selector: "option" }),
    ).toBeInTheDocument();
  });

  it("preselects the only approved endpoint and submits its origin as base_url", async () => {
    getAiSettingsMock.mockResolvedValue({
      configs: [],
      platform_fallback_enabled: false,
      approved_endpoints: [{ origin: "http://ollama:11434", label: "Local Ollama" }],
    });
    renderSection();
    const user = await openAddKeyModalOnOllama();

    await user.click(submitButton());

    await waitFor(() =>
      expect(createAiKeyMock).toHaveBeenCalledWith(
        expect.objectContaining({ base_url: "http://ollama:11434" }),
      ),
    );
  });

  it("shows a message and disables Save when no endpoints are approved", async () => {
    getAiSettingsMock.mockResolvedValue({
      configs: [],
      platform_fallback_enabled: false,
      approved_endpoints: [],
    });
    renderSection();

    await openAddKeyModalOnOllama();

    expect(
      screen.getByText("No approved endpoints are configured. Contact your operator."),
    ).toBeInTheDocument();
    expect(submitButton()).toBeDisabled();
  });
});
