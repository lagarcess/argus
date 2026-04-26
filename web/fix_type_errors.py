with open('web/components/views/SettingsView.tsx', 'r') as f:
    content = f.read()

content = content.replace("await patchConversation(item.id, { deleted_at: null } as any);", "await patchConversation(item.id, { deleted_at: null } as unknown as Parameters<typeof patchConversation>[1]);")
content = content.replace("await patchStrategy(item.id, { deleted_at: null } as any);", "await patchStrategy(item.id, { deleted_at: null } as unknown as Parameters<typeof patchStrategy>[1]);")
content = content.replace("onFeedback?: (type: \"bug\" | \"feature\" | \"general\", context: Record<string, any>) => void;", "onFeedback?: (type: \"bug\" | \"feature\" | \"general\", context: Record<string, unknown>) => void;")

with open('web/components/views/SettingsView.tsx', 'w') as f:
    f.write(content)
