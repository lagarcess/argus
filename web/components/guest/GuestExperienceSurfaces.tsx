"use client";

import GuestConversionModal from "@/components/guest/GuestConversionModal";
import GuestNewConversationDialog from "@/components/guest/GuestNewConversationDialog";
import type { GuestExperience } from "@/components/guest/useGuestExperience";
import { ShareReceiptPanel } from "@/components/chat/ShareReceiptAction";
import { evidenceReceiptSharingEnabled } from "@/lib/private-alpha-flags";

export default function GuestExperienceSurfaces({
  experience,
}: {
  experience: GuestExperience;
}) {
  const { conversion, newConversation, receiptSharing } = experience;
  return (
    <>
      {evidenceReceiptSharingEnabled && receiptSharing.target && <ShareReceiptPanel key={receiptSharing.target.conversationId} {...receiptSharing.target} onClose={receiptSharing.close} />}
      {conversion.isOpen && (
        <GuestConversionModal
          isOpen
          reason={conversion.reason}
          initialMode={conversion.initialMode}
          resetAt={conversion.resetAt}
          resetKind={conversion.resetKind}
          locale={conversion.locale}
          publicAccountAccessEnabled={conversion.publicAccountAccessEnabled}
          onClose={conversion.close}
          onAuthenticate={conversion.authenticate}
        />
      )}
      <GuestNewConversationDialog
        isOpen={newConversation.isOpen}
        isReplacing={newConversation.isReplacing}
        publicAccountAccessEnabled={conversion.publicAccountAccessEnabled}
        onCancel={newConversation.close}
        onStartOver={() => void newConversation.startOver()}
        onConvert={newConversation.convert}
      />
    </>
  );
}
