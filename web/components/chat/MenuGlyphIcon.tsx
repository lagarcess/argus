import type { SVGProps } from "react";

/**
 * The drawer glyph: two stacked bars with the lower one shorter.
 *
 * An even three-bar hamburger reads as a generic nav menu. The uneven pair is
 * the mark chat products settled on, and it is the `=` the spec asks for
 * without being a literal equals sign.
 */
export function MenuGlyphIcon({
  className = "h-5 w-5",
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="14" y2="15" />
    </svg>
  );
}

export default MenuGlyphIcon;
