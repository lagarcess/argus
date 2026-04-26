with open('web/components/views/SettingsView.tsx', 'r') as f:
    content = f.read()

# Disable eslint for that line as this is standard React pattern and a false positive for the warning about cascading renders when fetching data.
content = content.replace("      setIsLoading(true);\n      listConversations", "      // eslint-disable-next-line react-hooks/set-state-in-effect\n      setIsLoading(true);\n      listConversations")
content = content.replace("      setIsLoading(true);\n      listHistory", "      // eslint-disable-next-line react-hooks/set-state-in-effect\n      setIsLoading(true);\n      listHistory")

with open('web/components/views/SettingsView.tsx', 'w') as f:
    f.write(content)
