from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestAudioStreamIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')

    def test_launcher_names_the_pipewire_pulse_stream(self):
        launcher = (ROOT / 'Lancer.sh').read_text(encoding='utf-8')
        self.assertIn('PULSE_PROP=', launcher)
        self.assertIn('application.name="Mirivue KDE"', launcher)
        self.assertIn('application.id="org.pdenams.Mirivue.Qt"', launcher)
        self.assertNotIn('application.name=\\"Mirivue KDE\\"', launcher)

    def test_pulse_properties_are_set_before_runtime_initialization(self):
        call = self.app.index('    prepare_audio_stream_identity()')
        runtime = self.app.index('    services.prepare_runtime()', call)
        self.assertLess(call, runtime)
        self.assertIn("os.environ['PULSE_PROP_application.name'] = name", self.app)
        self.assertIn("os.environ['PULSE_PROP_application.icon_name'] = desktop_id", self.app)
        self.assertIn("os.environ['PIPEWIRE_PROPS']", self.app)
        self.assertNotIn("tr('PULSE_PROP", self.app)
        self.assertIn('application.name = "Mirivue KDE"', self.app)

    def test_gstreamer_receives_the_glib_client_name(self):
        self.assertIn("glib.g_set_prgname(encoded)", self.app)
        self.assertIn("glib.g_set_application_name(encoded)", self.app)


if __name__ == '__main__':
    unittest.main()
