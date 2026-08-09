type ProvenanceMarkProps = {
  label: string;
};

/**
 * The provenance mark, visible in the page and repeated in the preview image.
 * Screenshots travel further than links, so a cropped screenshot of Argus numbers
 * has to carry where the numbers came from. Set as a lockup rather than a caption
 * for the same reason: it has to survive being cropped and rescaled.
 */
export default function ProvenanceMark({ label }: ProvenanceMarkProps) {
  return (
    <span className="font-display inline-flex shrink-0 items-center gap-2 whitespace-nowrap text-[12px] font-medium tracking-[0.02em] text-white/70">
      <span
        aria-hidden="true"
        className="inline-block h-[6px] w-[6px] rounded-full bg-[#5ba897]"
      />
      {label}
    </span>
  );
}
