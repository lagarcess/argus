import { describe, expect, test } from "bun:test";
import { readReturnPath } from "../lib/auth-return-path";
import { authLoginPathFromSearch } from "../lib/landing-intent";

describe("sign-in return path", () => {
  test("a signed-out Business receipt link returns to that receipt", () => {
    const login = authLoginPathFromSearch("?receipt=rcpt-123&utm_source=whatsapp", "/biz");
    const search = login.slice(login.indexOf("?"));
    expect(readReturnPath(search)).toBe("/biz?receipt=rcpt-123");
  });

  test("Business views and conversations survive; other query keys do not", () => {
    expect(readReturnPath("?return_to=%2Fbiz%3Fview%3Dinbox%26evil%3D1")).toBe("/biz?view=inbox");
    expect(readReturnPath("?return_to=%2Fbiz%3Fconversation%3Dabc-9")).toBe("/biz?conversation=abc-9");
  });

  test("unlisted paths and other origins are refused", () => {
    expect(readReturnPath("?return_to=%2F%2Fevil.example%2Fbiz")).toBeUndefined();
    expect(readReturnPath("?return_to=https%3A%2F%2Fevil.example%2Fbiz")).toBeUndefined();
    expect(readReturnPath("?return_to=%2Faccount%2Fsecurity")).toBeUndefined();
    expect(readReturnPath("?return_to=%2Fbiz%3Freceipt%3D%253Cscript%253E")).toBe("/biz");
  });

  test("chat sign-in keeps its existing shape", () => {
    expect(authLoginPathFromSearch("", "/chat")).toBe("/?from_path=%2Fchat&auth=login");
  });
});
