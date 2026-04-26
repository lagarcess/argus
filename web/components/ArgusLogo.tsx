import React from 'react';

export function ArgusLogo({
  className = "w-6 h-6",
  strokeWidth = 2,
  ...props
}: React.SVGProps<SVGSVGElement> & { className?: string, strokeWidth?: number }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {/* Outer Portal - The Sandbox / Gateway */}
      <path d="M5 21V11c0-3.87 3.13-7 7-7s7 3.13 7 7v10" />
      {/* Inner Portal - The Analytical Engine */}
      <path d="M9 21v-8c0-1.66 1.34-3 3-3s3 1.34 3 3v8" className="opacity-40" />
      {/* The Focal Point / The 'Eye' / The Idea */}
      <circle cx="12" cy="15" r="1.5" fill="currentColor" />
    </svg>
  );
}
