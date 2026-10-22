"""Veil - a programming language written entirely in blank Unicode characters.

SOURCE FORMAT
  A program is a stream of four blank symbols, used as base-4 digits:
      A = U+3164 (0)   B = U+200B (1)   C = U+2060 (2)   D = U+FEFF (3)
  Every other character (letters, spaces, newlines) is IGNORED, so any
  visible text you add is just a comment.

ENCODING (prefix code, so no terminators / escaping are needed)
  node    = opcode (3 symbols) followed by that opcode's operands
  number  = base-3 digits written with A,B,C, ended by D   (0 is just "D")
  string  = byte-count (number) + 4 symbols per UTF-8 byte
  list    = count (number) + that many nodes

Variables are numbers, not names, so the source reveals nothing readable.
The Studio's "readable view" is a lens for humans: compile_text() turns a
tiny S-expression syntax into blank source, disassemble() goes back.
"""
import json
import operator
import re
import sys

A, B, C, D = "\u3164", "\u200b", "\u2060", "\ufeff"
DIGITS = (A, B, C, D)
IDX = {c: i for i, c in enumerate(DIGITS)}

# Glyph lens (still unreadable — just visible void)
GLYPHS = ("·", "░", "▒", "█")  # maps to A B C D
GLYPH_TO_DIGIT = {g: DIGITS[i] for i, g in enumerate(GLYPHS)}
DIGIT_TO_GLYPH = {DIGITS[i]: GLYPHS[i] for i in range(4)}

# Marker prefix for (md ...) output lines — Studio renders these as markdown
MD_MARK = "\x00md\n"

# Rough “will this look empty / survive paste?” notes for the current alphabet
SURVIVAL = {
    A: ("Hangul filler U+3164", "often a wide empty glyph in fonts; Notepad may show a box; Discord/GitHub usually keep it"),
    B: ("ZWSP U+200B", "invisible; many messengers strip or normalize; GitHub usually keeps in files"),
    C: ("Word joiner U+2060", "invisible; often stripped by Discord/Slack paste"),
    D: ("BOM U+FEFF", "invisible; editors may strip a leading BOM; mid-file often kept"),
}


def blank_only(source: str) -> str:
    """Keep only program digits (decoy / whitespace stripped)."""
    return "".join(ch for ch in source if ch in IDX)


def to_glyphs(source: str) -> str:
    """Map blank digits → ·░▒█; leave decoy text as-is."""
    return "".join(DIGIT_TO_GLYPH.get(ch, ch) for ch in source)


def from_glyphs(text: str) -> str:
    """Map ·░▒█ → blank digits; leave other chars as-is."""
    return "".join(GLYPH_TO_DIGIT.get(ch, ch) for ch in text)


def analyze_emptiness(source: str) -> dict:
    """Stats + joke warnings for the status bar / diagnostics."""
    blanks = [ch for ch in source if ch in IDX]
    other = [ch for ch in source if ch not in IDX and not ch.isspace()]
    spaces = [ch for ch in source if ch.isspace()]
    # simpler counts by digit letter:
    by_digit = {"A": blanks.count(A), "B": blanks.count(B),
                "C": blanks.count(C), "D": blanks.count(D)}

    warnings = []
    if not blanks:
        warnings.append("No blank symbols — file is genuinely empty (or only decoy).")
    if by_digit["B"] or by_digit["C"]:
        warnings.append("Contains ZWSP/WJ — Discord/Slack paste may strip the program.")
    if by_digit["D"]:
        warnings.append("Contains BOM (U+FEFF) — some editors strip it at file start.")
    if by_digit["A"]:
        warnings.append("Contains Hangul filler — may show as a blank box in Notepad, not 'empty'.")
    if other:
        warnings.append(f"{len(other)} visible decoy chars (ignored by Veil).")
    # "appears blank" heuristic: no visible non-space, only blanks + whitespace
    appears_blank = len(other) == 0
    if appears_blank and blanks:
        warnings.append("Looks empty in most UIs that hide ZW* / BOM — until Hangul filler paints a hole.")

    return {
        "chars": len(source),
        "blanks": len(blanks),
        "decoy": len(other),
        "whitespace": len(spaces),
        "by_digit": by_digit,
        "appears_blank": appears_blank,
        "warnings": warnings,
    }


# Camouflage: {BLANK} is replaced by the blank program stream
CAMOUFLAGE = {
    "essay": (
        "In conclusion, further research is needed.\n"
        "{BLANK}\n"
        "We gratefully acknowledge the anonymous reviewers."
    ),
    "css": (
        "/* layout helpers — do not remove */\n"
        ".veil-spacer::{BLANK}\n"
        "  content: \"\";\n"
        "}\n"
    ),
    "python": (
        "# typing: ignore\n"
        "def _():\n"
        "    ...  # {BLANK}\n"
        "    return None\n"
    ),
    "markdown": (
        "# Notes\n\n"
        "<!-- {BLANK} -->\n\n"
        "_draft — ignore_\n"
    ),
}


def hide_in(source: str, template_name: str) -> str:
    blank = blank_only(source)
    if not blank:
        raise VeilError("Nothing to hide — no blank symbols in source")
    tmpl = CAMOUFLAGE.get(template_name)
    if tmpl is None:
        raise VeilError(f"Unknown camouflage {template_name!r}")
    return tmpl.replace("{BLANK}", blank)


def blank_diff(a: str, b: str) -> str:
    """Human-readable diff of blank streams only (decoy ignored)."""
    sa, sb = blank_only(a), blank_only(b)
    if sa == sb:
        return "No blank changes (decoy-only edit, or identical programs)."
    # tiny LCS-free summary — good enough for the joke
    lines = [
        f"blanks: {len(sa)} → {len(sb)} ({len(sb) - len(sa):+d})",
        f"glyphs A: {to_glyphs(sa)}",
        f"glyphs B: {to_glyphs(sb)}",
    ]
    # first mismatch index
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            lines.append(f"first mismatch at blank index {i}: {DIGIT_TO_GLYPH[x]} → {DIGIT_TO_GLYPH[y]}")
            break
    else:
        if len(sa) != len(sb):
            lines.append("prefix identical; length differs (insertion/deletion at end).")
    return "\n".join(lines)


def split_run_output(lines):
    """Split run_source lines into (plain_text_lines, markdown_chunks)."""
    text, md = [], []
    for line in lines:
        if isinstance(line, str) and line.startswith(MD_MARK):
            md.append(line[len(MD_MARK):])
        else:
            text.append(line)
    return text, md


# name, operand signature, readable keyword
# signature: x=expression  *=list of expressions  i=number  I=list of numbers  s=string
SPEC = [
    ("NULL", "", "null"), ("TRUE", "", "true"), ("FALSE", "", "false"),
    ("INT", "i", None), ("FLOAT", "s", None), ("STR", "s", None), ("VAR", "i", None),
    ("LET", "ix", "let"), ("SET", "ix", "set"), ("BLOCK", "*", "block"),
    ("PRINT", "x", "print"), ("INPUT", "", "input"),
    ("ADD", "xx", "+"), ("SUB", "xx", "-"), ("MUL", "xx", "*"), ("DIV", "xx", "/"),
    ("IDIV", "xx", "//"), ("MOD", "xx", "%"), ("POW", "xx", "**"), ("NEG", "x", "neg"),
    ("EQ", "xx", "=="), ("NE", "xx", "!="), ("LT", "xx", "<"), ("GT", "xx", ">"),
    ("LE", "xx", "<="), ("GE", "xx", ">="),
    ("AND", "xx", "and"), ("OR", "xx", "or"), ("NOT", "x", "not"),
    ("IF", "xxx", "if"), ("WHILE", "xx", "while"), ("FOREACH", "ixx", "foreach"),
    ("RANGE", "xx", "range"), ("BREAK", "", "break"), ("CONTINUE", "", "continue"),
    ("RETURN", "x", "return"), ("FUNC", "Ix", "fn"), ("CALL", "x*", None),
    ("LIST", "*", "list"), ("DICT", "*", "dict"),
    ("GET", "xx", "get"), ("PUT", "xxx", "put"), ("PUSH", "xx", "push"),
    ("POP", "x", "pop"), ("LEN", "x", "len"), ("SLICE", "xxx", "slice"),
    ("KEYS", "x", "keys"), ("HAS", "xx", "has"),
    ("TOSTR", "x", "str"), ("TOINT", "x", "int"), ("TOFLOAT", "x", "float"),
    ("TYPE", "x", "type"), ("ORD", "x", "ord"), ("CHR", "x", "chr"),
    ("THROW", "x", "throw"), ("TRY", "xix", "try"),
    # Append-only: do not insert earlier or existing .veil opcode numbers break
    ("MD", "x", "md"),
]
CODE = {n: i for i, (n, _, _) in enumerate(SPEC)}
SIG = {n: s for n, s, _ in SPEC}
TEXT = {n: t for n, _, t in SPEC}
BY_TEXT = {t: n for n, _, t in SPEC if t}
BIG = 1 << 30


class VeilError(Exception):
    pass


class VeilHalt(VeilError):
    """Not catchable by try (step limit)."""


# ------------------------------------------------------------------ encoding
def _num(n):
    ds = []
    while n:
        n, r = divmod(n, 3)
        ds.append(DIGITS[r])
    return "".join(reversed(ds)) + D


def _str(s):
    raw = s.encode("utf-8")
    return _num(len(raw)) + "".join(
        DIGITS[b >> 6] + DIGITS[(b >> 4) & 3] + DIGITS[(b >> 2) & 3] + DIGITS[b & 3]
        for b in raw
    )


def encode(node):
    out = []

    def walk(n):
        name, ops = n
        c = CODE[name]
        out.append(DIGITS[c >> 4] + DIGITS[(c >> 2) & 3] + DIGITS[c & 3])
        for kind, v in zip(SIG[name], ops):
            if kind == "x":
                walk(v)
            elif kind == "*":
                out.append(_num(len(v)))
                for k in v:
                    walk(k)
            elif kind == "i":
                out.append(_num(v))
            elif kind == "I":
                out.append(_num(len(v)))
                out.extend(_num(i) for i in v)
            else:
                out.append(_str(v))

    walk(node)
    return "".join(out)


class _Reader:
    def __init__(self, source):
        self.d = [IDX[c] for c in source if c in IDX]
        self.i = 0

    def digit(self):
        if self.i >= len(self.d):
            raise VeilError("Unexpected end of program")
        v = self.d[self.i]
        self.i += 1
        return v

    def num(self):
        n = 0
        while True:
            d = self.digit()
            if d == 3:
                return n
            n = n * 3 + d

    def string(self):
        raw = bytearray()
        for _ in range(self.num()):
            b = 0
            for _ in range(4):
                b = b * 4 + self.digit()
            raw.append(b)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raise VeilError(f"Invalid text data before symbol {self.i}") from None

    def node(self):
        at = self.i
        code = self.digit() * 16 + self.digit() * 4 + self.digit()
        if code >= len(SPEC):
            raise VeilError(f"Unknown opcode {code} at symbol {at}")
        name = SPEC[code][0]
        ops = []
        for kind in SIG[name]:
            if kind == "x":
                ops.append(self.node())
            elif kind == "*":
                ops.append([self.node() for _ in range(self.num())])
            elif kind == "i":
                ops.append(self.num())
            elif kind == "I":
                ops.append([self.num() for _ in range(self.num())])
            else:
                ops.append(self.string())
        return (name, ops)


def decode(source):
    r = _Reader(source)
    if not r.d:
        return ("BLOCK", [[]])
    node = r.node()
    if r.i != len(r.d):
        raise VeilError(f"Extra symbols after program end (symbol {r.i})")
    return node


# --------------------------------------------------- readable text -> blank
_NUM = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_TOK = re.compile(r'\s*(?:(;[^\n]*)|("(?:[^"\\]|\\.)*")|([()])|([^\s()";]+))')


def _tokenize(text):
    toks, pos = [], 0
    while True:
        m = _TOK.match(text, pos)
        if not m:
            if text[pos:].strip():
                raise VeilError(f"Bad text near {text[pos:pos + 20].strip()!r}")
            return toks
        pos = m.end()
        if m.group(1):
            continue
        if m.group(2):
            toks.append(("s", m.group(2)))
        elif m.group(3):
            toks.append(("p", m.group(3)))
        else:
            toks.append(("a", m.group(4)))


def _read(toks):
    top, stack = [], []
    cur = top
    for kind, v in toks:
        if kind == "p" and v == "(":
            stack.append(cur)
            new = []
            cur.append(new)
            cur = new
        elif kind == "p":
            if not stack:
                raise VeilError("Unmatched ')'")
            cur = stack.pop()
        elif kind == "s":
            try:
                cur.append(("s", json.loads(v, strict=False)))
            except ValueError:
                raise VeilError(f"Bad string literal {v}") from None
        else:
            cur.append(("n", v) if _NUM.match(v) else ("y", v))
    if stack:
        raise VeilError("Missing ')'")
    return top


class _Compiler:
    def __init__(self):
        self.ids = {}

    def ident(self, f):
        if not (isinstance(f, tuple) and f[0] == "y"):
            raise VeilError("Expected a variable name")
        if f[1] in BY_TEXT or f[1] == "def":
            raise VeilError(f"'{f[1]}' is a keyword, not a variable name")
        return self.ids.setdefault(f[1], len(self.ids))

    def body(self, forms):
        if not forms:
            return ("NULL", [])
        if len(forms) == 1:
            return self.expr(forms[0])
        return ("BLOCK", [[self.expr(f) for f in forms]])

    def params(self, f):
        if not isinstance(f, list):
            raise VeilError("Parameters must be a list, e.g. (a b)")
        return [self.ident(p) for p in f]

    def expr(self, f):
        if isinstance(f, tuple):
            kind, v = f
            if kind == "s":
                return ("STR", [v])
            if kind == "n":
                t = v.lstrip("+-")
                node = ("INT", [int(t)]) if t.isdigit() else ("FLOAT", [repr(float(t))])
                return ("NEG", [node]) if v.startswith("-") else node
            if v in BY_TEXT and SIG[BY_TEXT[v]] == "":
                return (BY_TEXT[v], [])
            return ("VAR", [self.ident(f)])
        if not f:
            raise VeilError("Empty ()")
        head, r = f[0], f[1:]
        if isinstance(head, tuple) and head[0] == "y":
            if head[1] == "def":
                if len(r) < 2:
                    raise VeilError("(def name (params) body...)")
                return ("LET", [self.ident(r[0]),
                                ("FUNC", [self.params(r[1]), self.body(r[2:])])])
            if head[1] in BY_TEXT:
                return self.form(BY_TEXT[head[1]], head[1], r)
        return ("CALL", [self.expr(head), [self.expr(a) for a in r]])

    def form(self, op, name, r):
        def need(lo, hi=None):
            if not lo <= len(r) <= (lo if hi is None else hi):
                raise VeilError(f"({name} ...) has the wrong number of arguments ({len(r)})")

        ex = self.expr
        if op in ("ADD", "SUB", "MUL", "AND", "OR") and len(r) > 2:
            node = ex(r[0])
            for x in r[1:]:
                node = (op, [node, ex(x)])
            return node
        if op == "SUB" and len(r) == 1:
            return ("NEG", [ex(r[0])])
        if op in ("LET", "SET"):
            need(2)
            return (op, [self.ident(r[0]), ex(r[1])])
        if op == "BLOCK":
            return (op, [[ex(x) for x in r]])
        if op == "LIST":
            return (op, [[ex(x) for x in r]])
        if op == "DICT":
            if len(r) % 2:
                raise VeilError("(dict k v k v ...) needs key/value pairs")
            return (op, [[ex(x) for x in r]])
        if op == "IF":
            need(2, 3)
            return (op, [ex(r[0]), ex(r[1]), ex(r[2]) if len(r) == 3 else ("NULL", [])])
        if op == "WHILE":
            need(1, BIG)
            return (op, [ex(r[0]), self.body(r[1:])])
        if op == "FOREACH":
            need(2, BIG)
            return (op, [self.ident(r[0]), ex(r[1]), self.body(r[2:])])
        if op == "RANGE":
            need(1, 2)
            if len(r) == 1:
                return (op, [("INT", [0]), ex(r[0])])
            return (op, [ex(r[0]), ex(r[1])])
        if op == "RETURN":
            need(0, 1)
            return (op, [ex(r[0]) if r else ("NULL", [])])
        if op == "FUNC":
            need(1, BIG)
            return (op, [self.params(r[0]), self.body(r[1:])])
        if op == "SLICE":
            need(2, 3)
            return (op, [ex(r[0]), ex(r[1]), ex(r[2]) if len(r) == 3 else ("NULL", [])])
        if op == "TRY":
            need(3, BIG)
            return (op, [ex(r[0]), self.ident(r[1]), self.body(r[2:])])
        need(len(SIG[op]))
        return (op, [ex(x) for x in r])


def compile_text(text):
    c = _Compiler()
    forms = _read(_tokenize(text))
    return encode(("BLOCK", [[c.expr(f) for f in forms]]))


# --------------------------------------------------- blank -> readable text
def _stmts(n):
    return n[1][0] if n[0] == "BLOCK" else [n]


def _show(node, ind=0):
    op, a = node
    if op in ("NULL", "TRUE", "FALSE", "BREAK", "CONTINUE", "INPUT"):
        return TEXT[op]
    if op == "INT":
        return str(a[0])
    if op == "FLOAT":
        return a[0]
    if op == "STR":
        return json.dumps(a[0], ensure_ascii=False)
    if op == "VAR":
        return f"v{a[0]}"
    if op in ("LET", "SET"):
        head, inline, body = TEXT[op], [f"v{a[0]}", a[1]], []
    elif op == "FUNC":
        head, inline, body = "fn", ["(" + " ".join(f"v{i}" for i in a[0]) + ")"], _stmts(a[1])
    elif op == "WHILE":
        head, inline, body = "while", [a[0]], _stmts(a[1])
    elif op == "FOREACH":
        head, inline, body = "foreach", [f"v{a[0]}", a[1]], _stmts(a[2])
    elif op == "TRY":
        head, inline, body = "try", [a[0], f"v{a[1]}"], _stmts(a[2])
    elif op == "IF":
        head, inline, body = "if", [a[0]], [a[1], a[2]]
    elif op == "BLOCK":
        head, inline, body = "block", [], a[0]
    elif op in ("LIST", "DICT"):
        head, inline, body = TEXT[op], a[0], []
    elif op == "CALL":
        head, inline, body = _show(a[0], ind + 1), a[1], []
    else:
        head, inline, body = TEXT[op], list(a), []
    ik = [k if isinstance(k, str) else _show(k, ind + 1) for k in inline]
    bk = [_show(k, ind + 1) for k in body]
    flat = "(" + " ".join([head] + ik + bk) + ")"
    if len(flat) <= 60 and "\n" not in flat:
        return flat
    pad = "  " * (ind + 1)
    return "(" + " ".join([head] + ik) + "".join("\n" + pad + k for k in bk) + ")"


def disassemble(source):
    return "\n".join(_show(s) for s in _stmts(decode(source)))


# ------------------------------------------------------------------- runtime
class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Throw(Exception):
    def __init__(self, value):
        self.value = value


class Function:
    __slots__ = ("params", "body", "env")

    def __init__(self, params, body, env):
        self.params, self.body, self.env = params, body, env


class Env:
    __slots__ = ("vars", "parent")

    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, i):
        e = self
        while e is not None:
            if i in e.vars:
                return e.vars[i]
            e = e.parent
        raise VeilError(f"Undefined variable v{i}")

    def set(self, i, v):
        e = self
        while e is not None:
            if i in e.vars:
                e.vars[i] = v
                return v
            e = e.parent
        self.vars[i] = v
        return v

    def let(self, i, v):
        self.vars[i] = v
        return v


def fmt(v, top=True):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return v if top else json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x, False) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{fmt(k, False)}: {fmt(x, False)}" for k, x in v.items()) + "}"
    if isinstance(v, Function):
        return "<fn>"
    return str(v)


def _type(v):
    if v is None:
        return "null"
    for t, n in ((bool, "bool"), (int, "int"), (float, "float"), (str, "str"),
                 (list, "list"), (dict, "dict"), (Function, "fn")):
        if isinstance(v, t):
            return n
    return "?"


def _pow(x, y):
    if isinstance(x, int) and isinstance(y, int) and y > 10000 and abs(x) > 1:
        raise VeilError("Exponent too large")
    r = x ** y
    if isinstance(r, complex):
        raise VeilError("Complex result")
    return r


_BIN = {
    "ADD": operator.add, "SUB": operator.sub, "MUL": operator.mul,
    "DIV": operator.truediv, "IDIV": operator.floordiv, "MOD": operator.mod,
    "POW": _pow, "EQ": operator.eq, "NE": operator.ne, "LT": operator.lt,
    "GT": operator.gt, "LE": operator.le, "GE": operator.ge,
}
_CATCH = (TypeError, ValueError, IndexError, KeyError, ZeroDivisionError,
          OverflowError, AttributeError, RecursionError)


class _Runtime:
    def __init__(self, input_fn, max_steps):
        self.input_fn, self.limit, self.steps, self.output = input_fn, max_steps, 0, []

    def ev(self, node, env):
        self.steps += 1
        if self.steps > self.limit:
            raise VeilHalt(f"Step limit ({self.limit}) exceeded - infinite loop?")
        op, a = node
        try:
            return self._ev(op, a, env)
        except _CATCH as exc:
            msg = f"missing key {exc}" if isinstance(exc, KeyError) else str(exc)
            raise VeilError(f"{op}: {msg}") from None

    def call(self, f, args):
        if not isinstance(f, Function):
            raise VeilError("CALL: value is not a function")
        if len(args) != len(f.params):
            raise VeilError(f"CALL: expected {len(f.params)} argument(s), got {len(args)}")
        scope = Env(f.env)
        for p, v in zip(f.params, args):
            scope.let(p, v)
        try:
            return self.ev(f.body, scope)
        except _Return as r:
            return r.value
        except (_Break, _Continue):
            raise VeilError("break/continue outside a loop") from None

    def _ev(self, op, a, env):
        ev = self.ev
        if op in _BIN:
            return _BIN[op](ev(a[0], env), ev(a[1], env))
        if op == "VAR":
            return env.get(a[0])
        if op in ("INT", "STR"):
            return a[0]
        if op == "FLOAT":
            return float(a[0])
        if op == "NULL":
            return None
        if op == "TRUE":
            return True
        if op == "FALSE":
            return False
        if op == "LET":
            return env.let(a[0], ev(a[1], env))
        if op == "SET":
            return env.set(a[0], ev(a[1], env))
        if op == "BLOCK":
            r = None
            for n in a[0]:
                r = ev(n, env)
            return r
        if op == "PRINT":
            v = ev(a[0], env)
            self.output.append(fmt(v))
            return v
        if op == "MD":
            v = fmt(ev(a[0], env))
            self.output.append(MD_MARK + v)
            return v
        if op == "INPUT":
            if self.input_fn is None:
                raise VeilError("INPUT: no input source")
            return str(self.input_fn())
        if op == "NEG":
            return -ev(a[0], env)
        if op == "NOT":
            return not ev(a[0], env)
        if op == "AND":
            x = ev(a[0], env)
            return ev(a[1], env) if x else x
        if op == "OR":
            x = ev(a[0], env)
            return x if x else ev(a[1], env)
        if op == "IF":
            return ev(a[1], env) if ev(a[0], env) else ev(a[2], env)
        if op == "WHILE":
            while ev(a[0], env):
                try:
                    ev(a[1], env)
                except _Break:
                    break
                except _Continue:
                    pass
            return None
        if op == "FOREACH":
            for item in list(ev(a[1], env)):
                env.let(a[0], item)
                try:
                    ev(a[2], env)
                except _Break:
                    break
                except _Continue:
                    pass
            return None
        if op == "RANGE":
            lo, hi = ev(a[0], env), ev(a[1], env)
            if hi - lo > 5_000_000:
                raise VeilError("Range too large")
            return list(range(lo, hi))
        if op == "BREAK":
            raise _Break()
        if op == "CONTINUE":
            raise _Continue()
        if op == "RETURN":
            raise _Return(ev(a[0], env))
        if op == "FUNC":
            return Function(a[0], a[1], env)
        if op == "CALL":
            f = ev(a[0], env)
            return self.call(f, [ev(x, env) for x in a[1]])
        if op == "LIST":
            return [ev(x, env) for x in a[0]]
        if op == "DICT":
            items = [ev(x, env) for x in a[0]]
            return {items[i]: items[i + 1] for i in range(0, len(items) - 1, 2)}
        if op == "GET":
            return ev(a[0], env)[ev(a[1], env)]
        if op == "PUT":
            c, i, v = ev(a[0], env), ev(a[1], env), ev(a[2], env)
            c[i] = v
            return v
        if op == "PUSH":
            c = ev(a[0], env)
            c.append(ev(a[1], env))
            return c
        if op == "POP":
            return ev(a[0], env).pop()
        if op == "LEN":
            return len(ev(a[0], env))
        if op == "SLICE":
            return ev(a[0], env)[ev(a[1], env):ev(a[2], env)]
        if op == "KEYS":
            return list(ev(a[0], env).keys())
        if op == "HAS":
            return ev(a[1], env) in ev(a[0], env)
        if op == "TOSTR":
            return fmt(ev(a[0], env))
        if op == "TOINT":
            return int(ev(a[0], env))
        if op == "TOFLOAT":
            return float(ev(a[0], env))
        if op == "TYPE":
            return _type(ev(a[0], env))
        if op == "ORD":
            return ord(ev(a[0], env))
        if op == "CHR":
            return chr(ev(a[0], env))
        if op == "THROW":
            raise _Throw(ev(a[0], env))
        if op == "TRY":
            try:
                return ev(a[0], env)
            except _Throw as t:
                env.let(a[1], t.value)
            except VeilHalt:
                raise
            except VeilError as e:
                env.let(a[1], str(e))
            return ev(a[2], env)
        raise VeilError(f"Unknown operation {op}")


def run_source(source, input_fn=None, max_steps=3_000_000):
    """Run blank source. Returns the printed lines.
    On failure raises VeilError with the lines printed so far in .output"""
    rt = _Runtime(input_fn, max_steps)
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(6000)
    err = None
    try:
        rt.ev(decode(source), Env())
    except _Return:
        pass
    except (_Break, _Continue):
        err = VeilError("break/continue outside a loop")
    except _Throw as t:
        err = VeilError("Uncaught throw: " + fmt(t.value))
    except VeilError as e:
        err = e
    except RecursionError:
        err = VeilError("Stack overflow")
    finally:
        sys.setrecursionlimit(old_limit)
    if err is not None:
        err.output = rt.output
        raise err
    return rt.output


def hello_world_source():
    return compile_text('(print "Hello, world!")')


def demo_source():
    return compile_text("(print (+ 20 22))")