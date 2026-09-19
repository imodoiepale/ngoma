import Link from "next/link";
import { listClients } from "../lib/studio";

const NAV = [
  ["/", "Home"],
  ["/explore", "Explore"],
  ["/batches", "Batches"],
  ["/jobs", "Jobs"],
  ["/library", "Library"],
];

// The page frame for everything that is not the canvas: wordmark, navigation, the workspace
// switcher and the current workspace's accent. Server rendered.
export async function Shell({ workspace = null, crumbs = [], children, current = "" }) {
  const workspaces = await listClients();
  const style = workspace ? { "--accent": workspace.accent, "--accent-ink": workspace.accentInk || "#15120b" } : undefined;
  return (
    <div className="shell" style={style}>
      <header className="shell-head">
        <Link href="/" className="wordmark">Director</Link>
        <nav className="shell-nav" aria-label="Primary">
          {NAV.map(([href, label]) => (
            <Link key={href} href={href} aria-current={current === href ? "page" : undefined}>{label}</Link>
          ))}
        </nav>
        <div className="shell-spaces" aria-label="Workspaces">
          {workspaces.map((w) => (
            <Link key={w.id} href={`/w/${w.id}`} className={`space-chip${workspace?.id === w.id ? " is-on" : ""}`} style={{ "--accent": w.accent }}>
              <span className="client-swatch" aria-hidden />{w.name}
            </Link>
          ))}
        </div>
      </header>
      {crumbs.length > 0 && (
        <nav className="crumbs" aria-label="Breadcrumb">
          <Link href="/">Home</Link>
          {crumbs.map((c, i) => (
            <span key={i}><span className="sep" aria-hidden>/</span>{c.href ? <Link href={c.href}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}</span>
          ))}
        </nav>
      )}
      <main className="shell-main">{children}</main>
      <footer className="shell-foot">
        <span>Dry run by default. Queued is not success. Every figure states whether it is measured or assumed.</span>
      </footer>
    </div>
  );
}
