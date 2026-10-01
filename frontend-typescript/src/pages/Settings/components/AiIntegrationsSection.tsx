import { useEffect, useState } from "react";
import { AlertTriangle, Eye, EyeOff, Info, Plus, Server, Sparkle, Trash2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAiSettings,
  createAiKey,
  setDefaultAiKey,
  deleteAiKey,
  setPlatformFallback,
  ApprovedEndpoint,
  ProviderKeyConfig,
} from "@/api/aiSettingsApi";
import { useAuth } from "@/context/AuthContext";
import Modal from "@/components/ui/Modal";
import Button from "@/components/ui/Button";

// Mirrors the seeded ai_providers rows (migration 003).
const PROVIDERS: {
  name: string;
  display_name: string;
  requires_key: boolean;
  key_prefix?: string;
  icon: typeof Sparkle;
}[] = [
  {
    name: "anthropic",
    display_name: "Anthropic",
    requires_key: true,
    key_prefix: "sk-ant-",
    icon: Sparkle,
  },
  { name: "ollama", display_name: "Ollama (Local)", requires_key: false, icon: Server },
];

// Mirrors migration 016's ai_provider_models table — keyed by provider so a
// model never shows up as valid for a provider it doesn't belong to.
const MODELS_BY_PROVIDER: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
    { value: "claude-haiku-4-5", label: "Claude Haiku 4.5" },
    { value: "claude-opus-4-5", label: "Claude Opus 4.5" },
  ],
  ollama: [
    { value: "llama3.2", label: "Llama 3.2" },
    { value: "gemma4:12b", label: "Gemma 4 12B" },
    { value: "qwen3.6:27b", label: "Qwen 3.6 27B" },
    { value: "deepseek-coder:6.7b", label: "DeepSeek Coder 6.7B" },
  ],
};

const PROVIDER_HELP: Record<string, { description: string; link: string; linkLabel: string }> = {
  anthropic: {
    description:
      "Used for AI-powered budget creation. Your key is encrypted at rest and never exposed.",
    link: "https://console.anthropic.com/settings/keys",
    linkLabel: "Get an Anthropic API key",
  },
};

function providerMetaFor(name: string) {
  return PROVIDERS.find((p) => p.name === name) ?? PROVIDERS[0];
}

function modelLabelFor(providerName: string, modelValue: string | null) {
  if (!modelValue) return null;
  return MODELS_BY_PROVIDER[providerName]?.find((m) => m.value === modelValue)?.label ?? modelValue;
}

function AddKeyModal({
  isOpen,
  onClose,
  isFirstKey,
  approvedEndpoints,
}: {
  isOpen: boolean;
  onClose: () => void;
  isFirstKey: boolean;
  approvedEndpoints: ApprovedEndpoint[];
}) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState(PROVIDERS[0].name);
  const [model, setModel] = useState(MODELS_BY_PROVIDER[PROVIDERS[0].name][0].value);
  const [label, setLabel] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [selectedOrigin, setSelectedOrigin] = useState(approvedEndpoints[0]?.origin ?? "");
  const [makeDefault, setMakeDefault] = useState(isFirstKey);

  useEffect(() => {
    if (isOpen) {
      setMakeDefault(isFirstKey);
      setSelectedOrigin(approvedEndpoints[0]?.origin ?? "");
    }
  }, [isOpen, isFirstKey, approvedEndpoints]);

  const providerMeta = providerMetaFor(provider);
  const availableModels = MODELS_BY_PROVIDER[provider] ?? [];

  const selectProvider = (name: string) => {
    setProvider(name);
    setModel(MODELS_BY_PROVIDER[name]?.[0]?.value ?? "");
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createAiKey({
        provider,
        label: label.trim() || null,
        key: providerMeta.requires_key ? keyInput : null,
        model,
        base_url: providerMeta.requires_key ? null : selectedOrigin || null,
        is_default: makeDefault,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-settings"] });
      setLabel("");
      setKeyInput("");
      setSelectedOrigin(approvedEndpoints[0]?.origin ?? "");
      setMakeDefault(false);
      onClose();
    },
  });

  const canSave = providerMeta.requires_key
    ? keyInput.trim().length > 0
    : selectedOrigin.length > 0;
  const help = PROVIDER_HELP[provider];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add AI provider key">
      <p className="text-sm text-gray-500 -mt-2 mb-5">
        Save a new provider config for your organization to use.
      </p>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5">Provider</label>
          <div className="flex gap-2">
            {PROVIDERS.map((p) => {
              const Icon = p.icon;
              const active = p.name === provider;
              return (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => selectProvider(p.name)}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border ${
                    active
                      ? "border-blue-600 bg-blue-50 text-blue-700"
                      : "border-gray-200 bg-white text-gray-600"
                  }`}
                >
                  <Icon size={15} />
                  {p.display_name}
                </button>
              );
            })}
          </div>
        </div>

        {help && (
          <p className="text-sm text-gray-500 -mt-2">
            {help.description}{" "}
            <a href={help.link} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
              {help.linkLabel}
            </a>
          </p>
        )}

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5">Model</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {availableModels.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {providerMeta.requires_key ? (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">API Key</label>
            <div className="relative">
              <input
                type={showKey ? "text" : "password"}
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder={`${providerMeta.key_prefix ?? "sk-"}...`}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
        ) : (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Endpoint</label>
            {approvedEndpoints.length > 0 ? (
              <select
                value={selectedOrigin}
                onChange={(e) => setSelectedOrigin(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {approvedEndpoints.map((endpoint) => (
                  <option key={endpoint.origin} value={endpoint.origin}>
                    {endpoint.label}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-sm text-gray-500">
                No approved endpoints are configured. Contact your operator.
              </p>
            )}
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5">
            Label <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder='e.g. "Fast drafts" — helps tell configs apart'
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <label className="flex items-start gap-2.5 p-3 bg-gray-50 border border-gray-200 rounded-lg cursor-pointer">
          <input
            type="checkbox"
            checked={makeDefault}
            disabled={isFirstKey}
            onChange={(e) => setMakeDefault(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            <span className="block text-sm font-medium text-gray-900">Set as default</span>
            <span className="block text-xs text-gray-500 mt-0.5">
              {isFirstKey
                ? "Your organization's first key is always the default."
                : "Used automatically across the organization unless a task specifies otherwise."}
            </span>
          </span>
        </label>

        <div className="flex justify-end gap-2 mt-1">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => createMutation.mutate()} disabled={!canSave || createMutation.isPending}>
            {createMutation.isPending ? "Saving…" : "Add key"}
          </Button>
        </div>

        {createMutation.isError && (
          <p className="text-sm text-red-600">
            {(createMutation.error as { response?: { data?: { detail?: string } } })?.response?.data
              ?.detail ?? "Failed to save"}
          </p>
        )}
      </div>
    </Modal>
  );
}

function DeleteConfirmModal({
  config,
  otherConfigs,
  onClose,
}: {
  config: ProviderKeyConfig;
  otherConfigs: ProviderKeyConfig[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const isDefaultWithOthers = config.is_default && otherConfigs.length > 0;
  const [replacementId, setReplacementId] = useState(otherConfigs[0]?.id ?? "");

  const deleteMutation = useMutation({
    mutationFn: () =>
      deleteAiKey(
        config.id,
        isDefaultWithOthers && replacementId ? { new_default_id: replacementId } : undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-settings"] });
      onClose();
    },
  });

  const modelLabel = modelLabelFor(config.provider, config.model) ?? config.provider;

  return (
    <Modal isOpen onClose={onClose}>
      <div className="flex gap-3 mb-4">
        <span className="w-9 h-9 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center flex-shrink-0">
          <AlertTriangle size={18} />
        </span>
        <div>
          <h2 className="text-base font-semibold text-gray-900 mb-1">
            {isDefaultWithOthers ? "Remove default AI key?" : "Remove AI key?"}
          </h2>
          <p className="text-sm text-gray-500 leading-relaxed">
            {isDefaultWithOthers ? (
              <>
                <strong className="text-gray-700">{modelLabel}</strong> is your organization's
                current default. You can optionally pick another key to take its place.
              </>
            ) : (
              <>Remove {modelLabel}? This cannot be undone.</>
            )}
          </p>
        </div>
      </div>

      {isDefaultWithOthers && (
        <div className="mb-2">
          <label className="block text-xs font-medium text-gray-700 mb-1.5">
            New default <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <select
            value={replacementId}
            onChange={(e) => setReplacementId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">No default — leave unset</option>
            {otherConfigs.map((c) => {
              const otherProviderMeta = providerMetaFor(c.provider);
              return (
                <option key={c.id} value={c.id}>
                  {modelLabelFor(c.provider, c.model) ?? c.provider} — {otherProviderMeta.display_name}
                </option>
              );
            })}
          </select>
        </div>
      )}

      <div className="flex justify-end gap-2 mt-4">
        <Button variant="secondary" onClick={onClose} disabled={deleteMutation.isPending}>
          Cancel
        </Button>
        <Button variant="danger" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
          {deleteMutation.isPending ? "Removing…" : "Remove key"}
        </Button>
      </div>

      {deleteMutation.isError && (
        <p className="text-sm text-red-600 mt-3">
          {(deleteMutation.error as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? "Failed to remove"}
        </p>
      )}
    </Modal>
  );
}

function ConfigRow({
  config,
  onRequestDelete,
}: {
  config: ProviderKeyConfig;
  onRequestDelete: (config: ProviderKeyConfig) => void;
}) {
  const queryClient = useQueryClient();
  const providerMeta = providerMetaFor(config.provider);
  const Icon = providerMeta.icon;

  const setDefaultMutation = useMutation({
    mutationFn: () => setDefaultAiKey(config.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-settings"] }),
  });

  return (
    <div className="flex items-center gap-4 px-6 py-4 border-t border-gray-100 first:border-t-0">
      <span
        className={`w-[18px] h-[18px] rounded-full flex-shrink-0 flex items-center justify-center ${
          config.is_default ? "bg-blue-600" : "border-2 border-gray-300"
        }`}
      >
        {config.is_default && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
      </span>
      <span className="w-9 h-9 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center flex-shrink-0 text-gray-600">
        <Icon size={18} />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">
            {config.label || modelLabelFor(config.provider, config.model) || providerMeta.display_name}
          </span>
          <span className="text-[11px] font-medium text-gray-700 bg-gray-100 px-2 py-0.5 rounded-full">
            {providerMeta.display_name}
          </span>
        </div>
        <div className="text-xs text-gray-400 font-mono mt-0.5">
          {config.masked_key ?? config.base_url ?? "—"}
        </div>
      </div>
      {config.is_default ? (
        <span className="text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-1 rounded-full flex-shrink-0">
          Default
        </span>
      ) : (
        <button
          onClick={() => setDefaultMutation.mutate()}
          disabled={setDefaultMutation.isPending}
          className="text-xs font-medium text-gray-500 border border-gray-200 px-2.5 py-1 rounded-full flex-shrink-0 disabled:opacity-50"
        >
          Set as default
        </button>
      )}
      <button
        onClick={() => onRequestDelete(config)}
        className="p-1.5 text-gray-400 hover:text-red-600 rounded-md flex-shrink-0"
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}

function PlatformFallbackNote({ enabled, isSuperuser }: { enabled: boolean; isSuperuser: boolean }) {
  const queryClient = useQueryClient();
  const toggleMutation = useMutation({
    mutationFn: (next: boolean) => setPlatformFallback(next),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-settings"] }),
  });

  return (
    <div className="flex items-start gap-2.5 px-4 py-3.5 bg-gray-50 border border-gray-200 rounded-lg">
      <Info size={16} className="text-gray-400 flex-shrink-0 mt-0.5" />
      <p className="text-xs text-gray-500 leading-relaxed flex-1">
        {enabled
          ? "No default key? Requests fall back to GrantFlow's platform-funded model (Claude Haiku 4.5), within your organization's monthly usage limits."
          : "No keys configured? Contact your organization's superuser to enable GrantFlow's platform-funded fallback model."}
      </p>
      {isSuperuser && (
        <Button
          variant="outline"
          className="text-xs py-1 px-2.5 flex-shrink-0"
          disabled={toggleMutation.isPending}
          onClick={() => toggleMutation.mutate(!enabled)}
        >
          {enabled ? "Disable" : "Enable"}
        </Button>
      )}
    </div>
  );
}

// Backend-confirmed customer-scoped (see settings_routes.py's resolve_customer_id),
// not per-user — lives under Organization even though the UI predates that split.
export function AiIntegrationsSection() {
  const { isSuperuser } = useAuth();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [deletingConfig, setDeletingConfig] = useState<ProviderKeyConfig | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: getAiSettings,
  });

  return (
    <div className="flex flex-col gap-4">
      {isLoading && <p className="text-sm text-gray-400">Loading…</p>}

      {data && (
        <>
          <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-5">
              <div>
                <h2 className="text-base font-semibold text-gray-900 mb-1">AI provider keys</h2>
                <p className="text-[13px] text-gray-500 max-w-lg leading-relaxed">
                  Keys your organization can use for AI features. Add as many as you like — the
                  one marked Default is used automatically when a task doesn't specify a model.
                </p>
              </div>
              <Button onClick={() => setAddModalOpen(true)} className="flex-shrink-0">
                <span className="inline-flex items-center gap-1.5">
                  <Plus size={16} /> Add key
                </span>
              </Button>
            </div>

            {data.configs.map((c) => (
              <ConfigRow key={c.id} config={c} onRequestDelete={setDeletingConfig} />
            ))}
          </section>

          <PlatformFallbackNote enabled={data.platform_fallback_enabled} isSuperuser={isSuperuser} />
        </>
      )}

      <AddKeyModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        isFirstKey={(data?.configs.length ?? 0) === 0}
        approvedEndpoints={data?.approved_endpoints ?? []}
      />

      {data && deletingConfig && (
        <DeleteConfirmModal
          config={deletingConfig}
          otherConfigs={data.configs.filter((c) => c.id !== deletingConfig.id)}
          onClose={() => setDeletingConfig(null)}
        />
      )}
    </div>
  );
}
