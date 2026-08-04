import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import { History } from "lucide-react";

import SidebarNavButton from "../components/sidebar/SidebarNavButton";

describe("SidebarNavButton conversation activity aggregate", () => {
  test("overlays a working ring on the existing icon without expanding the target", () => {
    const html = renderToStaticMarkup(
      <SidebarNavButton
        icon={History}
        label="Recents"
        collapsed
        activityPresentation="working"
        onClick={() => undefined}
      />,
    );

    expect(html.match(/<button/g)).toHaveLength(1);
    expect(html).toContain("h-11 w-full");
    expect(html).toContain("lucide-history");
    expect(html).toContain('data-sidebar-activity-overlay="true"');
    expect(html).toContain('data-conversation-activity="working"');
  });

  test("shows one unread dot only when no loaded conversation is working", () => {
    const html = renderToStaticMarkup(
      <SidebarNavButton
        icon={History}
        label="Recents"
        activityPresentation="new_activity"
        onClick={() => undefined}
      />,
    );

    expect(html.match(/data-sidebar-activity-overlay=/g)).toHaveLength(1);
    expect(html).toContain('data-activity-dot="true"');
    expect(html).toContain("lucide-history");
  });
});
