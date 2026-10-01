# Simplified recording controls

2026-10-01. Follows `78a0fec12`. Founder approved reducing locked recording to a small lock/timer, waveform, Cancelar and Detener, and fixing the lock hint shifting during up/left drags.

## Change

Removed the locked-state pill and explanatory paragraph. Gesture instructions are visible only while held; locking acknowledges “Puedes soltar,” then release reveals actions. Kept a shorter preview microphone notice. Status alternatives occupy one shared measured slot, guidance/actions another, and the longest hold hint determines reserved text height. Hidden alternatives neither receive taps nor enter the accessibility tree. No gesture semantics or provider behavior changed.

The lock/timer is exposed as one accessible status. The centering check uses its combined bounds with a two-point tolerance for SF Symbol accessibility bounds; the earlier text-only assertion used one point. An initial check selected the symbol child, then the combined symbol/text bounds differed from the layout center by 1.25 points. Actual captures confirm centered composition, rather than a renewed layout offset.

## Visual evidence

[Hold](hold.png) and [left cancellation](cancel.png) retain identical lock-hint and waveform anchors. [Before lock](before-lock.png) and [lock acknowledgment](lock-acknowledgment.png) retain the status position. These are actual native gesture-video frames from 01:43, at 26.4, 29.1, 16.0 and 17.0 seconds. Subsequent changes only group the timer's accessibility element and adjust the geometry assertion; their render/gesture evidence remains valid. All four images were inspected.

Final native run `Test-ArgusFoundation-2026.10.01_01-46-35--0500.xcresult`: two journeys passed, zero failures, terminal TEST SUCCEEDED. Spanish/English centering, both lock targets, review preservation, Cancelar/Detener and largest accessibility text passed. The held composer/waveform, left cancellation and typed-draft journey passed at 01:43; its behavior was unchanged by the final accessibility-only correction. [Locked Spanish](locked-es.png) and [largest text](large-text.png) captures were visually inspected. Signed physical iPhone build succeeded; Cuadrao Preview installed on the physical iPhone, receipt sequence 3216, and CoreDevice confirmed launch. Physical touch assessment remains with the founder. This remains an interaction preview: no microphone capture, transcription or provider session.
