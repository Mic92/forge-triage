Output demo.gif

Set Shell bash
Set FontSize 14
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"

Type "./result/bin/forge-triage"
Enter
Sleep 3s

# Navigate down through notifications
Sleep 1s
Type "j"
Sleep 500ms
Type "j"
Sleep 500ms
Type "j"
Sleep 500ms
Type "j"
Sleep 500ms

# Open filter
Type "/"
Sleep 500ms
Type "nixpkgs"
Sleep 500ms
Enter
Sleep 1.5s

# Clear filter
Escape
Sleep 1s

# Show help
Type "?"
Sleep 2s
Escape
Sleep 1s

# Quit
Type "q"
Sleep 500ms
