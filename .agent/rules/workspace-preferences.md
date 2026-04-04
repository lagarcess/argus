---
trigger: always_on
description: Workspace, file generation, and package management preferences
---

# Workspace Preferences

When working on this repository, AI agents must adhere to the following rules regarding file generation, temporary work, and package management:

1. **Use the `temp/` Directory**:
   - ANY ephemeral files, scripts, data dumps, or intermediate outputs used for temporary work MUST be placed in the `temp/` folder.
   - Do not dump temporary files in the root directory or clutter the main project folders.

2. **Keep the Environment Clean**:
   - Do not leave behind scratchpad files, generated test data, or debug logs in the root `crypto-signals/` directory.
   - For temporary script execution or scratch files needed during interactions, strictly use the `temp/` directory.

3. **Cleanup**:
   - The `temp/` directory is ephemeral. Agents may use it freely but should not store any production code or permanent documentation there.
   - Do not remove the `.gitkeep` file.

4. **Package Management**:
   - For development, use **Poetry** for package management.
   - Prefer to use the already supported packages shown in `pyproject.toml`.
   - If a new issue requires a non-supported package, **stop and ask the user** which package they would prefer. Provide a list of similar packages with high adoption, great maintainability, and excellent implemented tools to solve the problem at hand as choices.
