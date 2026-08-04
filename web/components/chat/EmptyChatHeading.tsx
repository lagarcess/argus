import GuestEmptyStateIntro from "@/components/guest/GuestEmptyStateIntro";

export default function EmptyChatHeading({ isGuest }: { isGuest: boolean }) {
  return (
    <>
      <h1
        className={`font-display text-[40px] font-medium tracking-tight text-black dark:text-white ${
          isGuest ? "mb-3" : "mb-8"
        }`}
      >
        argus
      </h1>
      {isGuest ? <GuestEmptyStateIntro /> : null}
    </>
  );
}
