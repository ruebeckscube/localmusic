import io
from PIL import Image
from unittest.mock import patch
import PIL
from django.core.files.uploadedfile import SimpleUploadedFile
from findshows.models import JPEGImageException
from findshows.tests.test_helpers import TestCaseHelpers

class JPEGImageFieldTests(TestCaseHelpers):
    def get_test_image(self):
        # Makes a ~325KB png
        file_obj = io.BytesIO()
        px_size = 2543
        image = Image.effect_noise((px_size, px_size), 80) # less easily compressible
        image.save(file_obj, "png")
        file_obj.seek(0)
        return SimpleUploadedFile("test_image.png", file_obj.read(), content_type="image/png")


    def test_successful_save(self):
        image = self.get_test_image()
        self.assertGreater(image.size//1024, 300)
        artist = self.create_artist(profile_picture=image)
        self.assertLessEqual(artist.profile_picture.width, 1200)
        self.assertLessEqual(artist.profile_picture.height, 1200)
        self.assertLessEqual(artist.profile_picture.size//1024, 300)


    @patch('findshows.models.Image.open', side_effect=PIL.UnidentifiedImageError)
    def test_unidentified_image_error(self, *args):
        image = self.get_test_image()
        with self.assertRaises(JPEGImageException):
            self.create_artist(profile_picture=image)


    @patch('findshows.models.Image.Image.save')
    def test_save_os_error(self, mock_save):
        image = self.get_test_image()
        mock_save.side_effect=OSError
        with self.assertRaises(JPEGImageException):
            self.create_artist(profile_picture=image)
