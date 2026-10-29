from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPreviewAudioOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'mirivue' / 'media_ui.py').read_text(encoding='utf-8')

    def test_video_preview_starts_silent_but_remains_adjustable(self):
        self.assertIn("if kind(row) == tr('video'):\n            self.set_media_volume(0, False)", self.source)
        self.assertIn("self.set_media_volume(self.settings.value('media/volume', 80, type=int), False)", self.source)
        self.assertIn('self.media_audio.setMuted(value == 0)', self.source)

    def test_player_tracks_the_current_default_audio_device(self):
        self.assertIn('QMediaDevices.defaultAudioOutput()', self.source)
        self.assertIn('audioOutputsChanged.connect(self.refresh_media_audio_devices)', self.source)
        self.assertIn('self.media_audio.setDevice(device)', self.source)

    def test_audio_output_can_be_selected_explicitly(self):
        self.assertIn("self.media_audio_device_combo = QComboBox()", self.source)
        self.assertIn("self.settings.setValue('media/audio-device-id', key)", self.source)
        self.assertIn('QMediaDevices.audioOutputs()', self.source)

    def test_volume_changes_do_not_reconnect_the_same_audio_sink(self):
        self.assertIn('self.media_player.audioOutput() != self.media_audio', self.source)
        self.assertIn('self.media_audio.setMuted(value == 0)', self.source)


if __name__ == '__main__':
    unittest.main()
