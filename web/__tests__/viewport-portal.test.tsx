import { expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import { withViewportPortal } from "../components/ui/withViewportPortal";

// SSR must not mount the surface (and its focus/history hooks) inline. The
// motion-on browser matrix checks the actual exports, placement and input.
test("viewport overlays defer their whole surface until the client mount", () => {
  let mounted = false;
  const Overlay = withViewportPortal(function Surface() {
    mounted = true;
    return <div role="dialog">Content</div>;
  });
  expect(renderToStaticMarkup(<Overlay />)).toBe("");
  expect(mounted).toBe(false);
});
