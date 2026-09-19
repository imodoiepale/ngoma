import { redirect } from "next/navigation";

// The old address. Workspaces live at /w/<workspace> now.
export default async function LegacyClientPage({ params }) {
  const { client } = await params;
  redirect(`/w/${client}`);
}
