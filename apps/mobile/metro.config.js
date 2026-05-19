const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// IMPORTANT: Do NOT add workspace root to nodeModulesPaths.
// All dependencies are installed in apps/mobile/node_modules (SDK 54).
// Adding workspace root causes the wrong SDK 52 packages (reanimated, etc.)
// to be loaded, breaking the build with RN 0.81.

module.exports = config;
