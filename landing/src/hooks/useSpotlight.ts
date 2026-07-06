import { useEffect, useRef } from "react";

const LERP_FACTOR = 0.09;

function lerp(from: number, to: number, t: number): number {
  return from + (to - from) * t;
}

/**
 * Drives the cursor-following spotlight reveal.
 *
 * Writes `--spot-x` / `--spot-y` directly onto the returned element's style
 * every animation frame (never through React state), smoothing the raw
 * pointer position with lerp so the reveal trails the cursor instead of
 * snapping to it. Before the first pointer move — and on touch devices that
 * never fire one — the spotlight drifts on its own slow path so the scene
 * still reads as alive. `prefers-reduced-motion` disables both the drift and
 * the tracking loop and simply fixes the spotlight in place.
 */
export function useSpotlight() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    let target = { x: 0, y: 0 };
    let current = { x: 0, y: 0 };
    let hasPointer = false;
    let frame = 0;
    const idleStart = performance.now();

    const setCenter = () => {
      const rect = node.getBoundingClientRect();
      const center = { x: rect.width * 0.5, y: rect.height * 0.42 };
      target = center;
      if (!hasPointer) current = center;
      node.style.setProperty("--spot-x", `${current.x}px`);
      node.style.setProperty("--spot-y", `${current.y}px`);
    };
    setCenter();

    if (prefersReducedMotion) {
      return;
    }

    const handlePointerMove = (event: PointerEvent) => {
      const rect = node.getBoundingClientRect();
      target = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      hasPointer = true;
    };

    const tick = (time: number) => {
      if (!hasPointer) {
        const rect = node.getBoundingClientRect();
        const elapsed = (time - idleStart) / 1000;
        target = {
          x: rect.width * 0.5 + Math.sin(elapsed * 0.25) * rect.width * 0.16,
          y: rect.height * 0.42 + Math.cos(elapsed * 0.2) * rect.height * 0.1,
        };
      }
      current.x = lerp(current.x, target.x, LERP_FACTOR);
      current.y = lerp(current.y, target.y, LERP_FACTOR);
      node.style.setProperty("--spot-x", `${current.x}px`);
      node.style.setProperty("--spot-y", `${current.y}px`);
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("resize", setCenter);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("resize", setCenter);
    };
  }, []);

  return ref;
}
