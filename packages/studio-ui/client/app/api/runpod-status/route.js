export const dynamic = "force-dynamic";

// Cloudflare fronts the RunPod API and rejects requests without a conventional
// User-Agent with error 1010.
const UA = "director-studio/1.0 (+https://runpod.io)";
const REST = "https://rest.runpod.io/v1";

const VOLUME_ID = process.env.RUNPOD_VOLUME_ID || "";
const ENDPOINT_ID = process.env.RUNPOD_ENDPOINT_ID || "";

async function rest(path, token) {
  const response = await fetch(`${REST}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      "User-Agent": UA,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`GET ${path} -> HTTP ${response.status}`);
  }
  return response.json();
}

export async function GET() {
  // The token is read server-side only and never returned to the browser.
  const token = process.env.RUNPOD_API_KEY;
  if (!token) {
    return Response.json(
      {
        ok: false,
        configured: false,
        error:
          "RUNPOD_API_KEY is not set on the server. Copy .env.example to .env.local and set it.",
      },
      { status: 503 },
    );
  }

  try {
    const [pods, endpoints, volumes] = await Promise.all([
      rest("/pods", token).catch((error) => ({ error: String(error) })),
      rest("/endpoints", token).catch((error) => ({ error: String(error) })),
      rest("/networkvolumes", token).catch((error) => ({ error: String(error) })),
    ]);

    const asArray = (value) =>
      Array.isArray(value) ? value : Array.isArray(value?.data) ? value.data : [];

    // Serverless health is a different host from the control-plane REST API.
    let health = null;
    try {
      if (!ENDPOINT_ID) throw new Error("no studio endpoint configured");
      const response = await fetch(
        `https://api.runpod.ai/v2/${ENDPOINT_ID}/health`,
        {
          headers: { Authorization: `Bearer ${token}`, "User-Agent": UA },
          cache: "no-store",
        },
      );
      if (response.ok) health = await response.json();
    } catch {
      health = null;
    }

    const podRows = asArray(pods).map((pod) => ({
      id: pod.id,
      name: pod.name,
      status: pod.desiredStatus,
      costPerHr: pod.costPerHr,
      gpu: pod.machine?.gpuTypeId || pod.gpuTypeIds?.[0] || null,
      gpuCount: pod.gpuCount,
      publicIp: pod.publicIp || null,
      portMappings: pod.portMappings || null,
      volume: pod.networkVolumeId || null,
    }));

    const runningCost = podRows
      .filter((pod) => pod.status === "RUNNING")
      .reduce((total, pod) => total + (pod.costPerHr || 0), 0);

    return Response.json({
      ok: true,
      configured: true,
      fetchedAt: new Date().toISOString(),
      pods: podRows,
      runningPods: podRows.filter((pod) => pod.status === "RUNNING").length,
      runningCostPerHr: Number(runningCost.toFixed(3)),
      volumes: asArray(volumes).map((volume) => ({
        id: volume.id,
        name: volume.name,
        size: volume.size,
        dataCenterId: volume.dataCenterId,
        isStudioVolume: volume.id === VOLUME_ID,
      })),
      endpoints: asArray(endpoints).map((endpoint) => ({
        id: endpoint.id,
        name: endpoint.name,
        gpuTypeIds: endpoint.gpuTypeIds,
        workersMin: endpoint.workersMin,
        workersMax: endpoint.workersMax,
        workersStandby: endpoint.workersStandby,
        idleTimeout: endpoint.idleTimeout,
        networkVolumeId: endpoint.networkVolumeId,
      })),
      endpointHealth: health,
    });
  } catch (error) {
    return Response.json({ ok: false, error: String(error) }, { status: 500 });
  }
}
