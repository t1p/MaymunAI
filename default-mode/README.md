# Installing the Default Mode for Roo Code

This document explains how to install the Default mode, which is a global mode that uses Roo Code's default system prompt while incorporating memory bank functionality and mode interactions from the RooFlow customized system prompts. 

## Purpose

The Default mode serves two main purposes:

1. Provides a fallback mode for troubleshooting when Roo Code functionality isn't working correctly with the customized RooFlow system prompts
2. Demonstrates token usage differences between the default system prompt and RooFlow's customized system prompts

## Installation Steps

1. Open Visual Studio Code

2. Open Roo Code's prompt settings:
   - Click on the Roo Code icon in the activity bar
   - Click the prompt settings icon, next to "+ (New Task)"
   - Click "{}" in the top right corner
   - Select "Edit Global Modes" from the dropdown menu

3. This will open your `cline_custom_modes.json` file in the editor. This file is typically located at:
   ```
   /home/[user]/.vscode-server/data/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_custom_modes.json

   or

   C:\Users\[user]\AppData\Roaming\Code\User\globalStorage\rooveterinaryinc.roo-cline\settings\cline_custom_modes.json
   ```

4. Copy the contents of the provided [`cline_custom_modes.json`](https://github.com/GreatScottyMac/RooFlow/blob/main/config/default-mode/cline_custom_modes.json) file into your existing file:
   - If you already have other custom modes, add the Default mode configuration to the `customModes` array
   - If this is your first custom mode, replace the entire contents with the provided configuration

## Configuration Files

The Default mode configuration is split across three files for easier maintenance:

1. [`cline_custom_modes.json`](https://github.com/GreatScottyMac/RooFlow/blob/main/config/default-mode/cline_custom_modes.json): The complete mode configuration in JSON format
2. [`custom-instructions.yaml`](https://github.com/GreatScottyMac/RooFlow/blob/main/config/default-mode/custom-instructions.yaml): The mode-specific instructions in YAML format (for reference if you want to modify the instructions)
3. [`role-definition.txt`](https://github.com/GreatScottyMac/RooFlow/blob/main/config/default-mode/role-definition.txt): The role definition text (for reference if you want to modify the role)

## Verification

After installation, you can verify the Default mode is working correctly:

1. Restart Visual Studio Code
2. Open the Roo Code chat panel
3. Click the mode selector (top of chat panel)
4. You should see "Default" listed as an available mode
5. Select Default mode and verify it responds with the memory bank functionality

## Troubleshooting

If you encounter any issues:

1. Verify the JSON syntax is correct in your `cline_custom_modes.json` file
2. Make sure the file path and permissions are correct
3. Restart Visual Studio Code after making changes
4. Check the VS Code Developer Tools console for any error messages

## Support

If you need help with the installation or encounter any issues, please file an issue on the GitHub repository:
[https://github.com/GreatScottyMac/roo-code-memory-bank](https://github.com/GreatScottyMac/roo-code-memory-bank)