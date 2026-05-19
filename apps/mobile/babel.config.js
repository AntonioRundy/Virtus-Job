module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    plugins: [
      [
        "module-resolver",
        {
          root: ["./src"],
          alias: {
            "@": "./src",
          },
          extensions: [".ios.js", ".android.js", ".js", ".jsx", ".ts", ".tsx", ".json"],
        },
      ],
      // NOTE: react-native-reanimated/plugin removed — babel-preset-expo
      // includes it automatically for Expo SDK 54+.
    ],
  };
};
