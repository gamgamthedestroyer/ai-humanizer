#!/usr/bin/env python3
"""
AI Humanizer + Detector Panel v2
Humanize AI-generated text, then check it against multiple detectors.
"""

import json
import os
import re
import random
import time
import threading
import urllib.parse
import requests
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# ─── Text Humanizer Engine ────────────────────────────────────────────────────

# Overused AI transition phrases → more natural replacements
TRANSITION_SWAPS = {
    r'\bFurthermore\b': lambda: random.choice(["On top of that", "What's more", "And", "Plus"]),
    r'\bAdditionally\b': lambda: random.choice(["Also", "And", "Beyond that", "On top of this"]),
    r'\bMoreover\b': lambda: random.choice(["And", "What's more", "On top of that", "Plus"]),
    r'\bIn conclusion\b': lambda: random.choice(["All in all", "At the end of the day", "So really", "Looking at the big picture"]),
    r'\bIn summary\b': lambda: random.choice(["To sum it up", "Pulling it all together", "So basically", "Bottom line"]),
    r'\bIt is important to note that\b': lambda: random.choice(["Worth mentioning —", "The thing is,", "One key detail:", "Keep in mind that"]),
    r'\bIt is worth noting that\b': lambda: random.choice(["Notably,", "Here's the thing —", "One thing to flag:", "Worth pointing out,"]),
    r'\bConsequently\b': lambda: random.choice(["So", "Because of that", "As a result", "That meant"]),
    r'\bNevertheless\b': lambda: random.choice(["Still", "Even so", "That said", "But"]),
    r'\bNonetheless\b': lambda: random.choice(["Still", "Even so", "That said", "But even then"]),
    r'\bTherefore\b': lambda: random.choice(["So", "Which means", "That's why", "Because of this"]),
    r'\bThus\b': lambda: random.choice(["So", "Which means", "And so", "This way"]),
    r'\bHowever\b': lambda: random.choice(["But", "That said", "Then again", "On the flip side"]),
    r'\bSpecifically\b': lambda: random.choice(["In particular", "To be exact", "More precisely", "Namely"]),
    r'\bUndoubtedly\b': lambda: random.choice(["Without question", "Clearly", "No doubt", "For sure"]),
    r'\bSignificantly\b': lambda: random.choice(["Noticeably", "In a big way", "Quite a bit", "Considerably"]),
    r'\bIn order to\b': lambda: random.choice(["To", "So as to", "For"]),
    r'\bDue to the fact that\b': lambda: random.choice(["Because", "Since", "Given that"]),
    r'\bIn the realm of\b': lambda: random.choice(["In", "When it comes to", "Within"]),
    r'\bIt is essential to\b': lambda: random.choice(["You need to", "It's key to", "The important thing is to"]),
    r'\bIn today\'s world\b': lambda: random.choice(["These days", "Right now", "Nowadays"]),
    r'\bIn today\'s society\b': lambda: random.choice(["These days", "Nowadays", "In the world we live in now"]),
    r'\bHas the potential to\b': lambda: random.choice(["Could", "Might", "Can"]),
    r'\bA wide range of\b': lambda: random.choice(["All sorts of", "Many different", "A mix of", "Various"]),
    r'\bPlays a crucial role\b': lambda: random.choice(["matters a lot", "is really important", "makes a big difference"]),
    r'\bIt is evident that\b': lambda: random.choice(["Clearly,", "You can see that", "It's pretty clear that"]),
    r'\bServes as a\b': lambda: random.choice(["works as a", "acts as a", "functions as a", "is basically a"]),
}

# Overused AI words → more natural alternatives
WORD_SWAPS = {
    r'\butilize\b': lambda: random.choice(["use", "rely on", "work with"]),
    r'\butilized\b': lambda: random.choice(["used", "relied on", "worked with"]),
    r'\butilizing\b': lambda: random.choice(["using", "relying on", "working with"]),
    r'\butilization\b': lambda: random.choice(["use", "usage"]),
    r'\bimplement\b': lambda: random.choice(["set up", "roll out", "put in place", "build"]),
    r'\bimplemented\b': lambda: random.choice(["set up", "rolled out", "put in place", "built"]),
    r'\bimplementation\b': lambda: random.choice(["setup", "rollout", "execution"]),
    r'\bleverage\b': lambda: random.choice(["use", "take advantage of", "tap into"]),
    r'\bleveraging\b': lambda: random.choice(["using", "taking advantage of", "tapping into"]),
    r'\bfacilitate\b': lambda: random.choice(["help with", "make easier", "support"]),
    r'\bfacilitated\b': lambda: random.choice(["helped with", "made easier", "supported"]),
    r'\benhance\b': lambda: random.choice(["improve", "boost", "strengthen"]),
    r'\benhanced\b': lambda: random.choice(["improved", "boosted", "strengthened"]),
    r'\boptimize\b': lambda: random.choice(["improve", "fine-tune", "streamline"]),
    r'\boptimized\b': lambda: random.choice(["improved", "fine-tuned", "streamlined"]),
    r'\brobust\b': lambda: random.choice(["solid", "strong", "reliable"]),
    r'\bseamless\b': lambda: random.choice(["smooth", "effortless", "clean"]),
    r'\bseamlessly\b': lambda: random.choice(["smoothly", "without friction", "cleanly"]),
    r'\bcomprehensive\b': lambda: random.choice(["thorough", "full", "complete", "in-depth"]),
    r'\binnovative\b': lambda: random.choice(["creative", "fresh", "new", "original"]),
    r'\bgroundbreaking\b': lambda: random.choice(["major", "game-changing", "huge"]),
    r'\bcutting-edge\b': lambda: random.choice(["latest", "modern", "advanced", "state-of-the-art"]),
    r'\bparadigm\b': lambda: random.choice(["model", "framework", "approach"]),
    r'\bparadigm shift\b': lambda: random.choice(["major change", "big shift", "turning point"]),
    r'\bsynergy\b': lambda: random.choice(["collaboration", "combined effort", "teamwork"]),
    r'\bholistic\b': lambda: random.choice(["overall", "complete", "big-picture"]),
    r'\bpivotal\b': lambda: random.choice(["key", "critical", "turning-point"]),
    r'\bmultifaceted\b': lambda: random.choice(["complex", "layered", "many-sided"]),
    r'\bdelve\b': lambda: random.choice(["dig into", "look at", "explore", "get into"]),
    r'\bdelving\b': lambda: random.choice(["digging into", "looking at", "exploring"]),
    r'\bmeticulous\b': lambda: random.choice(["careful", "detailed", "thorough"]),
    r'\bmeticulously\b': lambda: random.choice(["carefully", "with care", "thoroughly"]),
    r'\bplethora\b': lambda: random.choice(["ton", "lot", "bunch", "plenty"]),
    r'\bmyriad\b': lambda: random.choice(["many", "countless", "all kinds of"]),
    r'\blandscape\b': lambda: random.choice(["space", "scene", "world", "field"]),
    r'\bfundamentally\b': lambda: random.choice(["at its core", "basically", "at a deep level"]),
    r'\bunprecedented\b': lambda: random.choice(["never-before-seen", "unheard-of", "first-of-its-kind", "remarkable"]),
    r'\btransformative\b': lambda: random.choice(["game-changing", "major", "powerful"]),
    r'\brealm\b': lambda: random.choice(["area", "space", "world", "domain"]),
    r'\bcommence\b': lambda: random.choice(["start", "begin", "kick off"]),
    r'\bcommenced\b': lambda: random.choice(["started", "began", "kicked off"]),
    r'\bterminate\b': lambda: random.choice(["end", "stop", "wrap up"]),
    r'\bascertain\b': lambda: random.choice(["find out", "figure out", "determine"]),
    r'\bendeavor\b': lambda: random.choice(["effort", "attempt", "try"]),
    r'\bsubsequently\b': lambda: random.choice(["after that", "then", "later", "next"]),
    r'\bnotwithstanding\b': lambda: random.choice(["despite", "even with", "regardless of"]),
    r'\baforementioned\b': lambda: random.choice(["mentioned earlier", "noted above", "previous"]),
    r'\bhenceforth\b': lambda: random.choice(["from now on", "going forward", "from here on"]),
}

# Human-style hedges and asides to inject
HEDGES = [
    " — at least from what I've seen —",
    " (more or less)",
    ", which is kind of the point,",
    " — honestly —",
    ", if we're being real,",
    " (or something close to it)",
    ", give or take,",
    " — and this matters —",
]

INFORMALITIES = [
    "The thing is, ",
    "Honestly, ",
    "Look, ",
    "Here's the deal: ",
    "Let's be real — ",
    "Truth is, ",
    "The reality is pretty straightforward: ",
]

SENTENCE_STARTERS_CASUAL = [
    "And ",
    "But ",
    "So ",
    "Now, ",
    "Thing is, ",
]


def humanize_text(text):
    """Apply humanization transforms to AI-generated text."""
    # Step 1: Replace overused AI transitions
    for pattern, replacement_fn in TRANSITION_SWAPS.items():
        text = re.sub(pattern, lambda m: replacement_fn(), text, flags=re.IGNORECASE, count=1)

    # Step 2: Replace overused AI vocabulary
    for pattern, replacement_fn in WORD_SWAPS.items():
        # Only replace ~70% of matches to keep some natural variation
        def maybe_replace(m):
            if random.random() < 0.7:
                replacement = replacement_fn()
                # Preserve capitalization
                if m.group(0)[0].isupper():
                    return replacement[0].upper() + replacement[1:]
                return replacement
            return m.group(0)
        text = re.sub(pattern, maybe_replace, text, flags=re.IGNORECASE)

    # Step 3: Split into sentences for structural manipulation
    sentences = re.split(r'(?<=[.!?])\s+', text)

    if len(sentences) < 2:
        return text

    new_sentences = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue

        # Occasionally start with casual connector (15% chance, not first sentence)
        if i > 0 and i < len(sentences) - 1 and random.random() < 0.15:
            starter = random.choice(SENTENCE_STARTERS_CASUAL)
            # Lowercase the first letter of the existing sentence
            if sent and sent[0].isupper():
                sent = starter + sent[0].lower() + sent[1:]

        # Inject a hedge/aside into ~12% of longer sentences
        if len(sent.split()) > 12 and random.random() < 0.12:
            words = sent.split()
            insert_pos = len(words) // 2
            hedge = random.choice(HEDGES)
            words.insert(insert_pos, hedge)
            sent = ' '.join(words)

        # Add informality opener to ~8% of sentences (not first)
        if i > 1 and random.random() < 0.08 and not any(sent.startswith(s) for s in SENTENCE_STARTERS_CASUAL):
            informal = random.choice(INFORMALITIES)
            if sent and sent[0].isupper():
                sent = informal + sent[0].lower() + sent[1:]

        # Burstiness: occasionally split long sentences at commas
        if len(sent.split()) > 18 and random.random() < 0.3:
            comma_pos = sent.find(', ', len(sent) // 3)
            if comma_pos > 0:
                part1 = sent[:comma_pos] + '.'
                part2 = sent[comma_pos + 2:]
                if part2 and part2[0].islower():
                    part2 = part2[0].upper() + part2[1:]
                new_sentences.append(part1)
                sent = part2

        # Burstiness: occasionally merge short consecutive sentences
        if (len(new_sentences) > 0 and
            len(sent.split()) < 6 and
            len(new_sentences[-1].split()) < 8 and
            random.random() < 0.25):
            prev = new_sentences[-1].rstrip('.')
            sent_lower = sent[0].lower() + sent[1:] if sent else sent
            new_sentences[-1] = prev + ' — ' + sent_lower
            continue

        new_sentences.append(sent)

    # Step 4: Vary paragraph structure
    # Join and re-split by paragraphs
    result = ' '.join(new_sentences)

    # Step 5: Clean up artifacts
    result = re.sub(r'\s{2,}', ' ', result)
    result = re.sub(r'\s([.,!?])', r'\1', result)
    result = re.sub(r'\.{2,}', '.', result)

    # Step 6: Randomly add a contraction or two
    contraction_map = {
        "It is ": ["It's ", 0.6],
        "it is ": ["it's ", 0.6],
        "That is ": ["That's ", 0.5],
        "that is ": ["that's ", 0.5],
        "There is ": ["There's ", 0.5],
        "there is ": ["there's ", 0.5],
        "does not ": ["doesn't ", 0.6],
        "do not ": ["don't ", 0.6],
        "can not ": ["can't ", 0.7],
        "cannot ": ["can't ", 0.7],
        "will not ": ["won't ", 0.6],
        "should not ": ["shouldn't ", 0.5],
        "would not ": ["wouldn't ", 0.5],
        "could not ": ["couldn't ", 0.5],
        "is not ": ["isn't ", 0.6],
        "are not ": ["aren't ", 0.6],
        "was not ": ["wasn't ", 0.5],
        "were not ": ["weren't ", 0.5],
        "have not ": ["haven't ", 0.5],
        "has not ": ["hasn't ", 0.5],
        "had not ": ["hadn't ", 0.5],
        "we have ": ["we've ", 0.4],
        "they have ": ["they've ", 0.4],
        "I have ": ["I've ", 0.5],
        "I am ": ["I'm ", 0.6],
        "we are ": ["we're ", 0.5],
        "they are ": ["they're ", 0.5],
        "you are ": ["you're ", 0.5],
    }
    for formal, (contraction, prob) in contraction_map.items():
        if random.random() < prob:
            result = result.replace(formal, contraction, 1)

    return result.strip()


# ─── Detector Backends ────────────────────────────────────────────────────────

def check_zerogpt(text):
    """Check text against ZeroGPT's API."""
    try:
        url = "https://api.zerogpt.com/api/detect/detectText"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Origin": "https://www.zerogpt.com",
            "Referer": "https://www.zerogpt.com/",
        }
        payload = {"input_text": text}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json()

        if data.get("success") or data.get("is_success"):
            result = data.get("data", data)
            ai_pct = result.get("fake_percentage", result.get("fakePercentage", None))
            if ai_pct is None:
                ai_pct = result.get("isHuman", 0)
                ai_pct = 100 - float(ai_pct) if ai_pct else 0

            return {
                "detector": "ZeroGPT",
                "status": "success",
                "ai_percentage": round(float(ai_pct), 1),
                "human_percentage": round(100 - float(ai_pct), 1),
                "verdict": _verdict(float(ai_pct)),
                "details": result.get("feedback", ""),
            }
        else:
            return _manual_result("ZeroGPT", "https://www.zerogpt.com/",
                                  data.get("message", "API limit reached"))
    except Exception as e:
        return _manual_result("ZeroGPT", "https://www.zerogpt.com/", str(e))


def _get_sapling_key():
    """Dynamically fetch the Sapling API key from their website."""
    try:
        resp = requests.get(
            "https://sapling.ai/ai-content-detector",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/122.0.0.0 Safari/537.36",
            },
            timeout=15,
        )
        # The key is embedded in the page JS like: key: 'eyJ...'
        match = re.search(r"key:\s*'(eyJ[^']+)'", resp.text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


# Cache the sapling key so we don't fetch it every time
_sapling_key_cache = {"key": None, "fetched_at": 0}


def check_sapling(text):
    """Check text against Sapling.ai's detector with dynamic key."""
    try:
        # Refresh key if older than 30 minutes
        now = time.time()
        if not _sapling_key_cache["key"] or now - _sapling_key_cache["fetched_at"] > 1800:
            new_key = _get_sapling_key()
            if new_key:
                _sapling_key_cache["key"] = new_key
                _sapling_key_cache["fetched_at"] = now

        api_key = _sapling_key_cache["key"]
        if not api_key:
            return _manual_result("Sapling AI", "https://sapling.ai/ai-content-detector",
                                  "Could not fetch API key. Check manually.")

        url = "https://api.sapling.ai/api/v1/aidetect"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36",
            "Origin": "https://sapling.ai",
            "Referer": "https://sapling.ai/ai-content-detector",
        }
        payload = {"key": api_key, "text": text}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)

        if resp.status_code != 200:
            return _manual_result("Sapling AI", "https://sapling.ai/ai-content-detector",
                                  f"HTTP {resp.status_code}")

        data = resp.json()
        if "msg" in data and "Invalid" in str(data["msg"]):
            # Key expired, clear cache and fallback
            _sapling_key_cache["key"] = None
            return _manual_result("Sapling AI", "https://sapling.ai/ai-content-detector",
                                  "Key expired. Check manually.")

        score = data.get("score", 0)
        ai_pct = round(float(score) * 100, 1)

        # Get per-sentence scores for details
        sentence_scores = data.get("sentence_scores", [])
        detail_parts = [f"Overall: {score:.3f}"]
        for ss in sentence_scores[:3]:
            s_score = ss.get("score", 0)
            s_text = ss.get("sentence", "")[:60]
            detail_parts.append(f"  \"{s_text}...\" → {s_score:.2f}")

        return {
            "detector": "Sapling AI",
            "status": "success",
            "ai_percentage": ai_pct,
            "human_percentage": round(100 - ai_pct, 1),
            "verdict": _verdict(ai_pct),
            "details": " | ".join(detail_parts[:2]),
        }
    except Exception as e:
        return _manual_result("Sapling AI", "https://sapling.ai/ai-content-detector", str(e))


def check_gptzero(text):
    """GPTZero - requires paid API, manual check."""
    return _manual_result("GPTZero", "https://gptzero.me/",
                          "Requires login. Open & paste to check.")


def check_quillbot(text):
    """Quillbot AI detector - no free API, manual check."""
    return _manual_result("Quillbot", "https://www.quillbot.com/ai-content-detector",
                          "Open & paste to check.")


def check_copyleaks(text):
    """Copyleaks detector - needs auth, manual check."""
    return _manual_result("Copyleaks", "https://copyleaks.com/ai-content-detector",
                          "Requires login. Open & paste to check.")


def check_scribbr(text):
    """Scribbr AI detector - Cloudflare protected, manual check."""
    return _manual_result("Scribbr", "https://www.scribbr.com/ai-detector/",
                          "Open & paste to check.")


# ─── Local HuggingFace model pipelines (lazy-loaded) ────────────────────────
_roberta_openai_pipe = None
_hc3_chatgpt_pipe = None


def _get_roberta_openai_pipe():
    """Lazy-load the RoBERTa OpenAI GPT-2 detector pipeline."""
    global _roberta_openai_pipe
    if _roberta_openai_pipe is None:
        from transformers import pipeline as hf_pipeline
        _roberta_openai_pipe = hf_pipeline(
            "text-classification",
            model="openai-community/roberta-base-openai-detector",
            top_k=None,
            device=-1,  # CPU
        )
    return _roberta_openai_pipe


def _get_hc3_chatgpt_pipe():
    """Lazy-load the HC3 ChatGPT detector pipeline."""
    global _hc3_chatgpt_pipe
    if _hc3_chatgpt_pipe is None:
        from transformers import pipeline as hf_pipeline
        _hc3_chatgpt_pipe = hf_pipeline(
            "text-classification",
            model="Hello-SimpleAI/chatgpt-detector-roberta",
            top_k=None,
            device=-1,  # CPU
        )
    return _hc3_chatgpt_pipe


def check_roberta_openai(text):
    """RoBERTa OpenAI GPT detector — runs locally via transformers."""
    try:
        pipe = _get_roberta_openai_pipe()
        raw = pipe(text[:1500])
        # Pipeline returns [[{label, score}, ...]] for single input
        results = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
        fake_score = 0
        for item in (results if isinstance(results, list) else []):
            if item.get("label") in ("Fake", "LABEL_1"):
                fake_score = item.get("score", 0)
        ai_pct = round(float(fake_score) * 100, 1)
        return {
            "detector": "RoBERTa OpenAI",
            "status": "success",
            "ai_percentage": ai_pct,
            "human_percentage": round(100 - ai_pct, 1),
            "verdict": _verdict(ai_pct),
            "details": "GPT-2 output detector (RoBERTa-base) — local",
        }
    except Exception as e:
        return {
            "detector": "RoBERTa OpenAI",
            "status": "error",
            "message": str(e),
        }


def check_hc3_chatgpt(text):
    """HC3 ChatGPT detector — runs locally via transformers."""
    try:
        pipe = _get_hc3_chatgpt_pipe()
        raw = pipe(text[:1500])
        # Pipeline returns [[{label, score}, ...]] for single input
        results = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
        chatgpt_score = 0
        for item in (results if isinstance(results, list) else []):
            if item.get("label") in ("ChatGPT", "LABEL_1"):
                chatgpt_score = item.get("score", 0)
        ai_pct = round(float(chatgpt_score) * 100, 1)
        return {
            "detector": "HC3 ChatGPT",
            "status": "success",
            "ai_percentage": ai_pct,
            "human_percentage": round(100 - ai_pct, 1),
            "verdict": _verdict(ai_pct),
            "details": "ChatGPT detector trained on HC3 dataset — local",
        }
    except Exception as e:
        return {
            "detector": "HC3 ChatGPT",
            "status": "error",
            "message": str(e),
        }


def _manual_result(name, url, msg):
    return {
        "detector": name,
        "status": "manual",
        "message": msg,
        "url": url,
    }


def _verdict(ai_pct):
    if ai_pct <= 15:
        return "Human Written"
    elif ai_pct <= 40:
        return "Mostly Human"
    elif ai_pct <= 60:
        return "Mixed"
    elif ai_pct <= 85:
        return "Mostly AI"
    else:
        return "AI Generated"


def strip_suspicious_chars(text):
    """Remove characters and patterns commonly flagged as AI-generated."""
    # Em dashes → commas or regular dashes
    text = re.sub(r'\s*—\s*', ', ', text)
    # En dashes → regular dashes
    text = text.replace('–', '-')
    # Curly/smart quotes → straight quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    # Ellipsis character → three dots
    text = text.replace('\u2026', '...')
    # Bullet points → dashes
    text = text.replace('\u2022', '-')
    # Non-breaking spaces → regular spaces
    text = text.replace('\u00a0', ' ')
    # Double spaces
    text = re.sub(r'  +', ' ', text)
    # Fix any double commas from em dash replacement
    text = re.sub(r',\s*,', ',', text)
    # Semicolons (AI overuses them) → periods with new sentence
    def semicolon_to_period(m):
        after = m.group(1).strip()
        if after and after[0].islower():
            after = after[0].upper() + after[1:]
        return '. ' + after
    text = re.sub(r';\s*(.)', semicolon_to_period, text)
    # Colons mid-sentence (AI pattern) → period when followed by uppercase
    # Skip if preceded by common colon words
    def replace_colon(m):
        before = m.string[max(0, m.start()-15):m.start()].lower()
        keep_words = ['example', 'following', 'include', 'including', 'such as', 'namely', 'i.e', 'e.g']
        if any(before.endswith(w) for w in keep_words):
            return m.group(0)
        return '. '
    text = re.sub(r':\s*(?=[A-Z])', replace_colon, text)
    return text.strip()


# ─── Plagiarism Search ────────────────────────────────────────────────────────

def _search_web(phrase):
    """Search for exact phrase matches online via DuckDuckGo."""
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": f'"{phrase[:100]}"'},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/122.0.0.0 Safari/537.36",
            },
            timeout=15,
        )
        matches = []
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        ):
            href, title = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            actual = re.search(r'uddg=([^&]+)', href)
            if actual:
                href = urllib.parse.unquote(actual.group(1))
            if href.startswith('http') and 'duckduckgo' not in href:
                matches.append({"url": href, "title": title or href})
                if len(matches) >= 3:
                    break
        return matches
    except Exception:
        return []


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/humanize", methods=["POST"])
def humanize():
    """Humanize the provided text."""
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Run humanization multiple passes for stronger effect
    passes = data.get("passes", 1)
    result = text
    for _ in range(min(passes, 3)):
        result = humanize_text(result)

    return jsonify({
        "original": text,
        "humanized": result,
        "original_word_count": len(text.split()),
        "humanized_word_count": len(result.split()),
    })


@app.route("/api/humanize-until", methods=["POST"])
def humanize_until():
    """Iteratively humanize text until it hits a target AI % threshold.
    Cross-references ZeroGPT AND Sapling — uses the MAX (worst) score."""
    data = request.get_json()
    text = data.get("text", "").strip()
    target = float(data.get("target", 0))
    max_iterations = int(data.get("max_iterations", 999))
    strip_chars = bool(data.get("strip_suspicious", False))

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) < 50:
        return jsonify({"error": "Text too short. Need at least 50 characters."}), 400

    iterations = []
    current_text = text
    best_text = text
    best_ai_pct = 100.0
    best_iteration = 0
    stagnant_rounds = 0          # count iterations with no improvement
    stagnation_limit = 15        # stop after this many rounds without progress
    consecutive_errors = 0       # count consecutive total-failure iterations
    stop_reason = None

    for i in range(max_iterations):
        # Humanize (always 2 passes for consistent quality)
        for _ in range(2):
            current_text = humanize_text(current_text)

        # Strip suspicious AI characters if requested
        if strip_chars:
            current_text = strip_suspicious_chars(current_text)

        # Cross-reference BOTH detectors concurrently
        zerogpt_result = {"status": "error"}
        sapling_result = {"status": "error"}
        threads = []

        def run_zero():
            nonlocal zerogpt_result
            zerogpt_result = check_zerogpt(current_text)

        def run_sapling():
            nonlocal sapling_result
            sapling_result = check_sapling(current_text)

        t1 = threading.Thread(target=run_zero)
        t2 = threading.Thread(target=run_sapling)
        threads = [t1, t2]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=35)

        # Get scores from both, use AVERAGE for target check
        z_pct = zerogpt_result.get("ai_percentage", 100.0) if zerogpt_result["status"] == "success" else None
        s_pct = sapling_result.get("ai_percentage", 100.0) if sapling_result["status"] == "success" else None

        scores = [p for p in [z_pct, s_pct] if p is not None]
        avg_pct = round(sum(scores) / len(scores), 1) if scores else 100.0
        max_pct = max(scores) if scores else 100.0

        # Track consecutive detector failures
        if not scores:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                stop_reason = "detectors_failed"
                break
        else:
            consecutive_errors = 0

        iterations.append({
            "iteration": i + 1,
            "ai_percentage": avg_pct,
            "max_percentage": max_pct,
            "zerogpt": round(z_pct, 1) if z_pct is not None else None,
            "sapling": round(s_pct, 1) if s_pct is not None else None,
            "verdict": _verdict(avg_pct),
            "word_count": len(current_text.split()),
            "text_snapshot": current_text,
        })

        # Track best result (lowest AVERAGE ai%)
        if avg_pct < best_ai_pct:
            best_ai_pct = avg_pct
            best_text = current_text
            best_iteration = i + 1
            stagnant_rounds = 0      # reset — we improved
        else:
            stagnant_rounds += 1

        # Check if we hit the target (average of both detectors)
        if avg_pct <= target:
            stop_reason = "target_reached"
            break

        # Stop if no improvement for too long (text won't get better)
        if stagnant_rounds >= stagnation_limit:
            stop_reason = "stagnated"
            break

    # Strip text snapshots from response (too large), keep best
    clean_iterations = []
    for it in iterations:
        clean_it = {k: v for k, v in it.items() if k != "text_snapshot"}
        clean_it["is_best"] = it["iteration"] == best_iteration
        clean_iterations.append(clean_it)

    return jsonify({
        "original": text,
        "humanized": best_text,
        "original_word_count": len(text.split()),
        "humanized_word_count": len(best_text.split()),
        "iterations": clean_iterations,
        "final_ai_percentage": round(best_ai_pct, 1),
        "target_reached": best_ai_pct <= target,
        "total_iterations": len(iterations),
        "best_iteration": best_iteration,
        "stop_reason": stop_reason or ("target_reached" if best_ai_pct <= target else "max_iterations"),
    })


@app.route("/api/check", methods=["POST"])
def check_all():
    """Run text through all available detectors concurrently."""
    data = request.get_json()
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) < 50:
        return jsonify({"error": "Text too short. Need at least 50 characters."}), 400

    results = []
    threads = []
    lock = threading.Lock()

    detectors = [
        check_zerogpt,
        check_sapling,
        check_roberta_openai,
        check_hc3_chatgpt,
        check_gptzero,
        check_quillbot,
        check_copyleaks,
        check_scribbr,
    ]

    def run_detector(fn):
        result = fn(text)
        with lock:
            results.append(result)

    for det in detectors:
        t = threading.Thread(target=run_detector, args=(det,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=35)

    order = {"success": 0, "manual": 1, "error": 2}
    results.sort(key=lambda r: order.get(r.get("status"), 3))

    successful = [r for r in results if r["status"] == "success"]
    avg_ai = 0
    if successful:
        avg_ai = round(sum(r["ai_percentage"] for r in successful) / len(successful), 1)

    return jsonify({
        "results": results,
        "summary": {
            "total_checked": len(successful),
            "total_detectors": len(results),
            "avg_ai_percentage": avg_ai,
            "avg_human_percentage": round(100 - avg_ai, 1),
            "overall_verdict": _verdict(avg_ai),
        }
    })


@app.route("/api/plagiarism", methods=["POST"])
def check_plagiarism():
    """Check text for plagiarism by searching for exact phrase matches."""
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) < 50:
        return jsonify({"error": "Text too short. Need at least 50 characters."}), 400

    # Split into sentences and group into 2-sentence chunks
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    i = 0
    while i < len(sentences):
        chunk = sentences[i].strip()
        if i + 1 < len(sentences):
            chunk += ' ' + sentences[i + 1].strip()
            i += 2
        else:
            i += 1
        if len(chunk) > 30:
            chunks.append(chunk)

    # Search each chunk concurrently
    results = []
    lock = threading.Lock()

    def check_chunk(chunk):
        matches = _search_web(chunk)
        with lock:
            results.append({
                "text": chunk[:120] + ("..." if len(chunk) > 120 else ""),
                "flagged": len(matches) > 0,
                "matches": matches,
            })

    threads = []
    for chunk in chunks[:10]:
        t = threading.Thread(target=check_chunk, args=(chunk,))
        threads.append(t)
        t.start()
        time.sleep(0.3)  # Stagger to avoid rate limiting

    for t in threads:
        t.join(timeout=20)

    total = len(results)
    flagged = sum(1 for r in results if r["flagged"])
    plag_pct = round((flagged / total) * 100, 1) if total > 0 else 0

    return jsonify({
        "chunks": results,
        "summary": {
            "total_chunks": total,
            "flagged_chunks": flagged,
            "plagiarism_percentage": plag_pct,
            "verdict": "No Plagiarism Detected" if plag_pct == 0
                       else "Some Matches Found" if plag_pct < 50
                       else "Significant Matches Found",
        }
    })


# ─── HTML Template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Humanizer + Detector Panel</title>
<style>
  :root {
    --bg: #08080d;
    --surface: #111118;
    --surface2: #191924;
    --surface3: #22222f;
    --border: #2a2a3a;
    --border-bright: #3a3a55;
    --text: #e4e4ef;
    --text-dim: #7878a0;
    --accent: #6c5ce7;
    --accent2: #a29bfe;
    --accent-glow: rgba(108, 92, 231, 0.25);
    --green: #00b894;
    --green-dim: rgba(0, 184, 148, 0.15);
    --red: #e17055;
    --red-dim: rgba(225, 112, 85, 0.15);
    --yellow: #fdcb6e;
    --yellow-dim: rgba(253, 203, 110, 0.15);
    --cyan: #74b9ff;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* ─── Layout ─── */
  .app { max-width: 1400px; margin: 0 auto; padding: 24px 20px; }
  .header { text-align: center; margin-bottom: 28px; }
  .header h1 {
    font-size: 1.8rem; font-weight: 800;
    background: linear-gradient(135deg, #6c5ce7, #a29bfe, #74b9ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .header p { color: var(--text-dim); font-size: 0.9rem; margin-top: 4px; }

  /* ─── Tabs ─── */
  .tabs {
    display: flex; gap: 4px;
    background: var(--surface); border-radius: 12px;
    padding: 4px; margin-bottom: 20px;
    border: 1px solid var(--border);
  }
  .tab {
    flex: 1; padding: 12px; text-align: center;
    border-radius: 10px; cursor: pointer;
    font-weight: 600; font-size: 0.95rem;
    color: var(--text-dim); transition: all 0.3s;
    border: none; background: none;
  }
  .tab:hover { color: var(--text); }
  .tab.active {
    background: var(--accent);
    color: white;
    box-shadow: 0 2px 12px var(--accent-glow);
  }

  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* ─── Shared ─── */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 22px; margin-bottom: 18px;
  }
  textarea {
    width: 100%; min-height: 180px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 10px; color: var(--text);
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.88rem; padding: 14px; resize: vertical;
    outline: none; transition: border-color 0.3s; line-height: 1.65;
  }
  textarea:focus { border-color: var(--accent); box-shadow: 0 0 15px var(--accent-glow); }
  textarea::placeholder { color: var(--text-dim); }

  .controls { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; align-items: center; }

  .btn {
    padding: 10px 22px; border: none; border-radius: 9px;
    font-size: 0.9rem; font-weight: 600; cursor: pointer;
    transition: all 0.25s; display: inline-flex; align-items: center; gap: 7px;
  }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none !important; }

  .btn-primary {
    background: linear-gradient(135deg, #6c5ce7, #a29bfe); color: white;
    box-shadow: 0 3px 12px var(--accent-glow);
  }
  .btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 5px 20px var(--accent-glow); }

  .btn-green {
    background: linear-gradient(135deg, #00b894, #55efc4); color: #111;
    box-shadow: 0 3px 12px rgba(0,184,148,0.25);
  }
  .btn-green:hover:not(:disabled) { transform: translateY(-1px); }

  .btn-ghost {
    background: var(--surface2); color: var(--text-dim);
    border: 1px solid var(--border); padding: 10px 16px;
  }
  .btn-ghost:hover { color: var(--text); border-color: var(--accent); }

  .meta { color: var(--text-dim); font-size: 0.82rem; margin-left: auto; font-family: monospace; }

  /* ─── Humanizer ─── */
  .split-panel { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .panel-label { font-size: 0.8rem; color: var(--text-dim); margin-bottom: 8px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
  /* strength selector removed — using AI limit only */

  .diff-highlight {
    background: rgba(108, 92, 231, 0.08);
    border-left: 3px solid var(--accent);
    padding: 12px 16px;
    border-radius: 0 10px 10px 0;
    margin-top: 12px;
    font-size: 0.85rem;
    color: var(--text-dim);
    line-height: 1.5;
  }

  /* ─── Progress ─── */
  .progress { width: 100%; height: 3px; background: var(--surface2); border-radius: 2px; overflow: hidden; display: none; margin-bottom: 18px; }
  .progress.active { display: block; }
  .progress .fill { height: 100%; width: 40%; background: linear-gradient(90deg, #6c5ce7, #74b9ff); border-radius: 2px; animation: slide 1.8s ease-in-out infinite; }
  @keyframes slide { 0%{transform:translateX(-100%)} 100%{transform:translateX(350%)} }

  /* ─── Summary ─── */
  .summary { display: none; }
  .summary.visible { display: block; }
  .summary-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  .verdict-badge {
    padding: 5px 14px; border-radius: 16px;
    font-weight: 700; font-size: 0.88rem;
  }
  .v-human { background: var(--green-dim); color: var(--green); border: 1px solid rgba(0,184,148,0.3); }
  .v-mixed { background: var(--yellow-dim); color: var(--yellow); border: 1px solid rgba(253,203,110,0.3); }
  .v-ai { background: var(--red-dim); color: var(--red); border: 1px solid rgba(225,112,85,0.3); }

  .meter-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .meter-label { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 6px; }
  .meter-label .pct { font-weight: 700; font-family: monospace; }
  .meter-track { height: 8px; background: var(--surface2); border-radius: 4px; overflow: hidden; }
  .meter-fill { height: 100%; border-radius: 4px; transition: width 0.8s ease; }
  .meter-fill.human { background: linear-gradient(90deg, #00b894, #55efc4); }
  .meter-fill.ai { background: linear-gradient(90deg, #e17055, #fab1a0); }

  /* ─── Results Grid ─── */
  .results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; margin-bottom: 18px; }
  .result-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px; transition: all 0.3s; }
  .result-card:hover { border-color: var(--border-bright); }
  .rh { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .rname { font-weight: 600; font-size: 0.98rem; }
  .badge { font-size: 0.7rem; padding: 3px 9px; border-radius: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }
  .b-ok { background: var(--green-dim); color: var(--green); }
  .b-err { background: var(--red-dim); color: var(--red); }
  .b-man { background: var(--yellow-dim); color: var(--yellow); }
  .b-load { background: rgba(108,92,231,0.15); color: var(--accent); }
  .score-line { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px; }
  .score-line .l { color: var(--text-dim); }
  .score-line .v { font-weight: 600; font-family: monospace; }
  .rbar { height: 6px; background: var(--surface2); border-radius: 3px; overflow: hidden; margin: 8px 0; }
  .rbar-fill { height: 100%; border-radius: 3px; transition: width 0.6s; }
  .rverdict { font-size: 0.8rem; color: var(--text-dim); font-style: italic; }
  .rmsg { color: var(--text-dim); font-size: 0.82rem; margin-top: 6px; line-height: 1.4; }
  .rlink {
    display: inline-block; margin-top: 8px; padding: 6px 14px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 7px; color: var(--accent); text-decoration: none;
    font-size: 0.82rem; transition: all 0.3s;
  }
  .rlink:hover { border-color: var(--accent); }

  /* ─── Manual Links ─── */
  .manual-section { margin-top: 8px; }
  .manual-section h4 { font-size: 0.9rem; color: var(--text-dim); margin-bottom: 12px; font-weight: 500; }
  .manual-grid { display: flex; flex-wrap: wrap; gap: 8px; }
  .mbtn {
    padding: 8px 16px; background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); text-decoration: none;
    font-size: 0.85rem; cursor: pointer; transition: all 0.3s;
  }
  .mbtn:hover { border-color: var(--accent); transform: translateY(-1px); box-shadow: 0 2px 10px var(--accent-glow); }

  /* ─── Spinner ─── */
  .spinner { width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ─── Toast ─── */
  .toast {
    position: fixed; bottom: 24px; right: 24px;
    background: var(--surface); border: 1px solid var(--accent);
    border-radius: 10px; padding: 12px 20px;
    color: var(--text); font-size: 0.88rem;
    box-shadow: 0 6px 24px rgba(0,0,0,0.3);
    transform: translateY(80px); opacity: 0;
    transition: all 0.35s; z-index: 999;
  }
  .toast.show { transform: translateY(0); opacity: 1; }

  /* ─── Target Input ─── */
  .target-group {
    display: flex; align-items: center; gap: 8px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 9px; padding: 6px 12px;
  }
  .target-group label {
    font-size: 0.8rem; color: var(--text-dim); font-weight: 600;
    white-space: nowrap;
  }
  .target-input {
    width: 52px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 0.9rem;
    padding: 4px 6px; text-align: center; outline: none;
    font-family: monospace; font-weight: 700;
  }
  .target-input:focus { border-color: var(--accent); }
  .target-group .unit { font-size: 0.8rem; color: var(--text-dim); }

  /* ─── Checkbox option ─── */
  .check-option {
    display: flex; align-items: center; gap: 6px; cursor: pointer;
    font-size: 0.82rem; color: var(--text-dim); font-weight: 600;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 9px; padding: 6px 12px; white-space: nowrap;
  }
  .check-option:hover { border-color: var(--accent); color: var(--text); }
  .check-option input[type="checkbox"] {
    accent-color: var(--accent); width: 15px; height: 15px; cursor: pointer;
  }

  /* ─── Iteration Log ─── */
  .iter-log {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; margin-bottom: 16px; display: none;
  }
  .iter-log.visible { display: block; }
  .iter-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 14px 16px; cursor: pointer; user-select: none;
  }
  .iter-header:hover { background: var(--surface2); border-radius: 12px; }
  .iter-header h4 { font-size: 0.9rem; color: var(--text-dim); margin: 0; }
  .iter-arrow {
    font-size: 1rem; color: var(--text-dim);
    transition: transform 0.2s;
    display: inline-block;
  }
  .iter-body { padding: 0 16px 14px; }
  .iter-body.collapsed { display: none; }
  .iter-row {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 0; border-bottom: 1px solid var(--border);
    font-size: 0.85rem;
  }
  .iter-row:last-child { border-bottom: none; }
  .iter-row.best { background: rgba(0,184,148,0.08); border-radius: 6px; padding: 6px 8px; margin: 0 -8px; }
  .iter-num { color: var(--text-dim); font-family: monospace; min-width: 24px; }
  .iter-scores { font-size: 0.75rem; color: var(--text-dim); min-width: 110px; font-family: monospace; }
  .iter-bar-wrap { flex: 1; height: 6px; background: var(--surface2); border-radius: 3px; overflow: hidden; }
  .iter-bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s; }
  .iter-pct { font-family: monospace; font-weight: 700; min-width: 45px; text-align: right; }
  .iter-check { font-size: 1rem; min-width: 20px; text-align: center; }

  /* ─── Plagiarism Results ─── */
  .plag-results { margin-bottom: 18px; }
  .plag-chunk {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px; margin-bottom: 10px;
  }
  .plag-chunk.flagged { border-left: 3px solid var(--red); }
  .plag-chunk.clean { border-left: 3px solid var(--green); }
  .plag-text { font-size: 0.88rem; color: var(--text); margin-bottom: 8px; line-height: 1.5; font-style: italic; }
  .plag-status { font-size: 0.78rem; font-weight: 600; }
  .plag-status.ok { color: var(--green); }
  .plag-status.warn { color: var(--red); }
  .plag-sources { margin-top: 6px; }
  .plag-source {
    font-size: 0.78rem; color: var(--cyan);
    display: block; margin-top: 3px;
    text-decoration: none; word-break: break-all;
  }
  .plag-source:hover { text-decoration: underline; }

  @media (max-width: 768px) {
    .split-panel { grid-template-columns: 1fr; }
    .results-grid { grid-template-columns: 1fr; }
    .meter-row { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<div class="app">
  <div class="header">
    <h1>⚡ AI Humanizer + Detector</h1>
    <p>Humanize your text, then verify it passes AI detection</p>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab active" onclick="switchTab('humanize')">✏️ Humanize</button>
    <button class="tab" onclick="switchTab('detect')">🔍 Detect</button>
    <button class="tab" onclick="switchTab('plagiarism')">📝 Plagiarism</button>
    <button class="tab" onclick="switchTab('workflow')">⚡ Full Workflow</button>
  </div>

  <!-- ═══ TAB 1: HUMANIZE ═══ -->
  <div class="tab-content active" id="tab-humanize">
    <div class="split-panel">
      <div>
        <div class="panel-label">📥 Original (AI-Generated)</div>
        <textarea id="hInput" placeholder="Paste your AI-generated text here..."></textarea>
        <div class="controls">
          <button class="btn btn-primary" onclick="doHumanizeUntil('hInput','hOutput','hIterLog','hMeta')">
            ✏️ Humanize
          </button>
          <button class="btn btn-ghost" onclick="document.getElementById('hInput').value=''">Clear</button>
          <div class="target-group">
            <label>AI Limit</label>
            <input type="number" class="target-input" id="hTarget" value="0" min="0" max="100">
            <span class="unit">%</span>
          </div>
          <label class="check-option" title="Remove em dashes, smart quotes, semicolons, and other AI-telltale characters">
            <input type="checkbox" id="hStrip" checked> <span>Clean AI chars</span>
          </label>
        </div>
      </div>
      <div>
        <div class="panel-label">📤 Humanized Output</div>
        <textarea id="hOutput" placeholder="Humanized text will appear here..." readonly></textarea>
        <div class="controls">
          <button class="btn btn-ghost" onclick="copyField('hOutput')">📋 Copy</button>
          <button class="btn btn-ghost" onclick="sendToDetect('hOutput')">🔍 Send to Detector →</button>
          <span class="meta" id="hMeta"></span>
        </div>
      </div>
    </div>
    <div class="iter-log" id="hIterLog">
      <div class="iter-header" onclick="toggleIterLog('hIterLog')"><h4>🔄 Iteration Log</h4><span class="iter-arrow" id="hIterArrow">▶</span></div>
      <div class="iter-body collapsed" id="hIterBody"><div class="iter-rows" id="hIterRows"></div></div>
    </div>
    <div class="diff-highlight" id="hDiff" style="display:none"></div>
  </div>

  <!-- ═══ TAB 2: DETECT ═══ -->
  <div class="tab-content" id="tab-detect">
    <div class="card">
      <textarea id="dInput" placeholder="Paste text to check against AI detectors...&#10;&#10;Min 50 characters."></textarea>
      <div class="controls">
        <button class="btn btn-primary" id="detectBtn" onclick="runDetection('dInput')">
          🔍 Check All Detectors
        </button>
        <button class="btn btn-ghost" onclick="document.getElementById('dInput').value=''">Clear</button>
        <button class="btn btn-ghost" onclick="copyField('dInput')">📋 Copy</button>
        <span class="meta" id="dMeta"></span>
      </div>
    </div>

    <div class="progress" id="detectProgress"><div class="fill"></div></div>
    <div class="summary card" id="detectSummary">
      <div class="summary-row">
        <h3 style="font-size:1.05rem">Aggregate Results</h3>
        <span class="verdict-badge" id="dVerdict"></span>
      </div>
      <div class="meter-row">
        <div>
          <div class="meter-label"><span>🧑 Human</span><span class="pct" id="dHumanPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill human" id="dHumanBar" style="width:0%"></div></div>
        </div>
        <div>
          <div class="meter-label"><span>🤖 AI</span><span class="pct" id="dAiPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill ai" id="dAiBar" style="width:0%"></div></div>
        </div>
      </div>
    </div>
    <div class="results-grid" id="detectResults"></div>

    <div class="manual-section card">
      <h4>🔗 Quick Manual Check — copies text & opens detector site</h4>
      <div class="manual-grid">
        <a class="mbtn" onclick="openManual('dInput','https://www.zerogpt.com/')">ZeroGPT ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://gptzero.me/')">GPTZero ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://www.quillbot.com/ai-content-detector')">Quillbot ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://copyleaks.com/ai-content-detector')">Copyleaks ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://www.scribbr.com/ai-detector/')">Scribbr ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://originality.ai/')">Originality.ai ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://sapling.ai/ai-content-detector')">Sapling AI ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://writer.com/ai-content-detector/')">Writer.com ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://contentdetector.ai/')">ContentDetector ↗</a>
        <a class="mbtn" onclick="openManual('dInput','https://undetectable.ai/')">Undetectable.ai ↗</a>
      </div>
    </div>
  </div>

  <!-- ═══ TAB 3: PLAGIARISM ═══ -->
  <div class="tab-content" id="tab-plagiarism">
    <div class="card">
      <textarea id="pInput" placeholder="Paste text to check for plagiarism...&#10;&#10;Searches for exact phrase matches online. Min 50 characters."></textarea>
      <div class="controls">
        <button class="btn btn-primary" id="plagBtn" onclick="runPlagiarism('pInput')">
          📝 Check Plagiarism
        </button>
        <button class="btn btn-ghost" onclick="document.getElementById('pInput').value=''">Clear</button>
        <button class="btn btn-ghost" onclick="copyField('pInput')">📋 Copy</button>
        <span class="meta" id="pMeta"></span>
      </div>
    </div>

    <div class="progress" id="plagProgress"><div class="fill"></div></div>
    <div class="summary card" id="plagSummary">
      <div class="summary-row">
        <h3 style="font-size:1.05rem">Plagiarism Results</h3>
        <span class="verdict-badge" id="pVerdict"></span>
      </div>
      <div class="meter-row">
        <div>
          <div class="meter-label"><span>✅ Original</span><span class="pct" id="pOrigPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill human" id="pOrigBar" style="width:0%"></div></div>
        </div>
        <div>
          <div class="meter-label"><span>⚠️ Flagged</span><span class="pct" id="pFlagPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill ai" id="pFlagBar" style="width:0%"></div></div>
        </div>
      </div>
    </div>
    <div id="plagResults" class="plag-results"></div>

    <div class="manual-section card">
      <h4>🔗 Manual Plagiarism Check — copies text & opens checker site</h4>
      <div class="manual-grid">
        <a class="mbtn" onclick="openManual('pInput','https://www.quetext.com/')">Quetext ↗</a>
        <a class="mbtn" onclick="openManual('pInput','https://www.grammarly.com/plagiarism-checker')">Grammarly ↗</a>
        <a class="mbtn" onclick="openManual('pInput','https://www.duplichecker.com/')">DupliChecker ↗</a>
        <a class="mbtn" onclick="openManual('pInput','https://smallseotools.com/plagiarism-checker/')">SmallSEOTools ↗</a>
        <a class="mbtn" onclick="openManual('pInput','https://plagiarismdetector.net/')">PlagiarismDetector ↗</a>
      </div>
    </div>
  </div>

  <!-- ═══ TAB 4: FULL WORKFLOW ═══ -->
  <div class="tab-content" id="tab-workflow">
    <div class="card">
      <div class="panel-label">📥 Paste AI Text → Humanize → Detect → Plagiarism (one click)</div>
      <textarea id="wInput" placeholder="Paste your AI-generated text here...&#10;This will humanize, detect AI, and check plagiarism automatically."></textarea>
      <div class="controls">
        <button class="btn btn-green" id="workflowBtn" onclick="runWorkflow()">
          ⚡ Humanize & Detect & Plagiarism
        </button>
        <button class="btn btn-ghost" onclick="document.getElementById('wInput').value=''">Clear</button>
        <div class="target-group">
          <label>AI Limit</label>
          <input type="number" class="target-input" id="wTarget" value="0" min="0" max="100">
          <span class="unit">%</span>
        </div>
        <label class="check-option" title="Remove em dashes, smart quotes, semicolons, and other AI-telltale characters">
          <input type="checkbox" id="wStrip" checked> <span>Clean AI chars</span>
        </label>
      </div>
    </div>

    <div class="progress" id="wfProgress"><div class="fill"></div></div>
    <div class="iter-log" id="wIterLog">
      <div class="iter-header" onclick="toggleIterLog('wIterLog')"><h4>🔄 Iteration Log</h4><span class="iter-arrow" id="wIterArrow">▶</span></div>
      <div class="iter-body collapsed" id="wIterBody"><div class="iter-rows" id="wIterRows"></div></div>
    </div>

    <div class="card" id="wfHumanizedCard" style="display:none">
      <div class="panel-label">📤 Humanized Result</div>
      <textarea id="wOutput" readonly style="min-height:120px"></textarea>
      <div class="controls">
        <button class="btn btn-ghost" onclick="copyField('wOutput')">📋 Copy</button>
        <span class="meta" id="wMeta"></span>
      </div>
    </div>

    <div class="summary card" id="wfSummary">
      <div class="summary-row">
        <h3 style="font-size:1.05rem">Detection Results</h3>
        <span class="verdict-badge" id="wVerdict"></span>
      </div>
      <div class="meter-row">
        <div>
          <div class="meter-label"><span>🧑 Human</span><span class="pct" id="wHumanPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill human" id="wHumanBar" style="width:0%"></div></div>
        </div>
        <div>
          <div class="meter-label"><span>🤖 AI</span><span class="pct" id="wAiPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill ai" id="wAiBar" style="width:0%"></div></div>
        </div>
      </div>
    </div>
    <div class="results-grid" id="wfResults"></div>

    <div class="summary card" id="wfPlagSummary">
      <div class="summary-row">
        <h3 style="font-size:1.05rem">Plagiarism Results</h3>
        <span class="verdict-badge" id="wpVerdict"></span>
      </div>
      <div class="meter-row">
        <div>
          <div class="meter-label"><span>✅ Original</span><span class="pct" id="wpOrigPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill human" id="wpOrigBar" style="width:0%"></div></div>
        </div>
        <div>
          <div class="meter-label"><span>⚠️ Flagged</span><span class="pct" id="wpFlagPct">0%</span></div>
          <div class="meter-track"><div class="meter-fill ai" id="wpFlagBar" style="width:0%"></div></div>
        </div>
      </div>
    </div>
    <div id="wfPlagResults" class="plag-results"></div>

    <div class="manual-section card">
      <h4>🔗 Quick Manual Check — copies humanized text & opens detector site</h4>
      <div class="manual-grid">
        <a class="mbtn" onclick="openManual('wOutput','https://www.zerogpt.com/')">ZeroGPT ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://gptzero.me/')">GPTZero ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://www.quillbot.com/ai-content-detector')">Quillbot ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://copyleaks.com/ai-content-detector')">Copyleaks ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://www.scribbr.com/ai-detector/')">Scribbr ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://originality.ai/')">Originality.ai ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://sapling.ai/ai-content-detector')">Sapling AI ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://writer.com/ai-content-detector/')">Writer.com ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://contentdetector.ai/')">ContentDetector ↗</a>
        <a class="mbtn" onclick="openManual('wOutput','https://undetectable.ai/')">Undetectable.ai ↗</a>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ─── Tab switching ───
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

// ─── Helpers ───
function toast(msg, ms=2500) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), ms);
}

function copyField(id) {
  const text = document.getElementById(id).value.trim();
  if (!text) { toast('Nothing to copy'); return; }
  navigator.clipboard.writeText(text);
  toast('✓ Copied to clipboard');
}

function openManual(inputId, url) {
  const text = document.getElementById(inputId).value.trim();
  if (text) { navigator.clipboard.writeText(text); toast('✓ Text copied — paste on detector site'); }
  window.open(url, '_blank');
}

function toggleIterLog(logId) {
  const log = document.getElementById(logId);
  const body = log.querySelector('.iter-body');
  const arrow = log.querySelector('.iter-arrow');
  body.classList.toggle('collapsed');
  const isOpen = !body.classList.contains('collapsed');
  arrow.textContent = isOpen ? '▼' : '▶';
}

function sendToDetect(outputId) {
  const text = document.getElementById(outputId).value.trim();
  if (!text) { toast('Nothing to send'); return; }
  document.getElementById('dInput').value = text;
  // Switch to detect tab
  document.querySelectorAll('.tab')[1].click();
  toast('✓ Text loaded in detector');
}

function updateMeta(id, original, humanized) {
  const el = document.getElementById(id);
  const ow = original.trim().split(/\s+/).length;
  const hw = humanized.trim().split(/\s+/).length;
  el.textContent = ow + ' → ' + hw + ' words';
}

// Update word counts on input
document.querySelectorAll('textarea').forEach(ta => {
  ta.addEventListener('input', () => {
    const id = ta.id;
    const parentMeta = ta.closest('.card, .split-panel, .tab-content');
    if (!parentMeta) return;
    const metaEl = parentMeta.querySelector('.meta');
    if (metaEl && !ta.readOnly) {
      const w = ta.value.trim() ? ta.value.trim().split(/\s+/).length : 0;
      metaEl.textContent = w + ' words';
    }
  });
});

// ─── Iteration log rendering ───
function renderIterLog(logId, rowsId, iterations, target) {
  const log = document.getElementById(logId);
  const rows = document.getElementById(rowsId);
  log.classList.add('visible');
  // Start collapsed with arrow
  const body = log.querySelector('.iter-body');
  const arrow = log.querySelector('.iter-arrow');
  if (body) body.classList.add('collapsed');
  if (arrow) arrow.textContent = '▶';
  // Show iteration count in header
  const header = log.querySelector('.iter-header h4');
  if (header) header.textContent = '🔄 Iteration Log (' + iterations.length + ' iterations)';
  rows.innerHTML = '';
  iterations.forEach(it => {
    const pct = it.ai_percentage;
    const hit = pct <= target;
    const color = pct <= 15 ? 'var(--green)' : pct <= 50 ? 'var(--yellow)' : 'var(--red)';
    const row = document.createElement('div');
    row.className = 'iter-row' + (it.is_best ? ' best' : '');
    const zLabel = it.zerogpt !== null && it.zerogpt !== undefined ? 'Z:' + it.zerogpt + '%' : 'Z:—';
    const sLabel = it.sapling !== null && it.sapling !== undefined ? 'S:' + it.sapling + '%' : 'S:—';
    row.innerHTML = `
      <span class="iter-num">#${it.iteration}</span>
      <span class="iter-scores">${zLabel} ${sLabel}</span>
      <div class="iter-bar-wrap"><div class="iter-bar-fill" style="width:${pct}%;background:${color}"></div></div>
      <span class="iter-pct" style="color:${color}">${pct}%</span>
      <span class="iter-check">${it.is_best ? '⭐' : hit ? '✅' : '🔄'}</span>
    `;
    rows.appendChild(row);
  });
}

// ─── Humanize (with target loop) ───
async function doHumanizeUntil(inputId, outputId, iterLogId, metaId) {
  const input = document.getElementById(inputId);
  const output = document.getElementById(outputId);
  const text = input.value.trim();
  if (!text) { toast('Paste some text first'); return; }

  const targetEl = document.getElementById(inputId === 'hInput' ? 'hTarget' : 'wTarget');
  const target = parseFloat(targetEl.value) || 0;

  const btn = event.target.closest('.btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Humanizing...';

  // Reset iter log
  const logEl = document.getElementById(iterLogId);
  logEl.classList.remove('visible');

  const stripId = inputId === 'hInput' ? 'hStrip' : 'wStrip';
  const stripSuspicious = document.getElementById(stripId)?.checked || false;

  try {
    const resp = await fetch('/api/humanize-until', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text, target, strip_suspicious: stripSuspicious }),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error); return; }

    output.value = data.humanized;
    updateMeta(metaId, data.original, data.humanized);

    // Show iteration log
    const rowsId = iterLogId.replace('Log', 'Rows');
    renderIterLog(iterLogId, rowsId, data.iterations, target);

    // Show diff stats
    const diff = document.getElementById('hDiff');
    if (diff && inputId === 'hInput') {
      diff.style.display = 'block';
      const status = data.target_reached ? '✅ Target reached!'
        : data.stop_reason === 'stagnated' ? '⚠️ Plateaued — no improvement in 15 rounds. Best result returned.'
        : data.stop_reason === 'detectors_failed' ? '❌ Detectors failed 5x in a row'
        : '⚠️ Target not reached — try again or raise limit';
      const bestNote = data.best_iteration !== data.total_iterations ? ' (best was iteration #' + data.best_iteration + ')' : '';
      diff.innerHTML = status + ' · ' +
        data.total_iterations + ' iteration' + (data.total_iterations > 1 ? 's' : '') + bestNote + ' · ' +
        'Final AI: <strong>' + data.final_ai_percentage + '%</strong> · ' +
        data.original_word_count + ' → ' + data.humanized_word_count + ' words';
    }

    if (data.target_reached) {
      toast('✅ Hit target: ' + data.final_ai_percentage + '% AI (best of ' + data.total_iterations + ' tries)');
    } else if (data.stop_reason === 'stagnated') {
      toast('⚠️ Plateaued at ' + data.final_ai_percentage + '% AI after ' + data.total_iterations + ' tries — best was #' + data.best_iteration, 5000);
    } else if (data.stop_reason === 'detectors_failed') {
      toast('❌ Detectors failed repeatedly — best: ' + data.final_ai_percentage + '% AI', 5000);
    } else {
      toast('⚠️ Best: ' + data.final_ai_percentage + '% AI (iteration #' + data.best_iteration + ')');
    }
  } catch(e) {
    toast('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✏️ Humanize';
  }
}

// ─── Detection ───
function barColor(pct) {
  if (pct <= 15) return 'linear-gradient(90deg,#00b894,#55efc4)';
  if (pct <= 40) return 'linear-gradient(90deg,#00b894,#ffeaa7)';
  if (pct <= 60) return 'linear-gradient(90deg,#ffeaa7,#fdcb6e)';
  if (pct <= 85) return 'linear-gradient(90deg,#e17055,#fdcb6e)';
  return 'linear-gradient(90deg,#d63031,#e17055)';
}
function verdictClass(v) {
  if (v.includes('Human')) return 'v-human';
  if (v.includes('Mixed')) return 'v-mixed';
  return 'v-ai';
}

function renderCard(r) {
  const d = document.createElement('div');
  d.className = 'result-card';
  if (r.status === 'success') {
    d.innerHTML = `
      <div class="rh"><span class="rname">${r.detector}</span><span class="badge b-ok">✓ Done</span></div>
      <div class="score-line"><span class="l">AI</span><span class="v" style="color:${r.ai_percentage>50?'var(--red)':'var(--green)'}">${r.ai_percentage}%</span></div>
      <div class="score-line"><span class="l">Human</span><span class="v">${r.human_percentage}%</span></div>
      <div class="rbar"><div class="rbar-fill" style="width:${r.ai_percentage}%;background:${barColor(r.ai_percentage)}"></div></div>
      <div class="rverdict">${r.verdict}</div>
      ${r.details ? '<div class="rmsg">'+r.details+'</div>' : ''}`;
  } else if (r.status === 'manual') {
    d.innerHTML = `
      <div class="rh"><span class="rname">${r.detector}</span><span class="badge b-man">Manual</span></div>
      <div class="rmsg">${r.message}</div>
      ${r.url ? '<a href="'+r.url+'" target="_blank" class="rlink">Open '+r.detector+' ↗</a>' : ''}`;
  } else {
    d.innerHTML = `
      <div class="rh"><span class="rname">${r.detector}</span><span class="badge b-err">Error</span></div>
      <div class="rmsg">${r.message||'Unknown error'}</div>`;
  }
  return d;
}

async function runDetection(inputId, summaryId, resultsId, progressId) {
  summaryId = summaryId || 'detectSummary';
  resultsId = resultsId || 'detectResults';
  progressId = progressId || 'detectProgress';

  const text = document.getElementById(inputId).value.trim();
  if (!text) { toast('Paste some text first'); return; }
  if (text.length < 50) { toast('Need at least 50 characters'); return; }

  const prog = document.getElementById(progressId);
  const grid = document.getElementById(resultsId);
  const summ = document.getElementById(summaryId);

  prog.classList.add('active');
  grid.innerHTML = '';
  summ.classList.remove('visible');

  // Loading placeholders
  ['ZeroGPT','Sapling AI','RoBERTa OpenAI','HC3 ChatGPT','GPTZero','Quillbot','Copyleaks','Scribbr'].forEach(n => {
    const c = document.createElement('div');
    c.className = 'result-card';
    c.style.opacity = '0.5';
    c.innerHTML = '<div class="rh"><span class="rname">'+n+'</span><span class="badge b-load"><span class="spinner"></span></span></div><div class="rmsg">Checking...</div>';
    grid.appendChild(c);
  });

  try {
    const resp = await fetch('/api/check', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text}),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error); grid.innerHTML=''; return; }

    grid.innerHTML = '';
    data.results.forEach(r => grid.appendChild(renderCard(r)));

    const s = data.summary;
    if (s.total_checked > 0) {
      summ.classList.add('visible');
      const prefix = summaryId.startsWith('wf') ? 'w' : 'd';
      document.getElementById(prefix+'HumanPct').textContent = s.avg_human_percentage + '%';
      document.getElementById(prefix+'AiPct').textContent = s.avg_ai_percentage + '%';
      document.getElementById(prefix+'HumanBar').style.width = s.avg_human_percentage + '%';
      document.getElementById(prefix+'AiBar').style.width = s.avg_ai_percentage + '%';
      const vEl = document.getElementById(prefix+'Verdict');
      vEl.textContent = s.overall_verdict;
      vEl.className = 'verdict-badge ' + verdictClass(s.overall_verdict);
    }
  } catch(e) {
    toast('Error: ' + e.message);
  } finally {
    prog.classList.remove('active');
  }
}

// ─── Plagiarism Check ───
async function runPlagiarism(inputId, summaryId, resultsId, progressId, prefix) {
  summaryId = summaryId || 'plagSummary';
  resultsId = resultsId || 'plagResults';
  progressId = progressId || 'plagProgress';
  prefix = prefix || 'p';

  const text = document.getElementById(inputId).value.trim();
  if (!text) { toast('Paste some text first'); return; }
  if (text.length < 50) { toast('Need at least 50 characters'); return; }

  const prog = document.getElementById(progressId);
  const resultsEl = document.getElementById(resultsId);
  const summ = document.getElementById(summaryId);

  prog.classList.add('active');
  resultsEl.innerHTML = '';
  summ.classList.remove('visible');

  try {
    const resp = await fetch('/api/plagiarism', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error); return; }
    renderPlagResults(data, summaryId, resultsId, prefix);
  } catch(e) {
    toast('Error: ' + e.message);
  } finally {
    prog.classList.remove('active');
  }
}

function renderPlagResults(data, summaryId, resultsId, prefix) {
  const resultsEl = document.getElementById(resultsId);
  const summ = document.getElementById(summaryId);
  const s = data.summary;

  summ.classList.add('visible');
  const origPct = Math.round(100 - s.plagiarism_percentage);
  document.getElementById(prefix + 'OrigPct').textContent = origPct + '%';
  document.getElementById(prefix + 'FlagPct').textContent = s.plagiarism_percentage + '%';
  document.getElementById(prefix + 'OrigBar').style.width = origPct + '%';
  document.getElementById(prefix + 'FlagBar').style.width = s.plagiarism_percentage + '%';
  const vEl = document.getElementById(prefix + 'Verdict');
  vEl.textContent = s.verdict;
  vEl.className = 'verdict-badge ' + (s.plagiarism_percentage === 0 ? 'v-human' : s.plagiarism_percentage < 50 ? 'v-mixed' : 'v-ai');

  resultsEl.innerHTML = '';
  data.chunks.forEach(chunk => {
    const div = document.createElement('div');
    div.className = 'plag-chunk ' + (chunk.flagged ? 'flagged' : 'clean');
    let html = '<div class="plag-text">"' + chunk.text + '"</div>';
    html += '<div class="plag-status ' + (chunk.flagged ? 'warn' : 'ok') + '">' + (chunk.flagged ? '⚠️ Potential match found' : '✅ No matches found') + '</div>';
    if (chunk.matches && chunk.matches.length > 0) {
      html += '<div class="plag-sources">';
      chunk.matches.forEach(m => {
        html += '<a class="plag-source" href="' + m.url + '" target="_blank">' + m.title + ' ↗</a>';
      });
      html += '</div>';
    }
    div.innerHTML = html;
    resultsEl.appendChild(div);
  });
}

// ─── Full Workflow ───
async function runWorkflow() {
  const input = document.getElementById('wInput');
  const text = input.value.trim();
  if (!text) { toast('Paste some text first'); return; }

  const target = parseFloat(document.getElementById('wTarget').value) || 0;
  const btn = document.getElementById('workflowBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Humanizing until ≤' + target + '% AI...';

  const prog = document.getElementById('wfProgress');
  prog.classList.add('active');
  document.getElementById('wfHumanizedCard').style.display = 'none';
  document.getElementById('wfSummary').classList.remove('visible');
  document.getElementById('wfResults').innerHTML = '';
  document.getElementById('wIterLog').classList.remove('visible');
  document.getElementById('wfPlagSummary').classList.remove('visible');
  document.getElementById('wfPlagResults').innerHTML = '';

  try {
    // Step 1: Humanize until target
    const stripSuspicious = document.getElementById('wStrip')?.checked || false;
    const hResp = await fetch('/api/humanize-until', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text, target, strip_suspicious: stripSuspicious}),
    });
    const hData = await hResp.json();
    if (hData.error) { toast(hData.error); return; }

    document.getElementById('wOutput').value = hData.humanized;
    document.getElementById('wfHumanizedCard').style.display = 'block';
    updateMeta('wMeta', hData.original, hData.humanized);

    // Show iteration log
    renderIterLog('wIterLog', 'wIterRows', hData.iterations, target);

    const statusMsg = hData.target_reached
      ? '✅ Target reached in ' + hData.total_iterations + ' iteration(s)!'
      : hData.stop_reason === 'stagnated'
        ? '⚠️ Plateaued at ' + hData.final_ai_percentage + '% after ' + hData.total_iterations + ' tries'
        : '⚠️ Best: ' + hData.final_ai_percentage + '% after ' + hData.total_iterations + ' tries';
    toast(statusMsg, 4000);

    // Step 2: Full detection on final result
    btn.innerHTML = '<span class="spinner"></span> Running all detectors...';

    const dResp = await fetch('/api/check', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text: hData.humanized}),
    });
    const dData = await dResp.json();
    if (dData.error) { toast(dData.error); return; }

    const grid = document.getElementById('wfResults');
    grid.innerHTML = '';
    dData.results.forEach(r => grid.appendChild(renderCard(r)));

    const s = dData.summary;
    if (s.total_checked > 0) {
      const summ = document.getElementById('wfSummary');
      summ.classList.add('visible');
      document.getElementById('wHumanPct').textContent = s.avg_human_percentage + '%';
      document.getElementById('wAiPct').textContent = s.avg_ai_percentage + '%';
      document.getElementById('wHumanBar').style.width = s.avg_human_percentage + '%';
      document.getElementById('wAiBar').style.width = s.avg_ai_percentage + '%';
      const vEl = document.getElementById('wVerdict');
      vEl.textContent = s.overall_verdict;
      vEl.className = 'verdict-badge ' + verdictClass(s.overall_verdict);
    }

    // Step 3: Plagiarism check on humanized text
    btn.innerHTML = '<span class="spinner"></span> Checking plagiarism...';

    const pResp = await fetch('/api/plagiarism', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text: hData.humanized}),
    });
    const pData = await pResp.json();
    if (!pData.error) {
      renderPlagResults(pData, 'wfPlagSummary', 'wfPlagResults', 'wp');
    }

  } catch(e) {
    toast('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '⚡ Humanize & Detect & Plagiarism';
    prog.classList.remove('active');
  }
}

// Keyboard shortcut: Cmd/Ctrl+Enter
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    const active = document.querySelector('.tab-content.active');
    if (active.id === 'tab-humanize') doHumanizeUntil('hInput','hOutput','hIterLog','hMeta');
    else if (active.id === 'tab-detect') runDetection('dInput');
    else if (active.id === 'tab-plagiarism') runPlagiarism('pInput');
    else if (active.id === 'tab-workflow') runWorkflow();
  }
});
</script>

</body>
</html>
'''


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 60)
    print("  AI Humanizer + Detector Panel")
    print(f"  Open  http://127.0.0.1:{port}  in your browser")
    print("  Cmd+C to stop")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
