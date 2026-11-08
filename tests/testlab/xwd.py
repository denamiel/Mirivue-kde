# SPDX-License-Identifier: MIT
"""Convert an X Window Dump (xwd -root) to PNG without third-party modules.

Only the formats produced by Xvfb are needed: ZPixmap, TrueColor/DirectColor,
depth 24 or 32 with 32 bits per pixel (or 24 bits per pixel), either byte order.
"""
import struct
import zlib

ZPIXMAP = 2
HEADER_FIELDS = 25


class XwdError(ValueError):
    pass


def _channel(pixel, mask):
    if not mask:
        return 0
    shift = (mask & -mask).bit_length() - 1
    width = (mask >> shift).bit_length()
    value = (pixel & mask) >> shift
    return value if width == 8 else round(value * 255 / ((1 << width) - 1))


def decode(data):
    """Return (width, height, rows of RGB bytes)."""
    if len(data) < HEADER_FIELDS * 4:
        raise XwdError('Fichier XWD tronqué.')
    for order in ('>', '<'):
        fields = struct.unpack(order + 'I' * HEADER_FIELDS, data[:HEADER_FIELDS * 4])
        if fields[1] == 7:  # file_version
            break
    else:
        raise XwdError('Version XWD non reconnue.')
    (header_size, _version, pixmap_format, _depth, width, height, _xoffset,
     byte_order, _unit, _bit_order, _pad, bits_per_pixel, bytes_per_line,
     _visual_class, red_mask, green_mask, blue_mask, _bits_rgb, _entries,
     ncolors) = fields[:20]
    if pixmap_format != ZPIXMAP or bits_per_pixel not in (24, 32):
        raise XwdError(f'Format XWD non pris en charge : {pixmap_format}/{bits_per_pixel}.')
    offset = header_size + ncolors * 12
    if len(data) < offset + bytes_per_line * height:
        raise XwdError('Données XWD incomplètes.')
    step = bits_per_pixel // 8
    endian = 'little' if byte_order == 0 else 'big'
    rows = []
    for y in range(height):
        start = offset + y * bytes_per_line
        line = data[start:start + width * step]
        out = bytearray(width * 3)
        for x in range(width):
            pixel = int.from_bytes(line[x * step:x * step + step], endian)
            out[x * 3] = _channel(pixel, red_mask)
            out[x * 3 + 1] = _channel(pixel, green_mask)
            out[x * 3 + 2] = _channel(pixel, blue_mask)
        rows.append(bytes(out))
    return width, height, rows


def png_bytes(width, height, rows):
    def chunk(kind, payload):
        body = kind + payload
        return struct.pack('>I', len(payload)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)
    raw = b''.join(b'\x00' + row for row in rows)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6))
            + chunk(b'IEND', b''))


def convert(xwd_path, png_path):
    width, height, rows = decode(open(xwd_path, 'rb').read())
    with open(png_path, 'wb') as output:
        output.write(png_bytes(width, height, rows))
    return width, height
