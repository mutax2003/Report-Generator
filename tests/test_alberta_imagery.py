"""Alberta imagery assets."""

from __future__ import annotations

import unittest

from ui.alberta_imagery import (
    HERO_IMAGE,
    SAMPLES_DIR,
    _image_paths,
    has_alberta_images,
    pick_image,
)


class TestAlbertaImagery(unittest.TestCase):
    def test_samples_photos_used(self) -> None:
        sample_imgs = [
            p
            for p in _image_paths()
            if p.parent.resolve() == SAMPLES_DIR.resolve()
        ]
        self.assertGreaterEqual(
            len(sample_imgs),
            1,
            "Add .jpg/.webp photos to samples/ (see imagery_manifest.json)",
        )

    def test_has_images(self) -> None:
        self.assertTrue(has_alberta_images())
        for p in _image_paths():
            self.assertEqual(p.parent.resolve(), SAMPLES_DIR.resolve())

    def test_hero_uses_lake_jpg(self) -> None:
        lake = SAMPLES_DIR / HERO_IMAGE
        if not lake.is_file():
            self.skipTest(f"missing samples/{HERO_IMAGE}")
        hero = pick_image(variant="hero")
        self.assertIsNotNone(hero)
        self.assertEqual(hero.name, HERO_IMAGE)

    def test_lake_file_readable(self) -> None:
        path = SAMPLES_DIR / HERO_IMAGE
        if not path.is_file():
            self.skipTest(f"missing samples/{HERO_IMAGE}")
        self.assertGreater(len(path.read_bytes()), 1000)

    def test_pick_rotates_sidebar(self) -> None:
        if not has_alberta_images():
            self.skipTest("no alberta images")
        self.assertIsNotNone(pick_image(variant="sidebar"))
        self.assertTrue(pick_image(variant="sidebar").is_file())


if __name__ == "__main__":
    unittest.main()
