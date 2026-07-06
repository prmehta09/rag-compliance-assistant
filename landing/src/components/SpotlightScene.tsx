import type { CSSProperties } from "react";
import { useSpotlight } from "../hooks/useSpotlight";

const BASE_IMAGE = "/hero-base.webp";
const REVEAL_IMAGE = "/hero-reveal.webp";

// Solid center feathering out to transparent at the spotlight's outer radius.
const SPOT_MASK =
  "radial-gradient(circle var(--spot-radius) at var(--spot-x) var(--spot-y), " +
  "black 0%, black 55%, transparent 100%)";

/**
 * Full-bleed backdrop built from two registered photographs: a barren ember-lit
 * ridge (always visible) and the same ridge in bloom, shown only inside the
 * cursor-following spotlight (see useSpotlight) — evidence uncovered in place.
 *
 * The mask lives on an UNtransformed wrapper: applying it directly to the
 * Ken Burns layer would scale the mask's coordinate space along with the image
 * and the circle would drift off the cursor. Instead, both images sit in
 * identical `animate-ken-burns` wrappers (same animation, same timing, so they
 * stay pixel-registered) and the reveal layer's wrapper is clipped from outside.
 */
export function SpotlightScene() {
  const sceneRef = useSpotlight();

  return (
    <div
      ref={sceneRef}
      className="absolute inset-0 h-dvh overflow-hidden bg-void"
      style={
        {
          "--spot-radius": "clamp(220px, 30vw, 480px)",
          "--spot-x": "50%",
          "--spot-y": "42%",
        } as CSSProperties
      }
    >
      <div aria-hidden className="absolute inset-0 animate-ken-burns">
        <div
          className="h-full w-full bg-cover bg-center"
          style={{ backgroundImage: `url(${BASE_IMAGE})` }}
        />
      </div>

      <div
        aria-hidden
        className="absolute inset-0"
        style={{ maskImage: SPOT_MASK, WebkitMaskImage: SPOT_MASK }}
      >
        <div className="absolute inset-0 animate-ken-burns">
          <div
            className="h-full w-full bg-cover bg-center"
            style={{ backgroundImage: `url(${REVEAL_IMAGE})` }}
          />
        </div>
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-void/80 via-transparent to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-t from-void via-void/10 to-transparent"
      />
    </div>
  );
}
