"use client";

import GuestConversionModal from "@/components/guest/GuestConversionModal";
import GuestNewConversationDialog from "@/components/guest/GuestNewConversationDialog";
import type { GuestExperience } from "@/components/guest/useGuestExperience";

export default function GuestExperienceSurfaces({
  experience,
}: {
  experience: GuestExperience;
}) {
  const { conversion, newConversation } = experience;
  return (
    <>
      <GuestConversionModal
        isOpen={conversion.isOpen}
        reason={conversion.reason}
        publicAccountAccessEnabled={conversion.publicAccountAccessEnabled}
        onClose={conversion.close}
        onAuthenticate={conversion.authenticate}
      />
      <GuestNewConversationDialog
        isOpen={newConversation.isOpen}
        isReplacing={newConversation.isReplacing}
        onCancel={newConversation.close}
        onStartOver={() => void newConversation.startOver()}
        onSignIn={newConversation.signIn}
      />
    </>
  );
}
