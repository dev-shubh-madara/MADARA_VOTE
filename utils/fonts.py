from __future__ import annotations

import re

_BTN_FROM = "abcdefghijklmnopqrstuvwxyz"
_BTN_TO = "αbc∂єfgɦιjκℓɱησρqяsτυvωxყz"
_BTN_TABLE = str.maketrans(_BTN_FROM, _BTN_TO)


def btn(text: str) -> str:
    """Convert button label to fancy Unicode style."""
    return text.lower().translate(_BTN_TABLE)


_MSG_TABLE = str.maketrans({
    "A": "𝐀", "B": "𝐁", "C": "𝐂", "D": "𝐃", "E": "𝐄", "F": "𝐅",
    "G": "𝐆", "H": "𝐇", "I": "𝐈", "J": "𝐉", "K": "𝐊", "L": "𝐋",
    "M": "𝐌", "N": "𝐍", "O": "𝐎", "P": "𝐏", "Q": "𝐐", "R": "𝐑",
    "S": "𝐒", "T": "𝐓", "U": "𝐔", "V": "𝐕", "W": "𝐖", "X": "𝐗",
    "Y": "𝐘", "Z": "𝐙",
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ",
    "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
    "m": "ᴍ", "n": "ɴ", "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ",
    "s": "s", "t": "ᴛ", "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x",
    "y": "ʏ", "z": "ᴢ",
})


def _convert_custom_emojis(text: str) -> str:
    if not text:
        return text

    # <emoji id="123">🎉</emoji>
    text = re.sub(
        r'<emoji\s+id=["\'](\d+)["\']\s*>(.*?)</emoji>',
        r'<tg-emoji emoji-id="\1">\2</tg-emoji>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <emoji emoji-id="123">🎉</emoji>
    text = re.sub(
        r'<emoji\s+emoji-id=["\'](\d+)["\']\s*>(.*?)</emoji>',
        r'<tg-emoji emoji-id="\1">\2</tg-emoji>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <emoji id=123>🎉</emoji>
    text = re.sub(
        r'<emoji\s+id=(\d+)\s*>(.*?)</emoji>',
        r'<tg-emoji emoji-id="\1">\2</tg-emoji>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return text


def mf(html: str) -> str:
    """Apply message font while preserving HTML tags, HTML entities (&amp; &lt; etc),
    and custom emojis."""

    if not html:
        return html

    html = _convert_custom_emojis(html)

    # Split on tags AND HTML entities so neither gets its letters stylized -
    # translating "amp" inside "&amp;" would corrupt the entity into "&ᴀᴍᴘ;",
    # which Telegram can no longer parse as an ampersand.
    parts = re.split(r"(<[^>]+>|&[a-zA-Z][a-zA-Z0-9]*;|&#[0-9]+;|&#x[0-9a-fA-F]+;)", html)

    result = []
    inside_code = False

    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            result.append(part)

            low = part.lower()

            if re.match(r"<code(?:\s[^>]*)?>", low):
                inside_code = True
            elif low == "</code>":
                inside_code = False

        elif part.startswith("&") and part.endswith(";"):
            result.append(part)

        else:
            if inside_code:
                result.append(part)
            else:
                result.append(part.translate(_MSG_TABLE))

    return "".join(result)
