const API_BASE = window.STUDIO_API_BASE || 'http://127.0.0.1:8000';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const payload = await response.json();
      throw new Error(payload.detail || JSON.stringify(payload) || `HTTP ${response.status}`);
    }
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export const studioApi = {
  listInfluencers() {
    return request('/api/v1/influencers');
  },

  getInfluencer(influencerId) {
    return request(`/api/v1/influencers/${encodeURIComponent(influencerId)}`);
  },

  updateInfluencer(influencerId, payload) {
    return request(`/api/v1/influencers/${encodeURIComponent(influencerId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  runPipeline(payload) {
    return request('/api/v1/pipeline/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  listPipelineRuns(influencerId) {
    const search = influencerId ? `?influencer_id=${encodeURIComponent(influencerId)}` : '';
    return request(`/api/v1/pipeline/runs${search}`);
  },

  getPipelineRun(influencerId, runId) {
    return request(`/api/v1/pipeline/runs/${encodeURIComponent(influencerId)}/${encodeURIComponent(runId)}`);
  },

  createGeneratedImage(payload) {
    return request('/api/v1/generated-images/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  generatePictureIdeas(payload) {
    return request('/api/v1/picture-ideas/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

export { API_BASE };
