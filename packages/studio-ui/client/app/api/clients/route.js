import { TEMPLATES, listClients, listWorkflows } from "../../../lib/studio";

export async function GET() {
  return Response.json({ clients: await listClients(), templates: await listWorkflows(TEMPLATES) });
}
