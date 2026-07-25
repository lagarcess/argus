import {
  assertExactLocalCandidate,
  assertZeroState,
  zeroStateSnapshot,
} from "./support/guest-qa";

export default async function guestExperienceGlobalSetup() {
  assertExactLocalCandidate();
  if (process.env.ARGUS_GUEST_QA_REQUIRE_ZERO_STATE === "true") {
    assertZeroState();
  } else {
    const state = zeroStateSnapshot();
    if (
      Object.values(state).some(
        (value) => !Number.isInteger(value) || value < 0,
      )
    ) {
      throw new Error("Guest QA database precondition helper returned bad data");
    }
  }
}
