# Automator Quick Action bundle, built by hand

Reference for `assets/Explain selection.workflow`, the Services entry that receives the selected text in any application and pipes it to the capture entrypoint on stdin. Compiled 2026-09-21 from real bundles: joshhopkins/translate-service-macos, cknadler/vim-anywhere, sgeb/macosx-automator-workflows, sheharyarn/dotfiles, ArloL/dotfiles, ludwig/dotfiles on GitHub. Nothing here has been verified on a Mac yet; the phase 5 live test on macOS is the check.

## Layout

```
Explain selection.workflow/
  Contents/
    Info.plist        required
    document.wflow    required
    QuickLook/        optional thumbnail
```

## Info.plist

Required keys: the `NSServices` array with `NSMenuItem` (the menu title) and `NSMessage` set to `runWorkflowAsService`. `NSSendTypes` declares that the service receives text. Omit `NSReturnTypes` because this service returns nothing; a service that declares a return type may write back into the selection.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>Explain selection</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSSendTypes</key>
            <array>
                <string>public.utf8-plain-text</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
```

## document.wflow

Required: `AMApplicationBuild`, `AMApplicationVersion`, one action in `actions` with `ActionBundlePath`, `ActionName`, `ActionParameters` (`COMMAND_STRING`, `inputMethod`, `shell`), `BundleIdentifier`, `UUID`, and `workflowMetaData` with `workflowTypeIdentifier` equal to `com.apple.Automator.servicesMenu`. `inputMethod` 0 means the input goes to stdin, 1 means arguments. UUIDs may be any valid UUID. `serviceInputTypeIdentifier` is `com.apple.Automator.text` for text input; use `com.apple.Automator.nothing` as the output type since nothing is returned. `AMApplicationVersion` 2.10 is the Automator on macOS 26.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>AMApplicationBuild</key>
    <string>523</string>
    <key>AMApplicationVersion</key>
    <string>2.10</string>
    <key>AMDocumentVersion</key>
    <string>2</string>
    <key>actions</key>
    <array>
        <dict>
            <key>action</key>
            <dict>
                <key>AMActionVersion</key>
                <string>2.0.3</string>
                <key>ActionBundlePath</key>
                <string>/System/Library/Automator/Run Shell Script.action</string>
                <key>ActionName</key>
                <string>Run Shell Script</string>
                <key>ActionParameters</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <string>exec "$HOME/.claude/explain-selection/capture" --text -</string>
                    <key>CheckedForUserDefaultShell</key>
                    <true/>
                    <key>inputMethod</key>
                    <integer>0</integer>
                    <key>shell</key>
                    <string>/bin/sh</string>
                    <key>source</key>
                    <string></string>
                </dict>
                <key>BundleIdentifier</key>
                <string>com.apple.RunShellScript</string>
                <key>CFBundleVersion</key>
                <string>2.0.3</string>
                <key>Class Name</key>
                <string>RunShellScriptAction</string>
                <key>InputUUID</key>
                <string>0E9B1D0A-0B7E-4C4E-9D9C-1B6C2A7E5F01</string>
                <key>OutputUUID</key>
                <string>3F5C8A2B-6D1E-4F7A-8B9C-2D4E6F8A0B02</string>
                <key>UUID</key>
                <string>7A1B2C3D-4E5F-4A6B-8C9D-0E1F2A3B4C03</string>
            </dict>
        </dict>
    </array>
    <key>workflowMetaData</key>
    <dict>
        <key>inputTypeIdentifier</key>
        <string>com.apple.Automator.text</string>
        <key>serviceInputTypeIdentifier</key>
        <string>com.apple.Automator.text</string>
        <key>serviceOutputTypeIdentifier</key>
        <string>com.apple.Automator.nothing</string>
        <key>serviceProcessesInput</key>
        <integer>0</integer>
        <key>workflowTypeIdentifier</key>
        <string>com.apple.Automator.servicesMenu</string>
        <key>presentationMode</key>
        <integer>15</integer>
        <key>backgroundColorName</key>
        <string>background</string>
        <key>useAutomaticInputType</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
```

## Keyboard shortcut

After the bundle is copied to `~/Library/Services/`, the service appears in System Settings, Keyboard, Keyboard Shortcuts, Services, under Text. To assign a key from a script:

```sh
defaults write pbs NSServicesStatus -dict-add \
  "(null) - Explain selection - runWorkflowAsService" \
  '{ "enabled_context_menu" = 1; "enabled_services_menu" = 1; "key_equivalent" = "@~e"; }'
/System/Library/CoreServices/pbs -flush
/System/Library/CoreServices/pbs -update
```

- Dictionary key format: `(null) - <NSMenuItem default> - runWorkflowAsService` for workflow services; app services use `bundle.id - Service Name - message`.
- Key equivalent syntax: `@` command, `~` option, `^` control, `$` shift, then the character. `@~e` is command-option-e.
- Community scripts run both `pbs -flush` and `pbs -update`; the shortcut takes effect in applications only after they relaunch. `install` should write the key, verify with `defaults read pbs NSServicesStatus`, and fall back to walking the user through System Settings.

## Sources

- https://github.com/joshhopkins/translate-service-macos
- https://github.com/cknadler/vim-anywhere
- https://github.com/sgeb/macosx-automator-workflows
- https://github.com/sheharyarn/dotfiles
- https://github.com/ArloL/dotfiles
- https://github.com/ludwig/dotfiles
