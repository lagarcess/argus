import { describe, it, expect } from "bun:test";
import * as apiHooks from "../lib/api/@tanstack/react-query.gen";
import * as apiSdk from "../lib/api/sdk.gen";

describe("Frontend API Sanity Check", () => {
    it("should successfully import generated TanStack Query hooks", () => {
        expect(apiHooks).toBeDefined();
        // Check for presence of key hooks defined in openapi.yaml
        expect(apiHooks.getHealthOptions).toBeDefined();
        expect(apiHooks.getAuthSessionOptions).toBeDefined();
    });

    it("should successfully import generated SDK functions", () => {
        expect(apiSdk).toBeDefined();
        expect(apiSdk.getHealth).toBeDefined();
        expect(apiSdk.postBacktests).toBeDefined();
    });
});
