import { Shell } from "../../components/Shell";
import LibraryBrowser from "../../components/LibraryBrowser";

export const dynamic = "force-dynamic";

// The archive index: ComfyUI workflow files by group, and full-text search over transcripts
// and descriptions. Read through /api/library.
export default function Library() {
  return (
    <Shell current="/library" crumbs={[{ label: "Library" }]}>
      <section className="page-head">
        <p className="eyebrow">Library</p>
        <h1>The workflow archive.</h1>
        <p className="lede">Every ComfyUI graph the studio knows about, grouped by family, and the text indexed around them. A step in the catalogue points at one of these files; a file not yet in the catalogue is a candidate for a new step.</p>
      </section>
      <LibraryBrowser />
    </Shell>
  );
}
