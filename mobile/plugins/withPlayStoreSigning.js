const { withAppBuildGradle } = require("@expo/config-plugins");

const signingEnvironment = `
def playStoreKeystoreFile = System.getenv("ZCHIT_OWNER_KEYSTORE_PATH")
def playStoreKeystorePassword = System.getenv("ZCHIT_OWNER_KEYSTORE_PASSWORD")
def playStoreKeyAlias = System.getenv("ZCHIT_OWNER_KEY_ALIAS")
def playStoreKeyPassword = System.getenv("ZCHIT_OWNER_KEY_PASSWORD")
def hasPlayStoreSigning = playStoreKeystoreFile && playStoreKeystorePassword && playStoreKeyAlias && playStoreKeyPassword
`;

module.exports = function withPlayStoreSigning(config) {
  return withAppBuildGradle(config, (gradleConfig) => {
    let contents = gradleConfig.modResults.contents;

    if (!contents.includes("def hasPlayStoreSigning =")) {
      contents = contents.replace("android {", `${signingEnvironment}\nandroid {`);
    }

    if (!contents.includes("playStoreRelease {")) {
      contents = contents.replace(
        "signingConfigs {\n        debug {",
        `signingConfigs {
        if (hasPlayStoreSigning) {
            playStoreRelease {
                storeFile file(playStoreKeystoreFile)
                storePassword playStoreKeystorePassword
                keyAlias playStoreKeyAlias
                keyPassword playStoreKeyPassword
            }
        }
        debug {`,
      );
    }

    const releaseBlockStart = contents.indexOf("release {");
    if (releaseBlockStart === -1) {
      throw new Error("Unable to locate the Android release build type.");
    }

    const beforeRelease = contents.slice(0, releaseBlockStart);
    const releaseBlock = contents.slice(releaseBlockStart).replace(
      "signingConfig signingConfigs.debug",
      "signingConfig hasPlayStoreSigning ? signingConfigs.playStoreRelease : signingConfigs.debug",
    );
    gradleConfig.modResults.contents = `${beforeRelease}${releaseBlock}`;
    return gradleConfig;
  });
};