# Build Tailwind CSS once (production minified)
& "$PSScriptRoot\tailwindcss.exe" -i "$PSScriptRoot\..\static\css\input.css" -o "$PSScriptRoot\..\static\css\output.css" --minify
