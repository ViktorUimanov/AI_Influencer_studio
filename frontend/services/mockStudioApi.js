import { assets as baseAssets, influencers as baseInfluencers, runs as baseRuns, settings as baseSettings, trends as baseTrends } from "../data/mockData.js";

const STORAGE_KEY = "ai-influencer-ui-v2";
const runtimeMedia = new Map();

function delay(value) {
  return new Promise((resolve) => setTimeout(() => resolve(value), 100));
}

function clone(value) {
  return typeof structuredClone === "function"
    ? structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || `item-${Date.now()}`;
}

function formatSize(bytes) {
  if (!bytes) return "Unknown";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function sentence(value, fallback) {
  const text = String(value || "").trim();
  if (!text) return fallback;
  return text.length > 180 ? `${text.slice(0, 177)}...` : text;
}

function loadStore() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    return {
      influencerOverrides: parsed.influencerOverrides || {},
      assetOverrides: parsed.assetOverrides || {},
      runOverrides: parsed.runOverrides || {},
      customInfluencers: parsed.customInfluencers || [],
      customAssets: parsed.customAssets || [],
      customRuns: parsed.customRuns || [],
      customSettings: parsed.customSettings || {},
    };
  } catch {
    return {
      influencerOverrides: {},
      assetOverrides: {},
      runOverrides: {},
      customInfluencers: [],
      customAssets: [],
      customRuns: [],
      customSettings: {},
    };
  }
}

function saveStore(store) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

function mergeCollection(baseItems, overrides, customItems) {
  return [
    ...baseItems.map((item) => ({ ...clone(item), ...(overrides[item.id] || {}) })),
    ...clone(customItems),
  ];
}

function buildWorkspace(store = loadStore()) {
  const influencers = mergeCollection(baseInfluencers, store.influencerOverrides, store.customInfluencers);
  const assets = mergeCollection(baseAssets, store.assetOverrides, store.customAssets);
  const runs = mergeCollection(baseRuns, store.runOverrides, store.customRuns);
  const influencerMap = Object.fromEntries(influencers.map((item) => [item.id, item]));
  const trendMap = Object.fromEntries(baseTrends.map((item) => [item.id, clone(item)]));
  const assetMap = Object.fromEntries(assets.map((item) => [item.id, item]));

  function hydrateRun(run) {
    return {
      ...run,
      influencer: influencerMap[run.influencerId] || null,
      trend: trendMap[run.trendId] || null,
      inputAssets: (run.inputAssetIds || []).map((id) => assetMap[id]).filter(Boolean),
      outputAssets: (run.outputAssetIds || []).map((id) => assetMap[id]).filter(Boolean),
    };
  }

  return {
    influencers,
    trends: clone(baseTrends),
    runs,
    assets,
    hydratedRuns: runs.map(hydrateRun),
    settings: { ...baseSettings, ...store.customSettings },
    maps: { influencerMap, trendMap, assetMap },
  };
}

function ensureInfluencerOverride(store, influencerId, nextPatch) {
  const workspace = buildWorkspace(store);
  const influencer = workspace.maps.influencerMap[influencerId];
  if (!influencer) throw new Error(`Influencer ${influencerId} not found`);
  store.influencerOverrides[influencerId] = {
    ...(store.influencerOverrides[influencerId] || {}),
    ...nextPatch(influencer),
  };
}

function registerRuntimeMedia(assetId, url) {
  if (assetId && url) {
    runtimeMedia.set(assetId, url);
  }
}

function assetsForFiles(influencerId, files, description) {
  return (files || []).map((file, index) => {
    const assetId = `${influencerId}-${Date.now().toString(36)}-${index + 1}`;
    if (file.previewUrl) registerRuntimeMedia(assetId, file.previewUrl);
    return {
      id: assetId,
      name: file.name,
      influencerId,
      kind: "reference",
      mediaType: file.mediaType,
      description: file.description || description,
      createdAt: new Date().toISOString(),
      duration: file.duration || "",
      fileSizeLabel: file.fileSizeLabel || formatSize(file.size),
      localOnly: true,
      path: "",
    };
  });
}

function upsertById(items, nextItem) {
  const index = items.findIndex((item) => item.id === nextItem.id);
  if (index >= 0) {
    items[index] = nextItem;
  } else {
    items.unshift(nextItem);
  }
}

function pipelineStageRows(detail, mockOutputCount) {
  const totalIngested = (detail.platforms || []).reduce((sum, platform) => sum + (platform.ingested_items || 0), 0);
  const totalAccepted = (detail.platforms || []).reduce((sum, platform) => sum + (platform.accepted || 0), 0);
  const totalRejected = (detail.platforms || []).reduce((sum, platform) => sum + (platform.rejected || 0), 0);
  const request = detail.request || {};
  const filterEnabled = request.filter?.enabled !== false;
  const vlmEnabled = request.vlm?.enabled !== false;

  return [
    {
      label: "Queued",
      status: "Completed",
      note: "Run submitted from the frontend and accepted by the backend pipeline.",
    },
    {
      label: "Fetching source",
      status: "Completed",
      note: `${totalIngested} source item${totalIngested === 1 ? "" : "s"} ingested across ${detail.platforms.length} platform${detail.platforms.length === 1 ? "" : "s"}.`,
    },
    {
      label: "Processing source",
      status: filterEnabled ? "Completed" : "Queued",
      note: filterEnabled
        ? `${totalAccepted} accepted and ${totalRejected} rejected after filtering and Gemini selection.`
        : "Filtering was disabled for this run.",
    },
    {
      label: "Generating output",
      status: mockOutputCount ? "Completed" : vlmEnabled ? "Completed" : "Queued",
      note: mockOutputCount
        ? `Mock Comfy output attached from ${mockOutputCount} selected asset${mockOutputCount === 1 ? "" : "s"}.`
        : "No mocked Comfy outputs were attached for this run.",
    },
    {
      label: "Packaging results",
      status: "Completed",
      note: "Run outputs and manifests are available in the shared workspace.",
    },
  ];
}

function importPipelineRunIntoStore(store, { summary, detail, influencer }) {
  const selectedAssets = [];
  const filteredAssets = [];
  for (const platform of detail.platforms || []) {
    for (const asset of platform.selected_assets || []) {
      selectedAssets.push({
        id: `asset-run-${summary.run_id}-selected-${asset.platform}-${asset.name}`,
        name: asset.name,
        influencerId: summary.influencer_id,
        kind: "source",
        mediaType: asset.media_type,
        description: `Selected ${asset.platform} parser asset from the real pipeline run.`,
        createdAt: asset.created_at || summary.started_at,
        duration: "",
        fileSizeLabel: formatSize(asset.size_bytes),
        localOnly: false,
        path: asset.path,
      });
    }
    for (const asset of platform.filtered_assets || []) {
      filteredAssets.push({
        id: `asset-run-${summary.run_id}-filtered-${asset.platform}-${asset.name}`,
        name: asset.name,
        influencerId: summary.influencer_id,
        kind: "source",
        mediaType: asset.media_type,
        description: `Filtered ${asset.platform} asset retained by the parser pipeline.`,
        createdAt: asset.created_at || summary.started_at,
        duration: "",
        fileSizeLabel: formatSize(asset.size_bytes),
        localOnly: false,
        path: asset.path,
      });
    }
  }

  const generatedImageAssets = (detail.generated_images || []).map((image, index) => ({
    id: `asset-run-${summary.run_id}-generated-${index + 1}`,
    name: image.file_name || `generated-${index + 1}.png`,
    influencerId: summary.influencer_id,
    kind: "output",
    mediaType: "image",
    description: "Generated image returned by the backend image stage.",
    createdAt: image.created_at || summary.started_at,
    duration: "",
    fileSizeLabel: "",
    localOnly: false,
    path: image.file_path || "",
  }));

  const mockComfyOutputs = selectedAssets.slice(0, 1).map((asset, index) => ({
    id: `asset-run-${summary.run_id}-mock-comfy-${index + 1}`,
    name: `mock-comfy-${index + 1}-${asset.name}`,
    influencerId: summary.influencer_id,
    kind: "output",
    mediaType: asset.mediaType,
    description: "Mock Comfy output using the first selected parser asset as a placeholder result.",
    createdAt: summary.started_at,
    duration: asset.duration || "",
    fileSizeLabel: asset.fileSizeLabel,
    localOnly: false,
    path: asset.path,
  }));

  const allAssets = [...selectedAssets, ...filteredAssets, ...mockComfyOutputs, ...generatedImageAssets];
  allAssets.forEach((asset) => upsertById(store.customAssets, asset));

  const stages = pipelineStageRows(detail, mockComfyOutputs.length + generatedImageAssets.length);
  const run = {
    id: `pipeline-${summary.influencer_id}-${summary.run_id}`,
    title: `${influencer?.name || summary.influencer_id} parser run`,
    type: "Video substitution",
    influencerId: summary.influencer_id,
    trendId: "",
    status: "Completed",
    progress: 100,
    createdAt: summary.started_at,
    outputCount: mockComfyOutputs.length + generatedImageAssets.length,
    stageText: stages[stages.length - 1].note,
    sourcePlatform: (summary.platforms || []).map((platform) => platform.platform).join(" + ") || "Manual",
    inputAssetIds: selectedAssets.length ? selectedAssets.map((asset) => asset.id) : filteredAssets.slice(0, 3).map((asset) => asset.id),
    outputAssetIds: [...mockComfyOutputs, ...generatedImageAssets].map((asset) => asset.id),
    stages,
    configSummary: {
      influencer: summary.influencer_id,
      source: (summary.platforms || []).map((platform) => `${platform.platform}:${platform.source}`).join(", "),
      limit: Object.values(summary.request?.platforms || {}).reduce((sum, platform) => sum + (platform.limit || 0), 0),
      mode: Object.values(summary.request?.platforms || {})
        .map((platform) => platform.selector?.mode)
        .filter(Boolean)
        .join(", ") || "auto",
      theme: summary.request?.vlm?.theme || influencer?.niche || "parser run",
    },
    pipelineRequest: summary.request || {},
    pipelineMeta: {
      runId: summary.run_id,
      baseDir: summary.base_dir,
      generatedImagesCount: summary.generated_images_count || generatedImageAssets.length,
      platformDetails: (detail.platforms || []).map((platform) => ({
        platform: platform.platform,
        source: platform.source,
        ingestedItems: platform.ingested_items,
        accepted: platform.accepted || 0,
        rejected: platform.rejected || 0,
        selectedAssetCount: (platform.selected_assets || []).length,
      })),
    },
  };

  upsertById(store.customRuns, run);

  if (influencer) {
    ensureInfluencerOverride(store, influencer.id, (current) => ({
      runIds: [run.id, ...(current.runIds || []).filter((id) => id !== run.id)],
      outputAssetIds: [
        ...[...mockComfyOutputs, ...generatedImageAssets].map((asset) => asset.id),
        ...(current.outputAssetIds || []).filter((id) => ![...mockComfyOutputs, ...generatedImageAssets].some((asset) => asset.id === id)),
      ],
      latestActivity: `Completed parser run ${summary.run_id} with ${(summary.platforms || []).length} platform${(summary.platforms || []).length === 1 ? "" : "s"}.`,
      updatedAt: new Date().toISOString(),
    }));
  }

  return run.id;
}

export function getAssetPreviewUrl(asset) {
  return runtimeMedia.get(asset?.id) || asset?.path || "";
}

export const mockStudioApi = {
  async getWorkspace() {
    return delay(buildWorkspace());
  },

  async listInfluencers() {
    return delay(buildWorkspace().influencers);
  },

  async getInfluencer(id) {
    const workspace = buildWorkspace();
    const influencer = workspace.maps.influencerMap[id];
    if (!influencer) throw new Error(`Influencer ${id} not found`);
    return delay({
      ...influencer,
      referenceMedia: workspace.assets.filter((asset) => influencer.referenceAssetIds.includes(asset.id)),
      outputs: workspace.assets.filter((asset) => influencer.outputAssetIds.includes(asset.id)),
      runs: workspace.hydratedRuns.filter((run) => run.influencerId === id),
    });
  },

  async updateInfluencer(id, payload) {
    const store = loadStore();
    ensureInfluencerOverride(store, id, (current) => ({
      ...payload,
      updatedAt: new Date().toISOString(),
      latestActivity: payload.latestActivity || current.latestActivity,
    }));
    saveStore(store);
    return this.getInfluencer(id);
  },

  async addReferenceAssets(id, files) {
    const store = loadStore();
    const createdAssets = assetsForFiles(id, files, "Uploaded from the influencer portfolio in mock mode.");
    store.customAssets.push(...createdAssets);
    ensureInfluencerOverride(store, id, (current) => ({
      referenceAssetIds: [...createdAssets.map((asset) => asset.id), ...(current.referenceAssetIds || [])],
      latestActivity: `Uploaded ${createdAssets.length} reference asset${createdAssets.length === 1 ? "" : "s"} in mock mode.`,
      updatedAt: new Date().toISOString(),
    }));
    saveStore(store);
    return this.getInfluencer(id);
  },

  async createInfluencer(payload) {
    const store = loadStore();
    const influencerId = `${slugify(payload.name)}-${Date.now().toString(36)}`;
    const referenceAssets = assetsForFiles(
      influencerId,
      payload.referenceFiles,
      "Uploaded during mock onboarding.",
    );
    const influencer = {
      id: influencerId,
      name: payload.name,
      status: "Draft",
      niche: payload.niche,
      summary: payload.summary,
      description: payload.description || payload.summary,
      avatar: "",
      heroMedia: "",
      tags: payload.tags || [],
      personaNotes: payload.personaNotes || "Persona guidance has not been finalized yet.",
      rejectionRules: payload.rejectionRules || "Reject clips with weak subject clarity or a poor persona fit.",
      referenceAssetIds: referenceAssets.map((asset) => asset.id),
      runIds: [],
      outputAssetIds: [],
      latestActivity: "Influencer created in mock mode. Portfolio review pending.",
      updatedAt: new Date().toISOString(),
    };

    store.customInfluencers.unshift(influencer);
    store.customAssets.push(...referenceAssets);
    saveStore(store);
    return this.getInfluencer(influencerId);
  },

  async listTrends() {
    return delay(buildWorkspace().trends);
  },

  async getTrend(id) {
    const trend = buildWorkspace().trends.find((item) => item.id === id);
    if (!trend) throw new Error(`Trend ${id} not found`);
    return delay(trend);
  },

  async listRuns() {
    return delay(buildWorkspace().hydratedRuns);
  },

  async getRun(id) {
    const run = buildWorkspace().hydratedRuns.find((item) => item.id === id);
    if (!run) throw new Error(`Run ${id} not found`);
    return delay(run);
  },

  async createRun(payload) {
    const store = loadStore();
    const workspace = buildWorkspace(store);
    const influencer = workspace.maps.influencerMap[payload.influencerId];
    if (!influencer) throw new Error(`Influencer ${payload.influencerId} not found`);

    const trend = payload.trendId ? workspace.trends.find((item) => item.id === payload.trendId) : null;
    const run = {
      id: `${slugify(payload.title || `${influencer.name} run`)}-${Date.now().toString(36)}`,
      title: payload.title || `${influencer.name} guided run`,
      type: payload.type || "Video substitution",
      influencerId: influencer.id,
      trendId: trend?.id || "",
      status: "Queued",
      progress: 0,
      createdAt: new Date().toISOString(),
      outputCount: 0,
      stageText: "Waiting for queue slot",
      sourcePlatform: trend?.platform || payload.sourcePlatform || "Manual source",
      inputAssetIds: workspace.assets
        .filter((asset) => asset.influencerId === influencer.id && asset.kind !== "output")
        .slice(0, 2)
        .map((asset) => asset.id),
      outputAssetIds: [],
      stages: [
        { label: "Queued", status: "Running", note: "Run created from the mock workspace." },
        { label: "Fetching source", status: "Queued", note: trend ? `Waiting on ${trend.platform} source fetch.` : "Waiting on source selection." },
        { label: "Processing source", status: "Queued", note: "" },
        { label: "Generating output", status: "Queued", note: "" },
        { label: "Packaging results", status: "Queued", note: "" },
      ],
      configSummary: {
        influencer: influencer.id,
        source: trend ? `${trend.platform.toLowerCase()} trend` : "manual",
        limit: payload.limit || 20,
        mode: payload.mode || "guided run",
        theme: payload.theme || influencer.niche,
      },
    };

    store.customRuns.unshift(run);
    ensureInfluencerOverride(store, influencer.id, (current) => ({
      runIds: [run.id, ...(current.runIds || [])],
      latestActivity: `Queued a new ${run.type.toLowerCase()} run from ${trend ? trend.title : "manual setup"}.`,
      updatedAt: new Date().toISOString(),
    }));
    saveStore(store);
    return this.getRun(run.id);
  },

  async importPipelineRun(payload) {
    const store = loadStore();
    const workspace = buildWorkspace(store);
    const influencer = workspace.maps.influencerMap[payload.summary.influencer_id] || null;
    const runId = importPipelineRunIntoStore(store, {
      summary: payload.summary,
      detail: payload.detail,
      influencer,
    });
    saveStore(store);
    return this.getRun(runId);
  },

  async duplicateRun(id) {
    const existing = await this.getRun(id);
    return this.createRun({
      influencerId: existing.influencerId,
      trendId: existing.trendId,
      title: `${existing.title} copy`,
      type: existing.type,
      sourcePlatform: existing.sourcePlatform,
      limit: existing.configSummary?.limit,
      mode: existing.configSummary?.mode,
      theme: existing.configSummary?.theme,
    });
  },

  async listAssets() {
    return delay(buildWorkspace().assets);
  },

  async getSettings() {
    return delay(buildWorkspace().settings);
  },

  async updateSettings(payload) {
    const store = loadStore();
    store.customSettings = { ...store.customSettings, ...payload };
    saveStore(store);
    return delay(buildWorkspace().settings);
  },

  async resetWorkspace() {
    window.localStorage.removeItem(STORAGE_KEY);
    runtimeMedia.clear();
    return delay(buildWorkspace());
  },
};
