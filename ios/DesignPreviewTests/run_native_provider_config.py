"""Exercise the production native configuration with synthetic bundles in both builds."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "ios/ArgusFoundation/Auth/NativeProviderSignIn.swift").read_text()
configuration = source[source.index("struct NativeProviderConfiguration:"):source.index("/// Apple and Google buttons")]
checks = r'''
func configuration(apple: Bool, google: Bool, client: String?, scheme: String?) -> NativeProviderConfiguration {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".bundle")
    try! FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: directory) }
    var info: [String: Any] = ["CFBundleIdentifier": "local.synthetic." + UUID().uuidString,
        "ARGUS_APPLE_SIGN_IN_ENABLED": apple, "ARGUS_GOOGLE_SIGN_IN_ENABLED": google]
    info["GOOGLE_SIGN_IN_IOS_CLIENT_ID"] = client
    if let scheme { info["CFBundleURLTypes"] = [["CFBundleURLSchemes": [scheme]]] }
    let data = try! PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0)
    try! data.write(to: directory.appendingPathComponent("Info.plist"))
    return NativeProviderConfiguration.load(bundle: Bundle(path: directory.path)!)
}
var count = 0
for apple in [false, true] {
    for google in [false, true] {
        for configured in [false, true] {
            let actual = configuration(apple: apple, google: google,
                client: configured ? "123-synthetic.apps.googleusercontent.com" : nil,
                scheme: configured ? "com.googleusercontent.apps.123-synthetic" : nil)
            #if DEBUG
            precondition(actual.apple == apple, "Apple respects debug flag")
            precondition((actual.google != nil) == (apple && google && configured), "Google requires Apple and valid callback")
            #else
            precondition(actual == .off, "Release must never enable native providers")
            #endif
            count += 1
        }
    }
}
for (client, scheme) in [("invalid", "com.googleusercontent.apps.123-synthetic"),
    ("123-synthetic.apps.googleusercontent.com", "wrong.callback"),
    ("$(GOOGLE_SIGN_IN_IOS_CLIENT_ID)", "wrong.callback")] {
    precondition(configuration(apple: true, google: true, client: client, scheme: scheme).google == nil)
    count += 1
}
print("Native provider configuration passed \(count) cases")
'''
with tempfile.TemporaryDirectory(prefix="cuadrao-provider-config-") as folder:
    folder = Path(folder)
    swift = folder / "main.swift"
    swift.write_text("import Foundation\n" + configuration + checks)
    for mode in ["Debug", "Release"]:
        executable = folder / mode
        command = ["xcrun", "swiftc", "-module-cache-path", str(folder / "ModuleCache")]
        if mode == "Debug":
            command += ["-D", "DEBUG"]
        subprocess.run(command + [str(swift), "-o", str(executable)], check=True)
        print(mode, flush=True)
        subprocess.run([str(executable)], check=True)
