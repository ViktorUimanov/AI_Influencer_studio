import { mockStudioApi } from "./mockStudioApi.js";
import { studioApi as liveStudioApi } from "./studioApi.js";

const mode = new URLSearchParams(window.location.search).get("api") === "live" ? "live" : "mock";

function summarizeDescription(text) {
  const value = String(text || "").trim();
  if (!value) return "No summary yet.";
  return value.length > 140 ? `${value.slice(0, 137)}...` : value;
}

function buildLiveInfluencerAssets(influencers) {
  return influencers
    .filter((influencer) => influencer.reference_image_path)
    .map((influencer) => ({
      id: `asset-reference-${influencer.influencer_id}`,
      name: influencer.reference_image_path.split("/").pop() || "reference",
      influencerId: influencer.influencer_id,
      kind: "reference",
      mediaType: "image",
      description: "Reference image stored in the backend workspace.",
      createdAt: influencer.updated_at,
      duration: "",
      fileSizeLabel: "",
      localOnly: false,
      path: influencer.reference_image_path,
    }));
}

function buildLiveInfluencers(influencers, assets, runs) {
  const outputByInfluencer = new Map();
  for (const asset of assets) {
    if (!outputByInfluencer.has(asset.influencerId)) outputByInfluencer.set(asset.influencerId, []);
    outputByInfluencer.get(asset.influencerId).push(asset.id);
  }

  return influencers.map((influencer) => {
    const influencerRuns = runs.filter((run) => run.influencerId === influencer.influencer_id);
    return {
      id: influencer.influencer_id,
      name: influencer.name,
      status: influencer.onboarding_complete ? "Active" : "Draft",
      niche: (influencer.hashtags || []).slice(0, 3).join(" · ") || "Configured influencer",
      summary: summarizeDescription(influencer.description),
      description: influencer.description || "",
      avatar: influencer.reference_image_path || "",
      heroMedia: influencer.reference_image_path || "",
      tags: influencer.hashtags || [],
      personaNotes: influencer.description || "",
      rejectionRules: influencer.video_suggestions_requirement || "",
      referenceAssetIds: influencer.reference_image_path ? [`asset-reference-${influencer.influencer_id}`] : [],
      runIds: influencerRuns.map((run) => run.id),
      outputAssetIds: outputByInfluencer.get(influencer.influencer_id) || [],
      latestActivity: influencer.onboarding_complete
        ? `Ready for parser runs. Updated ${new Date(influencer.updated_at).toLocaleString("en", { month: "short", day: "numeric" })}.`
        : "Onboarding is incomplete.",
      updatedAt: influencer.updated_at,
    };
  });
}

function mergeCollectionsById(...collections) {
  const map = new Map();
  for (const collection of collections) {
    for (const item of collection || []) {
      map.set(item.id, { ...(map.get(item.id) || {}), ...item });
    }
  }
  return Array.from(map.values());
}

async function getLiveWorkspace() {
  const [mockWorkspace, liveInfluencersRaw, liveRunSummaries] = await Promise.all([
    mockStudioApi.getWorkspace(),
    liveStudioApi.listInfluencers(),
    liveStudioApi.listPipelineRuns(),
  ]);

  const detailRecords = await Promise.all(
    liveRunSummaries.map((summary) => liveStudioApi.getPipelineRun(summary.influencer_id, summary.run_id))
  );
  const importedRuns = await Promise.all(
    detailRecords.map((detail, index) =>
      mockStudioApi.importPipelineRun({
        summary: liveRunSummaries[index],
        detail,
      })
    )
  );

  const hydratedRuns = await Promise.all(importedRuns.map((run) => mockStudioApi.getRun(run.id)));
  const refreshedWorkspace = await mockStudioApi.getWorkspace();

  const liveReferenceAssets = buildLiveInfluencerAssets(liveInfluencersRaw);
  const mergedAssets = mergeCollectionsById(refreshedWorkspace.assets, liveReferenceAssets);
  const mergedRuns = mergeCollectionsById(refreshedWorkspace.runs, hydratedRuns);
  const mergedHydratedRuns = mergeCollectionsById(refreshedWorkspace.hydratedRuns, hydratedRuns);
  const liveInfluencers = buildLiveInfluencers(liveInfluencersRaw, mergedAssets.filter((asset) => asset.kind === "output"), mergedHydratedRuns);
  const influencerMap = new Map(liveInfluencers.map((item) => [item.id, item]));
  const assetMap = new Map(mergedAssets.map((item) => [item.id, item]));
  const finalHydratedRuns = mergedHydratedRuns.map((run) => ({
    ...run,
    influencer: influencerMap.get(run.influencerId) || run.influencer || null,
    inputAssets: (run.inputAssetIds || []).map((id) => assetMap.get(id)).filter(Boolean),
    outputAssets: (run.outputAssetIds || []).map((id) => assetMap.get(id)).filter(Boolean),
  }));

  return {
    ...mockWorkspace,
    influencers: mergeCollectionsById(refreshedWorkspace.influencers, liveInfluencers),
    assets: mergedAssets,
    runs: mergedRuns,
    hydratedRuns: finalHydratedRuns,
    settings: refreshedWorkspace.settings,
  };
}

async function createLiveRun(payload) {
  const influencer = payload.influencer || {};
  const referenceImagePath = payload.referenceImagePath || influencer.referenceImagePath || influencer.avatar || "";
  if (!referenceImagePath) {
    throw new Error("Reference image is required before starting a live run.");
  }

  await updateLiveInfluencer(influencer.id || payload.pipelineRequest.influencer_id, {
    name: influencer.name || payload.pipelineRequest.influencer_id,
    description: influencer.description || influencer.summary || "",
    tags: influencer.tags || [],
    rejectionRules: influencer.rejectionRules || "Reject clips that do not fit the influencer.",
    referenceImagePath,
  });

  const response = await liveStudioApi.runPipeline(payload.pipelineRequest);
  const runId = response.base_dir.split("/").filter(Boolean).pop();
  if (!runId) {
    throw new Error("Backend pipeline run did not return a usable run id.");
  }
  const detail = await liveStudioApi.getPipelineRun(response.influencer_id, runId);
  return mockStudioApi.importPipelineRun({
    summary: {
      run_id: runId,
      influencer_id: response.influencer_id,
      started_at: response.started_at,
      base_dir: response.base_dir,
      status: "Completed",
      request: payload.pipelineRequest,
      platforms: response.platforms,
      generated_images_count: response.generated_images?.length || 0,
    },
    detail,
  });
}

async function getLiveInfluencer(id) {
  const [workspace, influencer] = await Promise.all([getLiveWorkspace(), liveStudioApi.getInfluencer(id)]);
  const matched = workspace.influencers.find((item) => item.id === influencer.influencer_id);
  if (matched) return matched;
  return {
    id: influencer.influencer_id,
    name: influencer.name,
    status: influencer.onboarding_complete ? "Active" : "Draft",
    niche: (influencer.hashtags || []).slice(0, 3).join(" · ") || "Configured influencer",
    summary: summarizeDescription(influencer.description),
    description: influencer.description || "",
    avatar: influencer.reference_image_path || "",
    heroMedia: influencer.reference_image_path || "",
    tags: influencer.hashtags || [],
    personaNotes: influencer.description || "",
    rejectionRules: influencer.video_suggestions_requirement || "",
    referenceAssetIds: influencer.reference_image_path ? [`asset-reference-${influencer.influencer_id}`] : [],
    runIds: [],
    outputAssetIds: [],
    latestActivity: "Loaded from backend.",
    updatedAt: influencer.updated_at,
  };
}

async function updateLiveInfluencer(id, payload) {
  const request = {
    name: payload.name,
    description: payload.description || payload.summary || "",
    hashtags: Array.isArray(payload.tags) ? payload.tags : String(payload.tags || "")
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    video_suggestions_requirement: payload.rejectionRules || "Reject clips that do not fit the influencer.",
    reference_image_path: payload.referenceImagePath || undefined,
  };
  await liveStudioApi.updateInfluencer(id, request);
  return getLiveInfluencer(id);
}

export const apiMode = mode;
export const appApi = mode === "live"
  ? {
      ...mockStudioApi,
      getWorkspace: getLiveWorkspace,
      listInfluencers: async () => (await getLiveWorkspace()).influencers,
      getInfluencer: getLiveInfluencer,
      updateInfluencer: updateLiveInfluencer,
      listRuns: async () => (await getLiveWorkspace()).hydratedRuns,
      getRun: async (id) => {
        const workspace = await getLiveWorkspace();
        const run = workspace.hydratedRuns.find((item) => item.id === id);
        if (!run) throw new Error(`Run ${id} not found`);
        return run;
      },
      createRun: createLiveRun,
    }
  : mockStudioApi;
