import os
import re


def check_doc_parity():
    """Simple script to check for cross-references between root and ./docs."""
    root_dir = os.getcwd()
    docs_dir = os.path.join(root_dir, "docs")

    root_files = ["README.md", "AGENTS.md", "DEPLOYMENT.md"]
    wiki_files = []
    for root, _, files in os.walk(docs_dir):
        for file in files:
            if file.endswith(".md"):
                wiki_files.append(os.path.relpath(os.path.join(root, file), root_dir))

    issues = []

    # Check for broken links in root files
    for r_file in root_files:
        path = os.path.join(root_dir, r_file)
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # Find all relative links like [label](docs/...) or [label](./docs/...)
            links = re.findall(r"\]\((docs/[^)]+)\)", content)
            links += re.findall(r"\]\(\./(docs/[^)]+)\)", content)

            for link in links:
                # Remove anchors
                clean_link = link.split("#")[0]
                if not os.path.exists(os.path.join(root_dir, clean_link)):
                    issues.append(f"🔴 Broken Link in {r_file}: {link}")

    # Check if root README mentions key wiki sections
    readme_path = os.path.join(root_dir, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "docs/architecture" not in content and "docs/operations" not in content:
                issues.append(
                    "🟡 Root README should link to Architecture and Operations wiki."
                )

    if issues:
        print("\n".join(issues))
        # sys.exit(1) # Uncomment to block CI/CD or /verify
    else:
        print("✅ Documentation parity check passed.")


if __name__ == "__main__":
    check_doc_parity()
