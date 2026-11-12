"""Exercise installed Mirivue playback against a disposable PipeWire sink."""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import time
import wave

# The workflow supplies a dedicated user, HOME, runtime, X server and D-Bus.
assert os.geteuid() != 0, 'run as the disposable test account'
root = Path(os.environ['HOME'])
assert root.name.startswith('mirivue-media-'), 'dedicated temporary HOME required'
processes = []
logs = []
try:
    for command in (['pipewire'], ['wireplumber'], ['pipewire-pulse']):
        log = (root / (command[0] + '.log')).open('w')
        logs.append(log)
        processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT))
    deadline = time.monotonic() + 20
    while subprocess.run(['pactl', 'info'], capture_output=True).returncode:
        assert time.monotonic() < deadline, 'PipeWire Pulse server did not start'
        time.sleep(.1)
    subprocess.run(['pactl', 'load-module', 'module-null-sink', 'sink_name=mirivue_validation'], check=True)
    subprocess.run(['pactl', 'set-default-sink', 'mirivue_validation'], check=True)
    audio = root / 'tone.wav'
    with wave.open(str(audio), 'wb') as output:
        output.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        second = b''.join(struct.pack('<h', int(6000 * math.sin(2 * math.pi * 440 * n / 48000)))
                          for n in range(48000))
        output.writeframes(second * 30)
    video = root / 'pattern.webm'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=10',
                    '-i', str(audio), '-t', '15', '-c:v', 'libvpx', '-c:a', 'libvorbis', str(video)], check=True)
    # Apply the same backend selection as the installed Fedora launcher.
    if Path('/usr/lib64/qt6/plugins/multimedia/libgstreamermediaplugin.so').is_file():
        os.environ['QT_MEDIA_BACKEND'] = 'gstreamer'
    from PySide6.QtCore import QSettings
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from unittest.mock import patch
    from mirivue.app import Window, prepare_audio_stream_identity
    from mirivue.metadata import basic_entry
    prepare_audio_stream_identity()
    app = QApplication(['Mirivue KDE'])
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('media/start-preview-panel', False)
    with patch('mirivue.app.mirivue_settings', return_value=settings):
        window = Window()
    window.show()

    def wait_for(predicate, message, timeout=20):
        until = time.monotonic() + timeout
        while not predicate() and time.monotonic() < until:
            app.processEvents()
            QTest.qWait(20)
        assert predicate(), message

    # Exercise the application's actual asynchronous image and PDF previews.
    from PySide6.QtGui import QImage, QColor, QPainter, QPdfWriter
    wait_for(lambda: not window.scanning, 'initial directory scan did not finish')
    image_path = root / 'preview.png'
    image = QImage(320, 180, QImage.Format_RGB32)
    image.fill(QColor('#3a7db8'))
    assert image.save(str(image_path))
    pdf_path = root / 'preview.pdf'
    writer = QPdfWriter(str(pdf_path))
    painter = QPainter(writer)
    assert painter.isActive()
    painter.drawText(100, 200, 'Mirivue stable qualification')
    painter.end()
    del writer
    window.preview_dock.show()
    for preview in (image_path, pdf_path):
        window.media_image.clear_preview()
        row = basic_entry(preview)
        window._preview_playlist = [row]
        window._preview_index = 0
        window._preview_pending = row
        window.start_media_preview()
        wait_for(lambda: not window.media_image._image.isNull(), 'preview did not render: ' + preview.suffix)
        if preview == image_path:
            assert window.media_image._image.pixelColor(0, 0).name() == '#3a7db8'
        else:
            assert window._pdf_page_count == 1
        wait_for(lambda: window._preview_worker is None and window._pdf_worker is None,
                 'preview worker did not finish')

    def active_stream():
        result = subprocess.run(['pactl', '-f', 'json', 'list', 'sink-inputs'],
                                capture_output=True, text=True, check=True)
        return any(str(s.get('properties', {}).get('application.process.id')) == str(os.getpid())
                   and not s.get('corked', True) for s in json.loads(result.stdout))

    results = []
    for media in (audio, video):
        window._preview_playlist = [basic_entry(media)]
        window.play_media_at(0)
        player = window.media_player
        assert player is not None
        wait_for(lambda: player.position() > 400, 'playback did not advance')
        if media == video:
            assert window.media_audio.isMuted(), 'video should initially be silent'
            wait_for(lambda: player.videoSink().videoFrame().isValid(), 'no decoded video frame')
        window.set_media_volume(60, False)
        wait_for(active_stream, 'no active Mirivue stream through PipeWire Pulse')
        assert not window.media_audio.isMuted()
        window.toggle_media_playback()
        wait_for(lambda: player.playbackState() == QMediaPlayer.PausedState, 'pause failed')
        position = player.position()
        QTest.qWait(250)
        assert abs(player.position() - position) < 150, 'paused playback advanced'
        window.toggle_media_playback()
        wait_for(lambda: player.position() > position + 200, 'resume failed')
        assert player.error() == QMediaPlayer.NoError, player.errorString()
        results.append(media.suffix)
        window.stop_media_playback()
    # Ten minutes in the actual window; keep the event loop and backend alive.
    started = time.monotonic()
    rounds = 0
    while time.monotonic() - started < 600:
        assert all(p.poll() is None for p in processes), 'audio daemon exited'
        window._preview_playlist = [basic_entry(audio)]
        window.play_media_at(0)
        wait_for(lambda: window.media_player.position() > 200, 'session playback failed')
        window.stop_media_playback()
        window.set_split_view(rounds % 2 == 0, navigate_new=False)
        QTest.qWait(1000)
        app.processEvents()
        rounds += 1
    window.quit_requested = True
    wait_for(window.close, 'window shutdown did not complete')
    print(json.dumps(dict(audio=True, video_frame=True, image_preview=True, pdf_preview=True, pipewire_stream=True,
                          pause_resume=True, video_unmute=True, formats=results,
                          session_seconds=round(time.monotonic() - started), rounds=rounds)), flush=True)
finally:
    for process in reversed(processes):
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for log in logs:
        log.close()
