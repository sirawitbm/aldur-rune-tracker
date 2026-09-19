# Builds dist\PoE2RuneTracker\PoE2RuneTracker.exe - a standalone folder you
# can copy anywhere and double-click to run (no Python install needed).
# Re-run this after any code change; config.json/data/ (session, capture
# history, the learned icon library) are created next to the exe on first
# run and are left alone by rebuilds.

pip install -r requirements.txt
pip install pyinstaller

python -m PyInstaller --noconfirm --onedir --windowed --name PoE2RuneTracker `
    --collect-all winrt `
    --collect-all winocr `
    --add-data "data/rune_icon_seed.json;data" `
    --add-data "data/seed_icons;data/seed_icons" `
    main.py

Write-Host "Done: dist\PoE2RuneTracker\PoE2RuneTracker.exe"
