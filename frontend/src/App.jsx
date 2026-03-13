import { useEffect, useRef, useState } from "react";
import { apiMode, appApi } from "../services/appApi.js";
import { getAssetPreviewUrl } from "../services/mockStudioApi.js";
import {
  formatDateTime,
  formatRelative,
  formatShortDate,
  initials,
  matchesQuery,
  resolveMediaPath,
  sortByDateDesc,
  statusTone,
} from "./lib/workspace.js";

const navItems = [
  { key: "runs", label: "Runs history", mono: "RN", hash: "/runs" },
  { key: "influencer", label: "Influencer", mono: "IF", hash: "/influencer" },
  { key: "settings", label: "Settings", mono: "ST", hash: "/settings" },
];

const emptyWorkspace = {
  influencers: [],
  trends: [],
  runs: [],
  hydratedRuns: [],
  assets: [],
  settings: {},
};

const settingsDefaults = {
  storageMode: "filesystem",
  defaultPlatforms: ["TikTok", "Instagram"],
  defaultRunType: "Video substitution",
  trendLookbackDays: 45,
  parallelRunLimit: 2,
  autoOpenLatestRun: true,
  preserveReferenceSeparation: true,
  notes: "",
};

function createRunDraft(influencer) {
  const tags = influencer?.tags || [];
  return {
    influencerId: influencer?.id || "",
    referenceImagePath: influencer?.avatar || "",
    hashtags: tags.join(", "),
    searchTerms: tags.slice(0, 3).join(", "),
    theme: influencer?.niche ? `${influencer.niche} channel` : "influencer channel",
    mode: "mixed",
    recentDays: 30,
    minViews: "",
    minLikes: "",
    requireTopicMatch: true,
    tiktokEnabled: true,
    tiktokSource: "tiktok_custom",
    tiktokLimit: 20,
    instagramEnabled: true,
    instagramSource: "apify",
    instagramLimit: 20,
    downloadEnabled: true,
    filterEnabled: true,
    geminiEnabled: true,
    probeSeconds: 8,
    workers: 4,
    topK: 15,
    maxVideos: 15,
    vlmModel: "gemini-3.1-flash-lite-preview",
  };
}

function parseRoute(hash) {
  const clean = hash.replace(/^#\/?/, "");
  if (clean.startsWith("run/")) return "runDetail";
  if (clean.startsWith("influencer")) return "influencer";
  if (clean.startsWith("settings")) return "settings";
  return "runs";
}

function parseRunId(hash) {
  const clean = hash.replace(/^#\/?/, "");
  if (!clean.startsWith("run/")) return "";
  return decodeURIComponent(clean.slice(4));
}

function navigate(hash) {
  window.location.hash = hash;
}

function classNames(...values) {
  return values.filter(Boolean).join(" ");
}

function mapFiles(fileList) {
  return Array.from(fileList || []).map((file) => ({
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
    size: file.size,
    fileSizeLabel: appApi.formatSize ? appApi.formatSize(file.size) : `${Math.round(file.size / 1024)} KB`,
    mediaType: file.type.startsWith("video/") ? "video" : "image",
    previewUrl: URL.createObjectURL(file),
  }));
}

function App() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  const [workspace, setWorkspace] = useState(emptyWorkspace);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedInfluencerId, setSelectedInfluencerId] = useState("");
  const [runFilters, setRunFilters] = useState({ status: "All", influencer: "All" });
  const [influencerForm, setInfluencerForm] = useState({
    name: "",
    niche: "",
    summary: "",
    description: "",
    tags: "",
    personaNotes: "",
    rejectionRules: "",
  });
  const [settingsForm, setSettingsForm] = useState(settingsDefaults);
  const [previewAsset, setPreviewAsset] = useState(null);
  const [notices, setNotices] = useState([]);
  const [runDraft, setRunDraft] = useState(() => createRunDraft(null));
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [pendingRun, setPendingRun] = useState(null);
  const [expandedRunIds, setExpandedRunIds] = useState([]);
  const [runComposerOpen, setRunComposerOpen] = useState(false);
  const uploadInputRef = useRef(null);

  async function loadWorkspace({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = appApi.getWorkspace
        ? await appApi.getWorkspace()
        : await Promise.all([
            appApi.listInfluencers(),
            appApi.listTrends(),
            appApi.listRuns(),
            appApi.listAssets(),
            appApi.getSettings(),
          ]).then(([influencers, trends, runs, assets, settings]) => ({
            influencers,
            trends,
            runs,
            hydratedRuns: runs,
            assets,
            settings,
          }));
      const nextWorkspace = {
        influencers: data.influencers || [],
        trends: data.trends || [],
        runs: data.runs || [],
        hydratedRuns: data.hydratedRuns || data.runs || [],
        assets: data.assets || [],
        settings: data.settings || {},
      };
      setWorkspace(nextWorkspace);
      setSettingsForm((current) => ({
        ...settingsDefaults,
        ...nextWorkspace.settings,
        defaultPlatforms: nextWorkspace.settings?.defaultPlatforms || current.defaultPlatforms || settingsDefaults.defaultPlatforms,
      }));

      if (!selectedInfluencerId && nextWorkspace.influencers[0]) {
        setSelectedInfluencerId(nextWorkspace.influencers[0].id);
      }
      if (!selectedRunId && nextWorkspace.hydratedRuns[0]) {
        setSelectedRunId(sortByDateDesc(nextWorkspace.hydratedRuns)[0].id);
      }
    } catch (loadError) {
      setError(loadError.message || "Failed to load the frontend workspace.");
    } finally {
      setLoading(false);
    }
  }

  function pushNotice(message) {
    const id = `${Date.now()}-${Math.random()}`;
    setNotices((current) => [...current, { id, message }]);
    window.setTimeout(() => {
      setNotices((current) => current.filter((notice) => notice.id !== id));
    }, 2600);
  }

  useEffect(() => {
    loadWorkspace();
  }, []);

  useEffect(() => {
    function onHashChange() {
      setRoute(parseRoute(window.location.hash));
      const routeRunId = parseRunId(window.location.hash);
      if (routeRunId) setSelectedRunId(routeRunId);
      setSidebarOpen(false);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const sortedRuns = sortByDateDesc(pendingRun ? [pendingRun, ...workspace.hydratedRuns] : workspace.hydratedRuns);
  const filteredRuns = sortedRuns.filter((run) => {
    if (runFilters.status !== "All" && run.status !== runFilters.status) return false;
    if (runFilters.influencer !== "All" && run.influencerId !== runFilters.influencer) return false;
    return matchesQuery(search, [run.title, run.id, run.influencer?.name, run.stageText, run.type]);
  });

  useEffect(() => {
    if (!filteredRuns.length) return;
    if (!filteredRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(filteredRuns[0].id);
    }
  }, [filteredRuns, selectedRunId]);

  const selectedRun = filteredRuns.find((run) => run.id === selectedRunId) || sortedRuns.find((run) => run.id === selectedRunId) || null;
  const selectedInfluencer = workspace.influencers.find((item) => item.id === selectedInfluencerId) || workspace.influencers[0] || null;
  const influencerAssets = workspace.assets.filter((asset) => asset.influencerId === selectedInfluencer?.id && asset.kind === "reference");
  const influencerOutputs = workspace.assets.filter((asset) => asset.influencerId === selectedInfluencer?.id && asset.kind === "output");
  const influencerRuns = sortedRuns.filter((run) => run.influencerId === selectedInfluencer?.id).slice(0, 4);
  const runInfluencer = workspace.influencers.find((item) => item.id === runDraft.influencerId) || null;
  const runReferenceAssets = workspace.assets.filter((asset) => asset.influencerId === runDraft.influencerId && asset.kind === "reference");

  useEffect(() => {
    if (!workspace.influencers.length) return;
    if (!workspace.influencers.some((item) => item.id === selectedInfluencerId)) {
      setSelectedInfluencerId(workspace.influencers[0].id);
    }
  }, [workspace.influencers, selectedInfluencerId]);

  useEffect(() => {
    if (!sortedRuns.length) return;
    if (!sortedRuns.some((item) => item.id === selectedRunId)) {
      setSelectedRunId(sortedRuns[0].id);
    }
  }, [sortedRuns, selectedRunId]);

  useEffect(() => {
    if (!selectedInfluencer) return;
    setInfluencerForm({
      name: selectedInfluencer.name,
      niche: selectedInfluencer.niche,
      summary: selectedInfluencer.summary,
      description: selectedInfluencer.description,
      tags: (selectedInfluencer.tags || []).join(", "),
      personaNotes: selectedInfluencer.personaNotes || "",
      rejectionRules: selectedInfluencer.rejectionRules || "",
    });
  }, [selectedInfluencer?.id]);

  useEffect(() => {
    setRunDraft((current) => {
      if (current.influencerId && current.influencerId !== selectedInfluencer?.id) {
        return current;
      }
      return createRunDraft(selectedInfluencer);
    });
  }, [selectedInfluencer?.id]);

  useEffect(() => {
    if (!runInfluencer) return;
    const preferredReference = runReferenceAssets[0]?.path || runInfluencer.avatar || "";
    setRunDraft((current) => {
      const shouldRefreshDefaults = current.influencerId !== runInfluencer.id;
      if (shouldRefreshDefaults) {
        return {
          ...createRunDraft(runInfluencer),
          influencerId: runInfluencer.id,
          referenceImagePath: preferredReference,
        };
      }
      if (!current.referenceImagePath) {
        return { ...current, referenceImagePath: preferredReference };
      }
      return current;
    });
  }, [runInfluencer?.id, runReferenceAssets.length]);

  async function handleSaveInfluencer(event) {
    event.preventDefault();
    if (!selectedInfluencer) return;
    try {
      await appApi.updateInfluencer(selectedInfluencer.id, {
        ...influencerForm,
        tags: influencerForm.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        latestActivity: "Updated influencer configuration from the simplified frontend.",
      });
      await loadWorkspace({ silent: true });
      pushNotice("Influencer updated.");
    } catch (submitError) {
      pushNotice(submitError.message || "Failed to update influencer.");
    }
  }

  async function handleUploadAssets(fileList) {
    if (!selectedInfluencer) return;
    const files = mapFiles(fileList);
    if (!files.length) return;
    try {
      await appApi.addReferenceAssets(selectedInfluencer.id, files);
      await loadWorkspace({ silent: true });
      pushNotice("Reference media uploaded in mock mode.");
    } catch (submitError) {
      pushNotice(submitError.message || "Failed to upload reference media.");
    }
  }

  async function handleSaveSettings(event) {
    event.preventDefault();
    try {
      await appApi.updateSettings(settingsForm);
      await loadWorkspace({ silent: true });
      pushNotice("Settings saved.");
    } catch (submitError) {
      pushNotice(submitError.message || "Failed to save settings.");
    }
  }

  async function handleResetWorkspace() {
    if (!window.confirm("Reset all mock changes in the frontend workspace?")) return;
    try {
      await appApi.resetWorkspace();
      setSearch("");
      setRunFilters({ status: "All", influencer: "All" });
      await loadWorkspace({ silent: true });
      pushNotice("Mock workspace reset.");
    } catch (submitError) {
      pushNotice(submitError.message || "Failed to reset workspace.");
    }
  }

  function buildPipelineRequest() {
    const hashtags = runDraft.hashtags
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const searchTerms = runDraft.searchTerms
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const selector = {
      mode: runDraft.mode,
      search_terms: searchTerms,
      hashtags,
      min_views: runDraft.minViews === "" ? null : Number(runDraft.minViews),
      min_likes: runDraft.minLikes === "" ? null : Number(runDraft.minLikes),
      published_within_days: Number(runDraft.recentDays) || null,
      require_topic_match: Boolean(runDraft.requireTopicMatch),
    };
    const platforms = {};
    if (runDraft.tiktokEnabled) {
      platforms.tiktok = {
        enabled: true,
        source: runDraft.tiktokSource,
        limit: Number(runDraft.tiktokLimit) || 20,
        selector,
      };
    }
    if (runDraft.instagramEnabled) {
      platforms.instagram = {
        enabled: true,
        source: runDraft.instagramSource,
        limit: Number(runDraft.instagramLimit) || 20,
        selector,
      };
    }

    return {
      influencer_id: runDraft.influencerId,
      platforms,
      download: {
        enabled: Boolean(runDraft.downloadEnabled),
        force: false,
      },
      filter: {
        enabled: Boolean(runDraft.filterEnabled),
        probe_seconds: Number(runDraft.probeSeconds) || 8,
        workers: Number(runDraft.workers) || 4,
        top_k: Number(runDraft.topK) || 15,
      },
      vlm: {
        enabled: Boolean(runDraft.geminiEnabled),
        model: runDraft.vlmModel,
        api_key_env: "GEMINI_API_KEY",
        timeout_sec: 300,
        mock: false,
        max_videos: Number(runDraft.maxVideos) || 15,
        theme: runDraft.theme || "influencer channel",
        sync_folders: true,
      },
    };
  }

  async function handleCreateRun(event) {
    event.preventDefault();
    if (!runDraft.influencerId) {
      pushNotice("Choose an influencer before starting a run.");
      return;
    }
    if (!runDraft.referenceImagePath) {
      pushNotice("Choose a reference image before starting a run.");
      return;
    }
    if (!runDraft.tiktokEnabled && !runDraft.instagramEnabled) {
      pushNotice("Enable at least one platform.");
      return;
    }

    const pipelineRequest = buildPipelineRequest();
    const influencer = workspace.influencers.find((item) => item.id === runDraft.influencerId) || null;
    const pendingId = `pending-${Date.now()}`;
    setRunSubmitting(true);
    setPendingRun({
      id: pendingId,
      title: `${influencer?.name || runDraft.influencerId} parser run`,
      type: "Video substitution",
      influencerId: runDraft.influencerId,
      influencer,
      status: "Running",
      progress: 14,
      createdAt: new Date().toISOString(),
      outputAssets: [],
      stageText: "Running the real parsing pipeline",
      sourcePlatform: Object.keys(pipelineRequest.platforms).join(" + "),
      stages: [
        { label: "Queued", status: "Completed", note: "Run created from the frontend composer." },
        { label: "Fetching source", status: "Running", note: "Waiting for the backend parser to return results." },
      ],
    });

    try {
      const run = await appApi.createRun({
        pipelineRequest,
        influencer: influencer || {
          id: runDraft.influencerId,
          name: runDraft.influencerId,
          description: "",
          tags: [],
          rejectionRules: "",
        },
        referenceImagePath: runDraft.referenceImagePath,
      });
      setPendingRun(null);
      await loadWorkspace({ silent: true });
      setSelectedRunId(run.id);
      setRunComposerOpen(false);
      navigate(`/run/${run.id}`);
      pushNotice("Parser run completed.");
    } catch (submitError) {
      setPendingRun(null);
      pushNotice(submitError.message || "Failed to start the parser run.");
    } finally {
      setRunSubmitting(false);
    }
  }

  const page = loading
    ? <LoadingPage />
    : error
      ? <ErrorPage message={error} onRetry={() => loadWorkspace()} />
      : route === "runs"
        ? (
          <RunsPage
            runs={filteredRuns}
            search={search}
            filters={runFilters}
            influencers={workspace.influencers}
            expandedRunIds={expandedRunIds}
            onSearch={setSearch}
            onFilterChange={setRunFilters}
            onToggleExpanded={(runId) => setExpandedRunIds((current) => current.includes(runId) ? current.filter((id) => id !== runId) : [...current, runId])}
            onOpenRunPage={(runId) => {
              setSelectedRunId(runId);
              navigate(`/run/${runId}`);
            }}
            onOpenRunComposer={() => setRunComposerOpen(true)}
          />
        )
        : route === "runDetail"
          ? (
            <RunPage
              run={selectedRun}
              onBack={() => navigate("/runs")}
              onPreview={setPreviewAsset}
            />
          )
        : route === "influencer"
          ? (
            <InfluencerPage
              influencer={selectedInfluencer}
              influencers={workspace.influencers}
              form={influencerForm}
              assets={influencerAssets}
              outputs={influencerOutputs}
              runs={influencerRuns}
              search={search}
              onSearch={setSearch}
              onSelectInfluencer={setSelectedInfluencerId}
              onChangeForm={setInfluencerForm}
              onSubmit={handleSaveInfluencer}
              onUpload={() => uploadInputRef.current?.click()}
              onPreview={setPreviewAsset}
            />
          )
          : (
            <SettingsPage
              form={settingsForm}
              search={search}
              onSearch={setSearch}
              onChangeForm={setSettingsForm}
              onSubmit={handleSaveSettings}
              onResetWorkspace={handleResetWorkspace}
            />
          );

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} route={route} onNavigate={navigate} onClose={() => setSidebarOpen(false)} />

      <div className="workspace-shell">
        <Topbar
          route={route}
          search={search}
          onSearch={setSearch}
          onMenu={() => setSidebarOpen((current) => !current)}
        />
        <main className="workspace-main">{page}</main>
      </div>

      {route === "influencer" && (
        <input
          ref={uploadInputRef}
          type="file"
          hidden
          accept="image/*,video/*"
          multiple
          onChange={(event) => {
            handleUploadAssets(event.target.files);
            event.target.value = "";
          }}
        />
      )}

      {previewAsset ? <PreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} /> : null}
      {runComposerOpen ? (
        <RunComposerModal
          runDraft={runDraft}
          runSubmitting={runSubmitting}
          runReferenceAssets={runReferenceAssets}
          runInfluencer={runInfluencer}
          influencers={workspace.influencers}
          onClose={() => setRunComposerOpen(false)}
          onChangeRunDraft={setRunDraft}
          onCreateRun={handleCreateRun}
        />
      ) : null}
      <NoticeStack notices={notices} />
    </div>
  );
}

function Sidebar({ open, route, onNavigate, onClose }) {
  const activeRoute = route === "runDetail" ? "runs" : route;
  return (
    <>
      <aside className={classNames("sidebar", open && "sidebar-open")}>
        <div className="sidebar-brand">
          <div className="sidebar-mark">ST</div>
          <div>
            <div className="sidebar-title">Studio</div>
            <div className="sidebar-subtitle">Simplified frontend</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={classNames("nav-item", activeRoute === item.key && "nav-item-active")}
              onClick={() => onNavigate(item.hash)}
            >
              <span className="nav-item-mono">{item.mono}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="mode-chip">Mock mode</div>
          <div className="sidebar-note">Three-page workspace focused on runs, influencer editing, and system settings.</div>
        </div>
      </aside>
      {open ? <button className="sidebar-backdrop" aria-label="Close sidebar" onClick={onClose} /> : null}
    </>
  );
}

function Topbar({ route, search, onSearch, onMenu }) {
  const placeholders = {
    runs: "Search runs by title, status, or influencer",
    runDetail: "Search the selected run page",
    influencer: "Search within the selected influencer view",
    settings: "Search settings notes",
  };

  return (
    <header className="workspace-topbar">
      <button className="topbar-menu" onClick={onMenu}>Menu</button>
      <label className="search-shell">
        <span className="search-label">Search</span>
        <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder={placeholders[route]} />
      </label>
      <div className="topbar-meta">
        <span className="meta-chip">API: {apiMode}</span>
        <span className="meta-chip">Frontend only</span>
      </div>
    </header>
  );
}

function RunsPage({
  runs,
  search,
  filters,
  influencers,
  expandedRunIds,
  onSearch,
  onFilterChange,
  onToggleExpanded,
  onOpenRunPage,
  onOpenRunComposer,
}) {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="History"
        title="Runs history"
        subtitle="A compact run log with quick status, pipeline context, and click-through detail."
        actions={<button className="btn btn-primary" onClick={onOpenRunComposer}>Start parser run</button>}
      />

      <section className="surface-card">
        <div className="section-header-inline">
          <div>
            <h2>Runs list</h2>
            <p>Filter the history, expand inline metadata, or open a dedicated run page.</p>
          </div>
        </div>

        <div className="filter-row">
          <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search runs" />
          <select value={filters.status} onChange={(event) => onFilterChange((current) => ({ ...current, status: event.target.value }))}>
            <option>All</option>
            <option>Queued</option>
            <option>Running</option>
            <option>Completed</option>
            <option>Failed</option>
          </select>
          <select value={filters.influencer} onChange={(event) => onFilterChange((current) => ({ ...current, influencer: event.target.value }))}>
            <option value="All">All influencers</option>
            {influencers.map((influencer) => (
              <option key={influencer.id} value={influencer.id}>{influencer.name}</option>
            ))}
          </select>
        </div>

        {runs.length ? (
          <div className="run-list">
            {runs.map((run) => {
              const expanded = expandedRunIds.includes(run.id);
              return (
                <div key={run.id} className="run-history-card">
                  <div className="run-row">
                    <div className="run-main">
                      <strong>{run.title}</strong>
                      <span>{run.influencer?.name || "Unknown"} · {run.type}</span>
                    </div>
                    <div className="run-progress-cell">
                      <ProgressBar value={run.progress} compact />
                      <small>{run.stageText}</small>
                    </div>
                    <div className="run-meta">
                      <StatusPill status={run.status} />
                      <span>{formatRelative(run.createdAt)}</span>
                      <span>{run.outputAssets?.length || 0} outputs</span>
                    </div>
                    <div className="run-actions">
                      <button className="icon-button" onClick={() => onOpenRunPage(run.id)} aria-label="Open run page">→</button>
                    </div>
                  </div>
                  <div className="run-history-footer">
                    <button className="text-button" onClick={() => onToggleExpanded(run.id)}>
                      {expanded ? "Collapse metadata" : "Expand metadata"}
                    </button>
                  </div>
                  {expanded ? (
                    <div className="run-inline-meta">
                      <div className="run-inline-meta-grid">
                        <InlineMetaItem label="Created" value={formatDateTime(run.createdAt)} />
                        <InlineMetaItem label="Source" value={run.sourcePlatform} />
                        <InlineMetaItem label="Outputs" value={String(run.outputAssets?.length || 0)} />
                        <InlineMetaItem label="Progress" value={`${run.progress}%`} />
                      </div>
                      {run.configSummary ? (
                        <div className="run-inline-meta-grid">
                          <InlineMetaItem label="Source config" value={run.configSummary.source || "Unknown"} />
                          <InlineMetaItem label="Limit" value={String(run.configSummary.limit || 0)} />
                          <InlineMetaItem label="Mode" value={run.configSummary.mode || "auto"} />
                          <InlineMetaItem label="Theme" value={run.configSummary.theme || "influencer channel"} />
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState title="No runs match this filter" body="Clear the search or status filters to restore the run history." />
        )}
      </section>
    </div>
  );
}

function RunPage({ run, onBack, onPreview }) {
  return (
    <div className="page-stack run-page">
      <PageHeader
        eyebrow="Run"
        title={run?.title || "Run not found"}
        subtitle={run ? "Dedicated run page with pipeline state, inputs, and outputs." : "The selected run could not be loaded."}
        actions={<button className="btn btn-secondary" onClick={onBack}>Back to runs</button>}
      />
      <RunDetailPanel run={run} onPreview={onPreview} />
    </div>
  );
}

function RunComposerModal({
  runDraft,
  runSubmitting,
  runReferenceAssets,
  runInfluencer,
  influencers,
  onClose,
  onChangeRunDraft,
  onCreateRun,
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-shell run-composer-modal" onClick={(event) => event.stopPropagation()}>
        <div className="preview-toolbar">
          <div className="preview-meta">
            <strong>Start parser run</strong>
            <span>Customize the live API payload. Comfy output remains mocked.</span>
          </div>
          <div className="preview-actions">
            <button className="btn btn-secondary" onClick={onClose}>Close</button>
          </div>
        </div>
        <form className="surface-card run-composer" onSubmit={onCreateRun}>
          <div className="form-grid">
            <label>
              Influencer
              <select
                value={runDraft.influencerId}
                onChange={(event) => {
                  const nextId = event.target.value;
                  const nextInfluencer = influencers.find((item) => item.id === nextId) || null;
                  const nextReference = nextInfluencer?.avatar || "";
                  onChangeRunDraft(() => ({
                    ...createRunDraft(nextInfluencer),
                    influencerId: nextId,
                    referenceImagePath: nextReference,
                  }));
                }}
              >
                <option value="">Choose influencer</option>
                {influencers.map((influencer) => (
                  <option key={influencer.id} value={influencer.id}>{influencer.name}</option>
                ))}
              </select>
            </label>

            <label>
              Reference image
              <select
                value={runDraft.referenceImagePath}
                onChange={(event) => onChangeRunDraft((current) => ({ ...current, referenceImagePath: event.target.value }))}
              >
                <option value="">Choose reference image</option>
                {runReferenceAssets.map((asset) => (
                  <option key={asset.id} value={asset.path}>{asset.name}</option>
                ))}
                {!runReferenceAssets.length && runInfluencer?.avatar ? (
                  <option value={runInfluencer.avatar}>Primary influencer image</option>
                ) : null}
              </select>
            </label>

            <label>
              Theme
              <input value={runDraft.theme} onChange={(event) => onChangeRunDraft((current) => ({ ...current, theme: event.target.value }))} />
            </label>

            <label className="span-two">
              Hashtags
              <input value={runDraft.hashtags} onChange={(event) => onChangeRunDraft((current) => ({ ...current, hashtags: event.target.value }))} placeholder="altgirl, dance, choreography" />
            </label>

            <label className="span-two">
              Search terms
              <input value={runDraft.searchTerms} onChange={(event) => onChangeRunDraft((current) => ({ ...current, searchTerms: event.target.value }))} placeholder="alt girl dance, solo choreography" />
            </label>

            <label>
              Selector mode
              <select value={runDraft.mode} onChange={(event) => onChangeRunDraft((current) => ({ ...current, mode: event.target.value }))}>
                <option value="auto">auto</option>
                <option value="search">search</option>
                <option value="hashtag">hashtag</option>
                <option value="mixed">mixed</option>
              </select>
            </label>

            <label>
              Recent days
              <input type="number" min="1" value={runDraft.recentDays} onChange={(event) => onChangeRunDraft((current) => ({ ...current, recentDays: event.target.value }))} />
            </label>

            <label>
              Min views
              <input type="number" min="0" value={runDraft.minViews} onChange={(event) => onChangeRunDraft((current) => ({ ...current, minViews: event.target.value }))} placeholder="optional" />
            </label>

            <label>
              Min likes
              <input type="number" min="0" value={runDraft.minLikes} onChange={(event) => onChangeRunDraft((current) => ({ ...current, minLikes: event.target.value }))} placeholder="optional" />
            </label>

            <fieldset className="span-two inline-fieldset">
              <legend>Platforms</legend>
              <div className="platform-grid">
                <label className="platform-card">
                  <div className="platform-toggle">
                    <input type="checkbox" checked={runDraft.tiktokEnabled} onChange={(event) => onChangeRunDraft((current) => ({ ...current, tiktokEnabled: event.target.checked }))} />
                    <strong>TikTok</strong>
                  </div>
                  <select value={runDraft.tiktokSource} onChange={(event) => onChangeRunDraft((current) => ({ ...current, tiktokSource: event.target.value }))}>
                    <option value="tiktok_custom">tiktok_custom</option>
                    <option value="apify">apify</option>
                    <option value="seed">seed</option>
                  </select>
                  <input type="number" min="1" value={runDraft.tiktokLimit} onChange={(event) => onChangeRunDraft((current) => ({ ...current, tiktokLimit: event.target.value }))} />
                </label>

                <label className="platform-card">
                  <div className="platform-toggle">
                    <input type="checkbox" checked={runDraft.instagramEnabled} onChange={(event) => onChangeRunDraft((current) => ({ ...current, instagramEnabled: event.target.checked }))} />
                    <strong>Instagram</strong>
                  </div>
                  <select value={runDraft.instagramSource} onChange={(event) => onChangeRunDraft((current) => ({ ...current, instagramSource: event.target.value }))}>
                    <option value="apify">apify</option>
                    <option value="instagram_custom">instagram_custom</option>
                    <option value="seed">seed</option>
                  </select>
                  <input type="number" min="1" value={runDraft.instagramLimit} onChange={(event) => onChangeRunDraft((current) => ({ ...current, instagramLimit: event.target.value }))} />
                </label>
              </div>
            </fieldset>

            <fieldset className="span-two inline-fieldset">
              <legend>Pipeline stages</legend>
              <div className="checkbox-row">
                <label className="checkbox-chip">
                  <input type="checkbox" checked={runDraft.downloadEnabled} onChange={(event) => onChangeRunDraft((current) => ({ ...current, downloadEnabled: event.target.checked }))} />
                  Download
                </label>
                <label className="checkbox-chip">
                  <input type="checkbox" checked={runDraft.filterEnabled} onChange={(event) => onChangeRunDraft((current) => ({ ...current, filterEnabled: event.target.checked }))} />
                  Filter
                </label>
                <label className="checkbox-chip">
                  <input type="checkbox" checked={runDraft.geminiEnabled} onChange={(event) => onChangeRunDraft((current) => ({ ...current, geminiEnabled: event.target.checked }))} />
                  Gemini
                </label>
                <label className="checkbox-chip">
                  <input type="checkbox" checked={runDraft.requireTopicMatch} onChange={(event) => onChangeRunDraft((current) => ({ ...current, requireTopicMatch: event.target.checked }))} />
                  Require topic match
                </label>
              </div>
            </fieldset>

            <label>
              Probe seconds
              <input type="number" min="3" value={runDraft.probeSeconds} onChange={(event) => onChangeRunDraft((current) => ({ ...current, probeSeconds: event.target.value }))} />
            </label>

            <label>
              Workers
              <input type="number" min="1" value={runDraft.workers} onChange={(event) => onChangeRunDraft((current) => ({ ...current, workers: event.target.value }))} />
            </label>

            <label>
              Top K
              <input type="number" min="1" value={runDraft.topK} onChange={(event) => onChangeRunDraft((current) => ({ ...current, topK: event.target.value }))} />
            </label>

            <label>
              Max Gemini videos
              <input type="number" min="1" value={runDraft.maxVideos} onChange={(event) => onChangeRunDraft((current) => ({ ...current, maxVideos: event.target.value }))} />
            </label>

            <label className="span-two">
              Gemini model
              <input value={runDraft.vlmModel} onChange={(event) => onChangeRunDraft((current) => ({ ...current, vlmModel: event.target.value }))} />
            </label>
          </div>
          <div className="settings-footer">
            <button className="btn btn-primary" type="submit" disabled={runSubmitting}>
              {runSubmitting ? "Running..." : "Start run"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RunDetailPanel({ run, onPreview }) {
  if (!run) {
    return (
      <div className="surface-card">
        <EmptyState title="Select a run" body="Run details, inputs, stages, and outputs appear here." />
      </div>
    );
  }

  return (
    <div className="surface-card detail-panel">
      <div className="detail-panel-header">
        <div>
          <div className="page-eyebrow">Selected run</div>
          <h2>{run.title}</h2>
          <p>{run.influencer?.name || "Unknown"} · {run.type}</p>
        </div>
        <StatusPill status={run.status} />
      </div>

      <div className="info-grid">
        <InfoCard label="Created" value={formatDateTime(run.createdAt)} />
        <InfoCard label="Source" value={run.sourcePlatform} />
        <InfoCard label="Outputs" value={String(run.outputAssets?.length || 0)} />
        <InfoCard label="Progress" value={`${run.progress}%`} />
      </div>

      <div className="stack-list">
        <div>
          <div className="section-label">Pipeline</div>
          <ProgressBar value={run.progress} />
        </div>
        <div className="stage-list">
          {(run.stages || []).map((stage) => (
            <div key={stage.label} className={classNames("stage-item", `stage-${statusTone(stage.status)}`)}>
              <div className="stage-dot" />
              <div>
                <div className="stage-row">
                  <strong>{stage.label}</strong>
                  <StatusPill status={stage.status} />
                </div>
                <p>{stage.note || "Waiting for this stage."}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {run.configSummary ? (
        <div className="stack-list">
          <div className="section-label">Run config</div>
          <div className="info-grid">
            <InfoCard label="Source" value={run.configSummary.source || "Unknown"} />
            <InfoCard label="Limit" value={String(run.configSummary.limit || 0)} />
            <InfoCard label="Mode" value={run.configSummary.mode || "auto"} />
            <InfoCard label="Theme" value={run.configSummary.theme || "influencer channel"} />
          </div>
        </div>
      ) : null}

      <div className="stack-list">
        <div className="section-label">Input assets</div>
        <div className="asset-grid compact">
          {(run.inputAssets || []).map((asset) => (
            <MediaCard key={asset.id} asset={asset} onPreview={onPreview} />
          ))}
        </div>
      </div>

      <div className="stack-list">
        <div className="section-label">Outputs</div>
        {run.outputAssets?.length ? (
          <div className="asset-grid compact">
            {run.outputAssets.map((asset) => (
              <MediaCard key={asset.id} asset={asset} onPreview={onPreview} />
            ))}
          </div>
        ) : (
          <EmptyState
            title={run.status === "Completed" ? "No outputs attached" : "Outputs pending"}
            body={run.status === "Failed" ? "This failed run did not create outputs." : "Outputs will appear here after generation completes."}
          />
        )}
      </div>
    </div>
  );
}

function InfluencerPage({
  influencer,
  influencers,
  form,
  assets,
  outputs,
  runs,
  search,
  onSearch,
  onSelectInfluencer,
  onChangeForm,
  onSubmit,
  onUpload,
  onPreview,
}) {
  if (!influencer) {
    return <EmptyState title="No influencer available" body="Create or load an influencer in mock data to customize it here." />;
  }

  const visibleAssets = assets.filter((asset) => matchesQuery(search, [asset.name, asset.description, asset.mediaType]));
  const visibleOutputs = outputs.filter((asset) => matchesQuery(search, [asset.name, asset.description]));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Customization"
        title="Influencer"
        subtitle="Quickly adjust one influencer, upload references, and review recent results."
        actions={
          <select className="header-select" value={influencer.id} onChange={(event) => onSelectInfluencer(event.target.value)}>
            {influencers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        }
      />

      <section className="surface-card influencer-hero">
        <div className="hero-main">
          <Avatar influencer={influencer} />
          <div className="hero-copy">
            <div className="hero-title-row">
              <h2>{influencer.name}</h2>
              <StatusPill status={influencer.status} />
            </div>
            <p>{influencer.niche}</p>
            <small>{influencer.latestActivity}</small>
          </div>
        </div>
        <div className="hero-stats">
          <Metric label="References" value={influencer.referenceAssetIds?.length || 0} />
          <Metric label="Runs" value={influencer.runIds?.length || 0} />
          <Metric label="Outputs" value={influencer.outputAssetIds?.length || 0} />
        </div>
      </section>

      <section className="influencer-layout">
        <form className="surface-card form-stack" onSubmit={onSubmit}>
          <div className="section-header-inline">
            <div>
              <h2>Quick customization</h2>
              <p>Core persona fields, guardrails, and short operational notes.</p>
            </div>
            <button className="btn btn-primary" type="submit">Save influencer</button>
          </div>

          <div className="form-grid">
            <label>
              Name
              <input value={form.name} onChange={(event) => onChangeForm((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <label>
              Niche
              <input value={form.niche} onChange={(event) => onChangeForm((current) => ({ ...current, niche: event.target.value }))} />
            </label>
            <label className="span-two">
              Summary
              <textarea rows="3" value={form.summary} onChange={(event) => onChangeForm((current) => ({ ...current, summary: event.target.value }))} />
            </label>
            <label className="span-two">
              Description
              <textarea rows="4" value={form.description} onChange={(event) => onChangeForm((current) => ({ ...current, description: event.target.value }))} />
            </label>
            <label className="span-two">
              Tags
              <input value={form.tags} onChange={(event) => onChangeForm((current) => ({ ...current, tags: event.target.value }))} placeholder="wellness, editorial, healthy habits" />
            </label>
            <label className="span-two">
              Persona notes
              <textarea rows="4" value={form.personaNotes} onChange={(event) => onChangeForm((current) => ({ ...current, personaNotes: event.target.value }))} />
            </label>
            <label className="span-two">
              Rejection rules
              <textarea rows="4" value={form.rejectionRules} onChange={(event) => onChangeForm((current) => ({ ...current, rejectionRules: event.target.value }))} />
            </label>
          </div>
        </form>

        <div className="stack-column">
          <section className="surface-card">
            <div className="section-header-inline">
              <div>
                <h2>Reference media</h2>
                <p>Uploaded photos and videos for this influencer.</p>
              </div>
              <button className="btn btn-secondary" onClick={onUpload}>Upload files</button>
            </div>
            <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search reference media" />
            {visibleAssets.length ? (
              <div className="asset-grid">
                {visibleAssets.map((asset) => <MediaCard key={asset.id} asset={asset} onPreview={onPreview} />)}
              </div>
            ) : (
              <EmptyState title="No reference assets in view" body="Upload more files or broaden the current search." />
            )}
          </section>

          <section className="surface-card">
            <div className="section-header-inline">
              <div>
                <h2>Recent outputs</h2>
                <p>Generated media stays visually separate from references.</p>
              </div>
            </div>
            {visibleOutputs.length ? (
              <div className="asset-grid compact">
                {visibleOutputs.map((asset) => <MediaCard key={asset.id} asset={asset} onPreview={onPreview} />)}
              </div>
            ) : (
              <EmptyState title="No outputs yet" body="Outputs will appear here when runs complete." />
            )}
          </section>

          <section className="surface-card">
            <div className="section-header-inline">
              <div>
                <h2>Recent runs</h2>
                <p>Quick context for this influencer's latest activity.</p>
              </div>
            </div>
            {runs.length ? (
              <div className="run-list">
                {runs.map((run) => (
                  <div key={run.id} className="run-row">
                    <div className="run-main">
                      <strong>{run.title}</strong>
                      <span>{run.type}</span>
                    </div>
                    <div className="run-progress-cell">
                      <ProgressBar value={run.progress} compact />
                      <small>{run.stageText}</small>
                    </div>
                    <div className="run-meta">
                      <StatusPill status={run.status} />
                      <span>{formatShortDate(run.createdAt)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No runs yet" body="This influencer does not have run history yet." />
            )}
          </section>
        </div>
      </section>
    </div>
  );
}

function SettingsPage({ form, search, onSearch, onChangeForm, onSubmit, onResetWorkspace }) {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        subtitle="Workspace behavior, trend defaults, and run configuration. No visual theme controls."
      />

      <form className="surface-card form-stack" onSubmit={onSubmit}>
        <div className="section-header-inline">
          <div>
            <h2>Workspace configuration</h2>
            <p>These settings define behavior and defaults for the simplified frontend.</p>
          </div>
          <button className="btn btn-primary" type="submit">Save settings</button>
        </div>

        <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search notes or setting values" />

        <div className="settings-grid">
          <label>
            Storage mode
            <select value={form.storageMode} onChange={(event) => onChangeForm((current) => ({ ...current, storageMode: event.target.value }))}>
              <option>filesystem</option>
              <option>cloud</option>
            </select>
          </label>

          <label>
            Default run type
            <select value={form.defaultRunType} onChange={(event) => onChangeForm((current) => ({ ...current, defaultRunType: event.target.value }))}>
              <option>Video substitution</option>
              <option>Image generation</option>
              <option>Trend parse</option>
            </select>
          </label>

          <label>
            Trend lookback days
            <input type="number" min="1" value={form.trendLookbackDays} onChange={(event) => onChangeForm((current) => ({ ...current, trendLookbackDays: Number(event.target.value) }))} />
          </label>

          <label>
            Parallel run limit
            <input type="number" min="1" value={form.parallelRunLimit} onChange={(event) => onChangeForm((current) => ({ ...current, parallelRunLimit: Number(event.target.value) }))} />
          </label>

          <fieldset className="span-two">
            <legend>Default source platforms</legend>
            <div className="checkbox-row">
              {["TikTok", "Instagram", "X"].map((platform) => (
                <label key={platform} className="checkbox-chip">
                  <input
                    type="checkbox"
                    checked={form.defaultPlatforms.includes(platform)}
                    onChange={(event) =>
                      onChangeForm((current) => ({
                        ...current,
                        defaultPlatforms: event.target.checked
                          ? [...current.defaultPlatforms, platform]
                          : current.defaultPlatforms.filter((item) => item !== platform),
                      }))
                    }
                  />
                  {platform}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="toggle-row span-two">
            <input
              type="checkbox"
              checked={form.autoOpenLatestRun}
              onChange={(event) => onChangeForm((current) => ({ ...current, autoOpenLatestRun: event.target.checked }))}
            />
            <span>Auto focus the newest run after refresh</span>
          </label>

          <label className="toggle-row span-two">
            <input
              type="checkbox"
              checked={form.preserveReferenceSeparation}
              onChange={(event) => onChangeForm((current) => ({ ...current, preserveReferenceSeparation: event.target.checked }))}
            />
            <span>Keep reference media and outputs separated across surfaces</span>
          </label>

          <label className="span-two">
            Notes
            <textarea rows="5" value={form.notes} onChange={(event) => onChangeForm((current) => ({ ...current, notes: event.target.value }))} />
          </label>
        </div>

        <div className="settings-footer">
          <button type="button" className="btn btn-secondary" onClick={onResetWorkspace}>Reset mock workspace</button>
        </div>
      </form>
    </div>
  );
}

function PageHeader({ eyebrow, title, subtitle, actions }) {
  return (
    <section className="page-header">
      <div>
        <div className="page-eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="info-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InlineMetaItem({ label, value }) {
  return (
    <div className="inline-meta-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MediaCard({ asset, onPreview }) {
  const src = resolveMediaPath(getAssetPreviewUrl(asset));
  const isVideo = asset.mediaType === "video";

  return (
    <button className="media-card" onClick={() => onPreview({ ...asset, src })}>
      <div className="media-card-preview">
        {src ? (
          isVideo ? <video src={src} muted playsInline preload="metadata" /> : <img src={src} alt={asset.name} />
        ) : (
          <div className="media-card-fallback">{initials(asset.name)}</div>
        )}
        <span className="media-chip">{isVideo ? "Video" : "Image"}</span>
      </div>
      <div className="media-card-copy">
        <strong>{asset.name}</strong>
        <span>{asset.description}</span>
        <small>{asset.fileSizeLabel || asset.duration || formatShortDate(asset.createdAt)}</small>
      </div>
    </button>
  );
}

function PreviewModal({ asset, onClose }) {
  return (
    <div className="preview-backdrop" onClick={onClose}>
      <div className="preview-shell" onClick={(event) => event.stopPropagation()}>
        <div className="preview-toolbar">
          <div className="preview-meta">
            <strong>{asset.name}</strong>
            <span>{asset.mediaType === "video" ? "Video asset" : "Image asset"}</span>
          </div>
          <div className="preview-actions">
            <a className="btn btn-secondary" href={asset.src} target="_blank" rel="noreferrer">
              Open raw
            </a>
            <button className="btn btn-secondary" onClick={onClose}>Close</button>
          </div>
        </div>

        <div className="preview-stage">
          <div className="preview-media-frame">
            {asset.mediaType === "video" ? (
              <video src={asset.src} controls autoPlay playsInline />
            ) : (
              <img src={asset.src} alt={asset.name} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Avatar({ influencer }) {
  const src = resolveMediaPath(influencer.avatar || influencer.heroMedia);
  return src ? (
    <div className="avatar">
      {src.endsWith(".mp4") ? <video src={src} muted playsInline preload="metadata" /> : <img src={src} alt={influencer.name} />}
    </div>
  ) : (
    <div className="avatar avatar-fallback">{initials(influencer.name)}</div>
  );
}

function StatusPill({ status }) {
  return <span className={classNames("status-pill", `status-${statusTone(status)}`)}>{status}</span>;
}

function ProgressBar({ value, compact = false }) {
  return (
    <div className={classNames("progress-track", compact && "progress-track-compact")}>
      <div className="progress-fill" style={{ width: `${Math.max(4, value)}%` }} />
    </div>
  );
}

function EmptyState({ title, body }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">ST</div>
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function NoticeStack({ notices }) {
  return (
    <div className="notice-stack">
      {notices.map((notice) => <div key={notice.id} className="notice-card">{notice.message}</div>)}
    </div>
  );
}

function LoadingPage() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Loading" title="Preparing frontend" subtitle="Reading mock runs, influencers, assets, and settings." />
      <div className="surface-card loading-block">
        <div className="skeleton-row" />
        <div className="skeleton-row" />
        <div className="skeleton-row" />
      </div>
    </div>
  );
}

function ErrorPage({ message, onRetry }) {
  return (
    <div className="surface-card">
      <EmptyState title="Frontend failed to load" body={message} />
      <div className="settings-footer">
        <button className="btn btn-primary" onClick={onRetry}>Retry</button>
      </div>
    </div>
  );
}

export default App;
