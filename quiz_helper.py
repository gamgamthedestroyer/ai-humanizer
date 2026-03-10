#!/usr/bin/env python3
"""
Dolphin Quiz Helper
Screen reader + AI quiz solver using Ollama dolphin-llama3
Uses a compiled Swift helper for macOS Vision OCR (no Tesseract needed)
"""

import tkinter as tk
import threading
import queue
import time
import json
import re
import sys
import os
import tempfile
import subprocess

# ── Dependency check ──────────────────────────────────────────────────────────
missing = []
try:
    import ollama
except ImportError:
    missing.append("ollama")
try:
    import mss
except ImportError:
    missing.append("mss")
try:
    from PIL import Image
except ImportError:
    missing.append("Pillow")
try:
    import pyautogui
    pyautogui.FAILSAFE = True   # move mouse to top-left to abort
    pyautogui.PAUSE = 0.1
except ImportError:
    missing.append("pyautogui")

if missing:
    print(f"❌ Missing packages: {', '.join(missing)}")
    print(f"   pip3 install {' '.join(missing)}")
    sys.exit(1)

# ── OCR helper binary ─────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OCR_BIN    = os.path.join(SCRIPT_DIR, "ocr_helper")

if not os.path.exists(OCR_BIN):
    print(f"❌ OCR helper binary not found at {OCR_BIN}")
    print("   Run:  swiftc ocr_helper.swift -o ocr_helper")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
MODEL   = "dolphin-llama3"
PANEL_W = 370
MONO    = "Menlo"
SANS    = "SF Pro Text"

BG      = "#0d1117"
SURFACE = "#161b22"
BORDER  = "#21262d"
ACCENT  = "#f85149"
BLUE    = "#58a6ff"
TEXT    = "#c9d1d9"
MUTED   = "#8b949e"
GREEN   = "#3fb950"
YELLOW  = "#d29922"


# ── OCR ───────────────────────────────────────────────────────────────────────
class OCRWord:
    __slots__ = ("text", "x", "y", "w", "h")
    def __init__(self, text, x, y, w, h):
        self.text = text
        self.x, self.y, self.w, self.h = x, y, w, h


def vision_ocr(img):
    """Run macOS Vision OCR via Swift helper. Returns list of OCRWord (pixel coords)."""
    img_w, img_h = img.size

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = f.name
    try:
        img.save(tmp, "PNG")
        result = subprocess.run(
            [OCR_BIN, tmp],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"OCR helper error: {result.stderr.strip()}")

        raw = json.loads(result.stdout)
        words = []
        for item in raw:
            # Vision bbox: origin = bottom-left, normalised 0-1; flip y for screen
            ox, oy = item["x"], item["y"]
            bw, bh = item["w"], item["h"]
            px = int(ox * img_w)
            py = int((1.0 - oy - bh) * img_h)
            pw = int(bw * img_w)
            ph = int(bh * img_h)
            words.append(OCRWord(item["t"], px, py, pw, ph))
        return words
    finally:
        os.unlink(tmp)


def words_to_text(words):
    """Reconstruct readable text sorted top→bottom, left→right."""
    if not words:
        return ""
    sorted_words = sorted(words, key=lambda w: w.y)
    lines = []
    for word in sorted_words:
        placed = False
        for line in lines:
            if abs(word.y - line[0].y) < 20:
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])
    return "\n".join(
        " ".join(w.text for w in sorted(line, key=lambda w: w.x))
        for line in lines
    )


def find_phrase_coords(words, phrase):
    """Return (cx, cy) pixel centre of first occurrence of phrase in OCR words."""
    tokens = phrase.lower().split()
    texts  = [w.text.lower() for w in words]
    n      = len(tokens)

    for i in range(len(texts) - n + 1):
        if [texts[j] for j in range(i, i + n)] == tokens:
            matched = [words[j] for j in range(i, i + n)]
            lx = min(w.x for w in matched)
            ty = min(w.y for w in matched)
            rx = max(w.x + w.w for w in matched)
            by = max(w.y + w.h for w in matched)
            return (lx + rx) // 2, (ty + by) // 2

    if n > 2:
        return find_phrase_coords(words, " ".join(tokens[:n - 1]))
    return None


# ── App ───────────────────────────────────────────────────────────────────────
class QuizHelper:
    def __init__(self):
        self.root    = tk.Tk()
        self.q       = queue.Queue()
        self.busy    = False
        self.history = []

        self._build_window()
        self._build_ui()
        self._poll_queue()
        self._sys_msg(
            "🐬  Dolphin Quiz Helper ready!\n\n"
            "• Click  🎯 Do My Quiz  to auto-answer the quiz on screen\n"
            "• Click  👁 Read Screen  to describe what's visible\n"
            "• Type anything to chat with Dolphin\n\n"
            "⚠️  If prompts appear, grant Accessibility + Screen Recording\n"
            "    in System Settings → Privacy & Security, then relaunch."
        )

    # ── Window ────────────────────────────────────────────────────────────────
    def _build_window(self):
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.root.title("Quiz Helper")
        self.root.configure(bg=BG)
        self.root.geometry(f"{PANEL_W}x{self.sh}+{self.sw - PANEL_W}+0")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(hdr, text="🐬  Quiz Helper", bg=BG, fg=ACCENT,
                 font=(SANS, 15, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text=MODEL, bg=BG, fg=MUTED,
                 font=(MONO, 8)).pack(side=tk.RIGHT, pady=4)

        # Buttons
        bf = tk.Frame(self.root, bg=BG)
        bf.pack(fill=tk.X, padx=12, pady=4)
        self.quiz_btn = self._btn(bf, "🎯  Do My Quiz",  ACCENT, self._trig_quiz)
        self.quiz_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.read_btn = self._btn(bf, "👁  Read Screen", BLUE,  self._trig_read)
        self.read_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X, padx=12, pady=6)

        # Chat log
        self.chat = tk.Text(
            self.root, bg=SURFACE, fg=TEXT,
            font=(MONO, 10), wrap=tk.WORD, relief=tk.FLAT,
            padx=10, pady=8, state=tk.DISABLED, cursor="arrow",
            selectbackground=BLUE + "44"
        )
        self.chat.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))

        for tag, cfg in {
            "you":  {"foreground": ACCENT,  "font": (MONO, 10, "bold")},
            "ai":   {"foreground": BLUE,    "font": (MONO, 10, "bold")},
            "sys":  {"foreground": MUTED,   "font": (MONO,  9, "italic")},
            "body": {"foreground": TEXT,    "font": (MONO, 10)},
            "ok":   {"foreground": GREEN,   "font": (MONO, 10, "bold")},
            "warn": {"foreground": YELLOW,  "font": (MONO, 10)},
            "err":  {"foreground": ACCENT,  "font": (MONO, 10, "bold")},
        }.items():
            self.chat.tag_configure(tag, **cfg)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X, padx=12)

        # Input
        inp_f = tk.Frame(self.root, bg=BG)
        inp_f.pack(fill=tk.X, padx=12, pady=8)

        self.inp = tk.Text(
            inp_f, bg=SURFACE, fg=TEXT, font=(MONO, 10),
            height=3, relief=tk.FLAT, padx=8, pady=8,
            insertbackground=TEXT, wrap=tk.WORD
        )
        self.inp.pack(fill=tk.X, pady=(0, 6))
        self.inp.bind("<Return>",       self._on_enter)
        self.inp.bind("<Shift-Return>", lambda e: None)

        bot = tk.Frame(inp_f, bg=BG)
        bot.pack(fill=tk.X)
        self.status_lbl = tk.Label(bot, text="● Ready", bg=BG, fg=GREEN,
                                   font=(MONO, 9), anchor=tk.W)
        self.status_lbl.pack(side=tk.LEFT)
        self._btn(bot, "Send ↵", ACCENT, self._trig_chat,
                  padx=14, pady=4).pack(side=tk.RIGHT)

    def _btn(self, parent, text, color, cmd, **kw):
        return tk.Button(
            parent, text=text, bg=color, fg="white",
            font=(SANS, 10, "bold"), relief=tk.FLAT, cursor="hand2",
            activebackground=color, activeforeground="white",
            command=cmd, padx=kw.get("padx", 8), pady=kw.get("pady", 6),
            borderwidth=0
        )

    # ── Thread-safe UI ────────────────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(40, self._poll_queue)

    def _ui(self, fn):
        self.q.put(fn)

    def _append(self, label, label_tag, text, text_tag="body"):
        def _do():
            self.chat.configure(state=tk.NORMAL)
            if label:
                self.chat.insert(tk.END, f"\n{label}\n", label_tag)
            self.chat.insert(tk.END, f"{text}\n", text_tag)
            self.chat.configure(state=tk.DISABLED)
            self.chat.see(tk.END)
        self._ui(_do)

    def _user_msg(self, t): self._append("You:", "you", t)
    def _ai_msg(self, t):   self._append("🐬 Dolphin:", "ai", t)
    def _sys_msg(self, t, tag="sys"): self._append(None, "", t, tag)

    def _set_status(self, text, color=MUTED):
        self._ui(lambda: self.status_lbl.configure(text=f"● {text}", fg=color))

    def _set_busy(self, busy):
        self.busy  = busy
        state      = tk.DISABLED if busy else tk.NORMAL
        color      = YELLOW      if busy else GREEN
        status     = "Working…"  if busy else "Ready"
        def _do():
            self.quiz_btn.configure(state=state)
            self.read_btn.configure(state=state)
            self.status_lbl.configure(text=f"● {status}", fg=color)
        self._ui(_do)

    # ── Screen capture ────────────────────────────────────────────────────────
    def _capture(self):
        with mss.mss() as sct:
            region = {"top": 0, "left": 0,
                      "width": self.sw - PANEL_W, "height": self.sh}
            shot = sct.grab(region)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    # ── Ollama ────────────────────────────────────────────────────────────────
    def _ask(self, user_msg, system=None):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(self.history[-8:])
        msgs.append({"role": "user", "content": user_msg})
        resp = ollama.chat(model=MODEL, messages=msgs)
        return resp["message"]["content"]

    # ── Worker: quiz ──────────────────────────────────────────────────────────
    def _run_quiz(self):
        try:
            self._set_status("Capturing screen…", BLUE)
            time.sleep(0.4)
            img = self._capture()

            self._set_status("Running OCR…", BLUE)
            words = vision_ocr(img)
            text  = words_to_text(words)

            if not text.strip():
                self._sys_msg("❌  No text detected on screen.", "err")
                return

            self._set_status("Asking Dolphin…", BLUE)

            prompt = f"""You are a quiz-solving expert. Analyse the quiz text below and determine the correct answer.

SCREEN TEXT:
{text}

---
Reply with ONLY a JSON object — no extra prose — using exactly these keys:
{{
  "question":       "the question text",
  "choices":        {{"A": "choice text", "B": "choice text"}},
  "correct_letter": "A",
  "correct_text":   "exact answer text as it appears on screen",
  "reasoning":      "one-sentence explanation",
  "confidence":     "high | medium | low"
}}"""

            raw = self._ask(prompt,
                            system="You are a quiz-answering assistant. "
                                   "Always reply with valid JSON only, nothing else.")

            m = re.search(r'\{[\s\S]*\}', raw)
            if not m:
                self._ai_msg(raw)
                return
            try:
                ans = json.loads(m.group())
            except json.JSONDecodeError:
                self._ai_msg(raw)
                return

            letter = ans.get("correct_letter", "?")
            answer = ans.get("correct_text", "")
            reason = ans.get("reasoning", "")
            conf   = ans.get("confidence", "?")
            q_text = ans.get("question", "?")

            self._ai_msg(
                f"Question: {q_text}\n\n"
                f"✅  Answer: {letter})  {answer}\n\n"
                f"💭  {reason}\n"
                f"Confidence: {conf}"
            )

            # ── Click the answer
            if answer and words:
                clicked = False
                a_words = answer.split()
                for k in range(len(a_words), 0, -1):
                    phrase = " ".join(a_words[:k])
                    coords = find_phrase_coords(words, phrase)
                    if coords:
                        cx, cy = coords
                        self._sys_msg(f"🖱️  Clicking ({cx}, {cy}) — \"{phrase}\"")
                        time.sleep(0.3)
                        pyautogui.click(cx, cy)
                        self._sys_msg(f"✅  Clicked: {answer}", "ok")
                        clicked = True
                        break

                if not clicked:
                    self._sys_msg(
                        f"⚠️  Couldn't locate answer on screen.\n"
                        f"    Correct answer: {letter})  {answer}", "warn"
                    )

            self.history.append({"role": "user",      "content": f"[Quiz]\n{text}"})
            self.history.append({"role": "assistant",  "content": answer})

        except Exception as exc:
            import traceback
            self._sys_msg(f"❌  {exc}\n{traceback.format_exc()}", "err")
        finally:
            self._set_busy(False)

    # ── Worker: read screen ───────────────────────────────────────────────────
    def _run_read(self):
        try:
            self._set_status("Capturing screen…", BLUE)
            time.sleep(0.3)
            img   = self._capture()

            self._set_status("Running OCR…", BLUE)
            words = vision_ocr(img)
            text  = words_to_text(words)

            if not text.strip():
                self._sys_msg("❌  No text found on screen.", "err")
                return

            self._set_status("Asking Dolphin…", BLUE)
            reply = self._ask(
                f"Briefly describe what's on this screen in 2–3 sentences:\n\n{text}"
            )
            self._ai_msg(reply)

        except Exception as exc:
            self._sys_msg(f"❌  {exc}", "err")
        finally:
            self._set_busy(False)

    # ── Worker: chat ──────────────────────────────────────────────────────────
    def _run_chat(self, msg):
        try:
            reply = self._ask(msg)
            self._ai_msg(reply)
            self.history.append({"role": "user",     "content": msg})
            self.history.append({"role": "assistant", "content": reply})
        except Exception as exc:
            self._sys_msg(f"❌  {exc}", "err")
        finally:
            self._set_busy(False)

    # ── Triggers ─────────────────────────────────────────────────────────────
    def _trig_quiz(self):
        if self.busy:
            return
        self._set_busy(True)
        self._sys_msg("🎯  Starting quiz solver… switch to your quiz window now!")
        threading.Thread(target=self._run_quiz, daemon=True).start()

    def _trig_read(self):
        if self.busy:
            return
        self._set_busy(True)
        self._sys_msg("👁  Reading screen…")
        threading.Thread(target=self._run_read, daemon=True).start()

    def _trig_chat(self):
        if self.busy:
            return
        msg = self.inp.get("1.0", tk.END).strip()
        if not msg:
            return
        self.inp.delete("1.0", tk.END)
        self._user_msg(msg)

        low = msg.lower()
        if any(k in low for k in ("do my quiz", "do quiz", "answer quiz", "solve quiz")):
            self._trig_quiz()
            return
        if any(k in low for k in ("read screen", "what's on screen",
                                   "describe screen", "what do you see")):
            self._trig_read()
            return

        self._set_busy(True)
        threading.Thread(target=self._run_chat, args=(msg,), daemon=True).start()

    def _on_enter(self, event):
        self._trig_chat()
        return "break"

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = QuizHelper()
    app.run()
