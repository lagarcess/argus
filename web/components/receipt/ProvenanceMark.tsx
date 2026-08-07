type ProvenanceMarkProps = {
  label: string;
};

/**
 * The provenance mark, visible in the page and repeated in the preview image.
 * Screenshots travel further than links, so a cropped screenshot of Argus
 * numbers has to carry where the numbers came from.
 */
export default function ProvenanceMark({ label }: ProvenanceMarkProps) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium uppercase tracking-[0.08em] text-black/45 dark:text-white/45">
      <span
        aria-hidden="true"
        className="inline-block h-[7px] w-[7px] rounded-full bg-[#5ba897]"
      />
      {label}
    </span>
  );
}
