import { loadCatalog } from "../../../lib/studio";

export async function GET() {
  return Response.json(await loadCatalog());
}
