import { redirect } from "next/navigation";

// The old address. Workflows live at /w/<workspace>/f/<id> now.
export default async function LegacyWorkflowPage({ params }) {
  const { client, id } = await params;
  redirect(`/w/${client}/f/${id}`);
}
