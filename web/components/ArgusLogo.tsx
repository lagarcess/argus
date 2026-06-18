import React from 'react';

export function ArgusLogo({
  className = "w-6 h-6",
  ...props
}: React.SVGProps<SVGSVGElement> & { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 473 447"
      fill="currentColor"
      {...props}
    >
      <g data-logo="argus-angular-a-mark" data-source="vtracer-t120-polygon">
        <path
          d="M0,0 L34,0 L52,36 L63,59 L88,109 L99,132 L123,180 L131,196 L145,225 L160,255 L171,278 L212,360 L218,373 L218,375 L184,375 L176,359 L139,285 L128,262 L106,218 L95,195 L81,167 L72,148 L64,132 L43,90 L32,67 L17,37 L9,53 L-2,75 L-13,98 L-32,136 L-43,159 L-63,200 L-82,239 L-91,258 L-99,274 L-129,334 L-140,357 L-149,375 L-183,375 L-182,370 L-141,288 L-130,265 L-113,231 L-102,208 L-84,172 L-73,149 L-48,98 L-37,76 L-26,53 L-14,29 L-3,6 Z"
          transform="translate(219,36)"
        />
        <path
          d="M0,0 L4,5 L28,53 L38,72 L63,123 L74,146 L73,148 L-38,149 L-54,181 L-65,204 L-82,238 L-93,261 L-95,265 L-129,265 L-126,256 L-57,118 L-56,117 L26,117 L-16,33 L-15,28 L-1,1 Z"
          transform="translate(235,146)"
        />
        <path
          d="M0,0 L33,0 L43,19 L53,38 L64,61 L72,77 L75,83 L75,85 L41,85 L33,69 L1,5 Z"
          transform="translate(292,326)"
        />
      </g>
    </svg>
  );
}
