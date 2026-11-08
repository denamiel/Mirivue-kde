# SPDX-License-Identifier: MIT
"""Minimal Wayland client (pure Python) for KWin's org_kde_kwin_fake_input.

TestLab must drive Wayland sessions without xdotool or third-party modules.
This speaks the Wayland wire protocol directly over the compositor socket:
wl_display.get_registry / sync, wl_registry.bind and the fake-input requests
(keyboard keys, absolute pointer motion, buttons). KWin only exposes the
restricted fake-input interface to such a client when it runs with
KWIN_WAYLAND_NO_PERMISSION_CHECKS=1, which TestLab sets for its disposable
compositor only.
"""
import os
import select
import socket
import struct
import time

FAKE_INPUT = 'org_kde_kwin_fake_input'

# org_kde_kwin_fake_input request opcodes (fake-input.xml, version 6).
AUTHENTICATE, POINTER_MOTION, BUTTON, AXIS = 0, 1, 2, 3
POINTER_MOTION_ABSOLUTE, KEYBOARD_KEY, DESTROY, KEYBOARD_KEYSYM = 9, 10, 11, 12

BTN_LEFT, BTN_RIGHT = 0x110, 0x111

# Linux evdev key codes (linux/input-event-codes.h), US layout.
KEYS = {
    'esc': 1, 'escape': 1, 'backspace': 14, 'tab': 15, 'return': 28, 'enter': 28,
    'ctrl': 29, 'control': 29, 'shift': 42, 'alt': 56, 'space': 57, 'super': 125, 'meta': 125,
    'f1': 59, 'f2': 60, 'f3': 61, 'f4': 62, 'f5': 63, 'f6': 64, 'f7': 65, 'f8': 66,
    'f9': 67, 'f10': 68, 'f11': 87, 'f12': 88, 'delete': 111, 'home': 102, 'end': 107,
    'up': 103, 'down': 108, 'left': 105, 'right': 106, 'page_up': 104, 'page_down': 109,
    'menu': 127,
}
ROWS = {
    '1234567890-=': 2, 'qwertyuiop[]': 16, "asdfghjkl;'": 30, 'zxcvbnm,./': 44,
}
SHIFTED_ROWS = {
    '!@#$%^&*()_+': 2, 'QWERTYUIOP{}': 16, 'ASDFGHJKL:"': 30, 'ZXCVBNM<>?': 44,
}
CHARACTERS = {' ': (57, False), '`': (41, False), '~': (41, True), '\\': (43, False), '|': (43, True),
              '\n': (28, False)}
for row, first in ROWS.items():
    for offset, character in enumerate(row):
        CHARACTERS[character] = (first + offset, False)
for row, first in SHIFTED_ROWS.items():
    for offset, character in enumerate(row):
        CHARACTERS[character] = (first + offset, True)
for letter, code in [(c, CHARACTERS[c][0]) for c in 'abcdefghijklmnopqrstuvwxyz']:
    KEYS[letter] = code
for digit in '0123456789':
    KEYS[digit] = CHARACTERS[digit][0]
for name, character in (('minus', '-'), ('equal', '='), ('comma', ','), ('period', '.'), ('slash', '/')):
    KEYS[name] = CHARACTERS[character][0]


class WaylandError(RuntimeError):
    pass


def _string(value):
    data = value.encode('utf-8') + b'\0'
    return struct.pack('=I', len(data)) + data + b'\0' * (-len(data) % 4)


def _fixed(value):
    return struct.pack('=i', int(round(value * 256)))


def combination(text):
    """'ctrl+shift+n' -> [29, 42, 49] (modifiers first)."""
    codes = []
    for part in text.lower().split('+'):
        if part not in KEYS:
            raise WaylandError(f'Touche inconnue : {part}')
        codes.append(KEYS[part])
    return codes


def text_keys(text):
    """Return (code, shifted) pairs for ASCII text typed on a US layout."""
    result = []
    for character in text:
        if character not in CHARACTERS:
            raise WaylandError(f'Caractère non pris en charge par la saisie Wayland : {character!r}')
        result.append(CHARACTERS[character])
    return result


class Connection:
    """One client connection: registry, roundtrips and fake-input requests."""

    def __init__(self, path, timeout=10.0):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        self.socket.connect(str(path))
        self.timeout = timeout
        self.next_id = 2
        self.buffer = b''
        self.globals = {}
        self.callbacks = set()
        self.registry = self._new_id()
        self._send(1, 1, struct.pack('=I', self.registry))      # wl_display.get_registry
        self.roundtrip()
        self.fake_input = None

    def _new_id(self):
        identifier = self.next_id
        self.next_id += 1
        return identifier

    def _send(self, object_id, opcode, payload=b''):
        self.socket.sendall(struct.pack('=II', object_id, (8 + len(payload)) << 16 | opcode) + payload)

    def _dispatch(self, object_id, opcode, payload):
        if object_id == 1 and opcode == 0:                       # wl_display.error
            failed, code = struct.unpack_from('=II', payload)
            length = struct.unpack_from('=I', payload, 8)[0]
            message = payload[12:12 + length - 1].decode('utf-8', 'replace')
            raise WaylandError(f'Erreur Wayland (objet {failed}, code {code}) : {message}')
        if object_id == self.registry and opcode == 0:          # wl_registry.global
            name, length = struct.unpack_from('=II', payload)
            interface = payload[8:8 + length - 1].decode()
            version = struct.unpack_from('=I', payload, 8 + length + (-length % 4))[0]
            self.globals[interface] = (name, version)
        elif object_id in self.callbacks and opcode == 0:        # wl_callback.done
            self.callbacks.discard(object_id)

    def _read_events(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([self.socket], [], [], remaining)[0]:
            raise WaylandError('Le compositeur Wayland ne répond pas.')
        chunk = self.socket.recv(65536)
        if not chunk:
            raise WaylandError('Connexion Wayland fermée par le compositeur.')
        self.buffer += chunk
        while len(self.buffer) >= 8:
            object_id, header = struct.unpack_from('=II', self.buffer)
            size, opcode = header >> 16, header & 0xFFFF
            if len(self.buffer) < size:
                break
            payload, self.buffer = self.buffer[8:size], self.buffer[size:]
            self._dispatch(object_id, opcode, payload)

    def roundtrip(self):
        """Wait until the compositor has processed every request sent so far."""
        callback = self._new_id()
        self.callbacks.add(callback)
        self._send(1, 0, struct.pack('=I', callback))           # wl_display.sync
        deadline = time.monotonic() + self.timeout
        while callback in self.callbacks:
            self._read_events(deadline)

    def bind_fake_input(self, application='Mirivue TestLab', reason='Tests automatisés'):
        if FAKE_INPUT not in self.globals:
            raise WaylandError('Le compositeur n’expose pas org_kde_kwin_fake_input.')
        name, advertised = self.globals[FAKE_INPUT]
        version = min(advertised, 6)
        if version < 4:
            raise WaylandError(f'org_kde_kwin_fake_input version {advertised} : clavier indisponible.')
        self.fake_input = self._new_id()
        self._send(self.registry, 0, struct.pack('=I', name) + _string(FAKE_INPUT)
                   + struct.pack('=II', version, self.fake_input))
        self._send(self.fake_input, AUTHENTICATE, _string(application) + _string(reason))
        self.roundtrip()

    # ------------------------------------------------------------- input
    def key_event(self, code, pressed):
        self._send(self.fake_input, KEYBOARD_KEY, struct.pack('=II', code, 1 if pressed else 0))

    def press(self, text, delay=0.03):
        codes = combination(text)
        for code in codes:
            self.key_event(code, True)
            self.roundtrip()
            time.sleep(delay)
        for code in reversed(codes):
            self.key_event(code, False)
            self.roundtrip()
            time.sleep(delay)

    def type_text(self, text, delay=0.02):
        for code, shifted in text_keys(text):
            if shifted:
                self.key_event(KEYS['shift'], True)
            self.key_event(code, True)
            self.key_event(code, False)
            if shifted:
                self.key_event(KEYS['shift'], False)
            self.roundtrip()
            time.sleep(delay)

    def move_to(self, x, y):
        self._send(self.fake_input, POINTER_MOTION_ABSOLUTE, _fixed(x) + _fixed(y))
        self.roundtrip()

    def button(self, button, pressed):
        self._send(self.fake_input, BUTTON, struct.pack('=II', button, 1 if pressed else 0))
        self.roundtrip()

    def close(self):
        try:
            if self.fake_input is not None:
                self._send(self.fake_input, DESTROY)
            self.socket.close()
        except OSError:
            pass


def socket_path(environment):
    display = environment.get('WAYLAND_DISPLAY', 'wayland-0')
    return display if os.path.isabs(display) else os.path.join(environment['XDG_RUNTIME_DIR'], display)
