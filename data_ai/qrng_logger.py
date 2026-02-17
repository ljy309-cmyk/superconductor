"""QRNG (양자 난수 생성) 로그 저장 (Tkinter GUI).

- 큐비트 미세 노이즈의 소수점 자리를 추출하여 0/1 치환
- 실시간 비트 스트림 시각화
- 생성된 보안 키를 Excel로 저장
"""

import math
import os
import random
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import pandas as pd

from theme import get_tk_theme

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#89b4fa"
BIT_0_CLR = "#a6e3a1"
BIT_1_CLR = "#f38ba8"
KEY_CLR = "#f9e2af"


def _load_qrng_colors():
    """현재 테마(색맹 모드 포함)에서 비트 색상을 로드."""
    global BIT_0_CLR, BIT_1_CLR, BG, FG, ACCENT, KEY_CLR
    _tk = get_tk_theme()
    BG = _tk.BG
    FG = _tk.TEXT
    ACCENT = _tk.ACCENT_BLUE
    BIT_0_CLR = _tk.GREEN    # 비트 0 = safe color
    BIT_1_CLR = _tk.RED      # 비트 1 = danger color
    KEY_CLR = _tk.YELLOW

# ── 미션3: QRNG 키 공유 저장소 (BB84 통합, 스레드 안전) ──
import queue as _queue

_shared_key_queue: _queue.Queue = _queue.Queue()


def push_key_bits(bits: list[int]):
    """생성된 키 비트를 공유 저장소에 추가 (스레드 안전)."""
    for b in bits:
        _shared_key_queue.put(b)


def pop_key_bit():
    """공유 저장소에서 비트 1개 소비. 없으면 None (스레드 안전)."""
    try:
        return _shared_key_queue.get_nowait()
    except _queue.Empty:
        return None


def shared_key_available() -> int:
    """공유 저장소에 남아 있는 비트 수 (근사치)."""
    return _shared_key_queue.qsize()


from config_loader import cfg

OUTPUT_DIR = os.path.dirname(__file__)
BITS_PER_KEY = cfg("qrng", "bits_per_key", 256)
NOISE_SOURCES = cfg("qrng", "noise_sources", 7)


class QuantumNoiseSource:
    """큐비트 노이즈 소스 — 미세 노이즈의 소수점 자리에서 비트 추출."""

    def __init__(self, qid: int):
        self.qid = qid
        # 각 큐비트마다 다른 주파수/위상으로 노이즈 생성
        self._freq = 3.0 + random.random() * 10.0
        self._phase = random.random() * math.pi * 2
        self._drift = random.random() * 0.5

    def sample_noise(self) -> float:
        """현재 시간 기반 미세 노이즈 값 반환."""
        t = time.perf_counter()
        # 양자 노이즈 시뮬레이션: sin 중첩 + 열잡음 + 시스템 클럭 미세 차이
        noise = (
            math.sin(self._freq * t + self._phase)
            * math.cos(self._freq * 0.7 * t + self._drift)
            + random.gauss(0, 0.3)
            + math.sin(t * 137.035999)  # 미세구조상수 주파수
        )
        return noise

    def extract_bit(self) -> int:
        """노이즈에 ×1,000,000 → 일의 자리 % 2로 비트 추출 (미션1 업그레이드)."""
        noise = self.sample_noise()
        # ×1,000,000으로 소수점 끌어올림 → 일의 자리 추출 → 짝홀 판정
        amplified = int(abs(noise) * 1_000_000)
        digit = amplified % 10          # 일의 자리
        return digit % 2                # 짝수→0, 홀수→1

    def extract_bit_detail(self) -> tuple:
        """비트 추출 + 상세 정보 (bit, noise, amplified_ones_digit)."""
        noise = self.sample_noise()
        amplified = int(abs(noise) * 1_000_000)
        digit = amplified % 10
        bit = digit % 2
        return bit, noise, digit


class QRNGLoggerApp(tk.Toplevel):
    """QRNG 로그 저장 GUI."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("QRNG — 양자 난수 생성 로그")
        self.configure(bg=BG)
        self.geometry("820x620")
        self.resizable(False, False)

        # 큐비트 노이즈 소스
        self.sources = [QuantumNoiseSource(i) for i in range(NOISE_SOURCES)]

        # 생성된 데이터
        self.bit_buffer: list[int] = []
        self.keys: list[dict] = []  # {"id", "timestamp", "hex_key", "bits"}
        self.generating = False
        self._after_id = None

        self._build_ui()

    def _build_ui(self):
        # ── 상단: 큐비트 소스 표시 ───────────────────
        src_frame = tk.LabelFrame(
            self, text="  Qubit Noise Sources  ", font=("Consolas", 10, "bold"),
            bg=BG, fg=ACCENT, padx=8, pady=6,
        )
        src_frame.pack(fill=tk.X, padx=10, pady=(10, 4))

        self.source_labels: list[tk.Label] = []
        row = tk.Frame(src_frame, bg=BG)
        row.pack()
        for i in range(NOISE_SOURCES):
            lbl = tk.Label(
                row, text=f"Q{i}: —", font=("Consolas", 9), bg=BG, fg=FG, width=18,
            )
            lbl.pack(side=tk.LEFT, padx=4)
            self.source_labels.append(lbl)

        # ── 비트 스트림 표시 ─────────────────────────
        stream_frame = tk.LabelFrame(
            self, text="  Bit Stream (Live)  ", font=("Consolas", 10, "bold"),
            bg=BG, fg=ACCENT, padx=8, pady=6,
        )
        stream_frame.pack(fill=tk.X, padx=10, pady=4)

        self.stream_text = tk.Text(
            stream_frame, height=5, width=96, font=("Consolas", 10),
            bg="#181825", fg=FG, insertbackground=FG, state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self.stream_text.pack()
        self.stream_text.tag_configure("bit0", foreground=BIT_0_CLR)
        self.stream_text.tag_configure("bit1", foreground=BIT_1_CLR)

        # 진행 바
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill=tk.X, padx=10, pady=2)
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            prog_frame, maximum=BITS_PER_KEY, variable=self.progress_var, length=600,
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_label = tk.Label(
            prog_frame, text=f"0 / {BITS_PER_KEY} bits", font=("Consolas", 9),
            bg=BG, fg=FG,
        )
        self.progress_label.pack(side=tk.LEFT, padx=8)

        # ── 컨트롤 버튼 ─────────────────────────────
        ctrl_frame = tk.Frame(self, bg=BG)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=6)

        self.gen_btn = tk.Button(
            ctrl_frame, text="Generate Key", command=self._toggle_generate,
            font=("Consolas", 10, "bold"), width=16,
        )
        self.gen_btn.pack(side=tk.LEFT, padx=4)

        tk.Button(
            ctrl_frame, text="Save to Excel", command=self._save_excel,
            font=("Consolas", 10), width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            ctrl_frame, text="Clear All", command=self._clear_all,
            font=("Consolas", 10), width=10,
        ).pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            ctrl_frame, textvariable=self.status_var, font=("Consolas", 10, "bold"),
            bg=BG, fg=KEY_CLR,
        ).pack(side=tk.RIGHT, padx=8)

        # ── 키 로그 테이블 ───────────────────────────
        log_frame = tk.LabelFrame(
            self, text="  Generated Keys  ", font=("Consolas", 10, "bold"),
            bg=BG, fg=ACCENT, padx=8, pady=6,
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))

        columns = ("id", "timestamp", "hex_short", "hex_key", "entropy")
        self.tree = ttk.Treeview(log_frame, columns=columns, show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("timestamp", text="Timestamp")
        self.tree.heading("hex_short", text="Hash Fingerprint")
        self.tree.heading("hex_key", text="Full Hex Key")
        self.tree.heading("entropy", text="Entropy")
        self.tree.column("id", width=40)
        self.tree.column("timestamp", width=150)
        self.tree.column("hex_short", width=160)
        self.tree.column("hex_key", width=300)
        self.tree.column("entropy", width=70)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ── 생성 로직 ────────────────────────────────────

    def _toggle_generate(self):
        if self.generating:
            self.generating = False
            self.gen_btn.configure(text="Generate Key")
            if self._after_id:
                self.after_cancel(self._after_id)
                self._after_id = None
        else:
            self.bit_buffer.clear()
            self.progress_var.set(0)
            self.generating = True
            self.gen_btn.configure(text="Stop")
            self.status_var.set("Generating...")
            self._generate_step()

    def _generate_step(self):
        if not self.generating:
            return

        # 각 큐비트에서 1비트씩 추출 (라운드 로빈)
        bits_this_step = min(4, BITS_PER_KEY - len(self.bit_buffer))
        for _ in range(bits_this_step):
            src = self.sources[len(self.bit_buffer) % NOISE_SOURCES]
            bit = src.extract_bit()
            self.bit_buffer.append(bit)

        # 소스 라벨 업데이트 (미션1: ×1M 추출 과정 표시)
        for i, src in enumerate(self.sources):
            bit_val, noise_val, digit_val = src.extract_bit_detail()
            self.source_labels[i].configure(
                text=f"Q{i}: ×1M→d{digit_val}%2={bit_val}",
                fg=BIT_0_CLR if bit_val == 0 else BIT_1_CLR,
            )

        # 비트 스트림 업데이트
        self.stream_text.configure(state=tk.NORMAL)
        self.stream_text.delete("1.0", tk.END)
        for b in self.bit_buffer:
            tag = "bit0" if b == 0 else "bit1"
            self.stream_text.insert(tk.END, str(b), tag)
        self.stream_text.configure(state=tk.DISABLED)
        self.stream_text.see(tk.END)

        # 진행 바
        self.progress_var.set(len(self.bit_buffer))
        self.progress_label.configure(text=f"{len(self.bit_buffer)} / {BITS_PER_KEY} bits")

        # 키 완성 체크
        if len(self.bit_buffer) >= BITS_PER_KEY:
            self._finalize_key()
            return

        self._after_id = self.after(30, self._generate_step)

    def _finalize_key(self):
        self.generating = False
        self.gen_btn.configure(text="Generate Key")

        bits = self.bit_buffer[:BITS_PER_KEY]
        bit_str = "".join(str(b) for b in bits)

        # 비트열 → 16진수 키
        hex_key = hex(int(bit_str, 2))[2:].upper().zfill(BITS_PER_KEY // 4)

        # 엔트로피 계산 (0/1 비율 기반 간이 Shannon entropy)
        p1 = sum(bits) / len(bits)
        p0 = 1 - p1
        if p0 > 0 and p1 > 0:
            entropy = -(p0 * math.log2(p0) + p1 * math.log2(p1))
        else:
            entropy = 0.0

        key_id = len(self.keys) + 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 미션2: 16진수 해시 지문 (0x + 앞 16자)
        hex_short = "0x" + hex_key[:16]

        key_record = {
            "id": key_id,
            "timestamp": timestamp,
            "hex_key": hex_key,
            "hex_short": hex_short,
            "bits": bit_str,
            "entropy": round(entropy, 4),
        }
        self.keys.append(key_record)

        # 미션3: QRNG 키 비트를 공유 저장소에 추가 (BB84 통합)
        push_key_bits(bits)

        # 테이블에 추가
        display_hex = hex_key[:32] + ("..." if len(hex_key) > 32 else "")
        self.tree.insert("", tk.END, values=(
            key_id, timestamp, hex_short, display_hex, f"{entropy:.4f}",
        ))

        self.status_var.set(
            f"Key #{key_id} — {hex_short}… ({BITS_PER_KEY} bits, H={entropy:.4f})"
        )

    # ── Excel 저장 ───────────────────────────────────

    def _save_excel(self):
        if not self.keys:
            messagebox.showwarning("저장 실패", "생성된 키가 없습니다.", parent=self)
            return

        path = os.path.join(OUTPUT_DIR, "qrng_keys.xlsx")
        df = pd.DataFrame(self.keys)
        df.to_excel(path, index=False)
        self.status_var.set(f"Saved {len(self.keys)} keys → qrng_keys.xlsx")
        messagebox.showinfo("저장 완료", f"키 {len(self.keys)}개가 저장되었습니다.\n{path}", parent=self)

    def _clear_all(self):
        self.keys.clear()
        self.bit_buffer.clear()
        self.progress_var.set(0)
        self.progress_label.configure(text=f"0 / {BITS_PER_KEY} bits")
        self.stream_text.configure(state=tk.NORMAL)
        self.stream_text.delete("1.0", tk.END)
        self.stream_text.configure(state=tk.DISABLED)
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.status_var.set("Cleared")

    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        super().destroy()


def open_qrng_logger(master=None):
    """외부에서 호출하는 진입점."""
    _load_qrng_colors()
    QRNGLoggerApp(master)
