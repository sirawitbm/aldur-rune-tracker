import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = (ROOT / "installer.iss").read_text(encoding="utf-8")
        cls.release_script = (ROOT / "release.ps1").read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

    def test_installs_per_user_without_elevation(self):
        self.assertIn("DefaultDirName={localappdata}\\Programs\\AldurRuneTracker", self.installer)
        self.assertIn("PrivilegesRequired=lowest", self.installer)

    def test_upgrade_identity_is_stable(self):
        self.assertIn("AppId={{9D4E9B0C-28DA-4D94-BCB8-E81450E6C4DE}", self.installer)

    def test_runtime_data_is_not_installed_or_deleted_on_upgrade(self):
        self.assertIn('Excludes: "config.json,data\\*"', self.installer)
        self.assertIn('Type: filesandordirs; Name: "{app}\\_internal"', self.installer)
        self.assertNotIn('Name: "{app}\\data"', self.installer)
        self.assertNotIn('Name: "{app}\\config.json"', self.installer)

    def test_release_outputs_installer_and_checksum(self):
        self.assertIn("AldurRuneTracker-v$Version-Setup.exe", self.release_script)
        self.assertIn("installerChecksumPath", self.release_script)
        self.assertIn("dist/release/*-Setup.exe", self.workflow)


if __name__ == "__main__":
    unittest.main()