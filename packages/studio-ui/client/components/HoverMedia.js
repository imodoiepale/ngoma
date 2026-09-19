"use client";

// A still or a clip from a run. Clips play on hover or focus and pause otherwise, so a grid of
// results stays quiet until you look at one.
export function HoverMedia({ file, alt = "" }) {
  const src = `/api/media?path=${encodeURIComponent(String(file).replace(/\\/g, "/"))}`;
  if (/\.(mp4|webm|mov)$/i.test(file)) {
    const play = (e) => e.currentTarget.play().catch(() => {});
    const pause = (e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; };
    return <video src={src} muted loop playsInline preload="metadata" tabIndex={0} onMouseEnter={play} onFocus={play} onMouseLeave={pause} onBlur={pause} aria-label={alt || "Result clip"} />;
  }
  return <img src={src} alt={alt} loading="lazy" />;
}
