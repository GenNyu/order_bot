#!/usr/bin/env python3
"""Bot Telegram: random quán nước và người đi mua. Chạy thường trực (long polling).

Lệnh hỗ trợ:
    /random [n]       random 1 (hoặc n) quán
    /add <tên>        thêm quán (nhiều quán thì ngăn bằng dấu phẩy)
    /del <tên>        xoá quán
    /list             xem danh sách quán

    /add_pic <tên>    thêm người vào danh sách đi mua
    /del_pic <tên>    xoá người
    /list_pic         xem danh sách người
    /who_pic [n]      random 1 (hoặc n) người đi mua

    /today            random combo: quán + người
    /help             hướng dẫn

Cấu hình qua biến môi trường (hoặc file .env cùng thư mục):
    TELEGRAM_BOT_TOKEN  token lấy từ @BotFather
    SHOPS               (tuỳ chọn) danh sách quán mặc định, ngăn cách bằng dấu |
                        (DRINKS vẫn dùng được cho tương thích ngược)
    DATA_FILE           (tuỳ chọn) nơi lưu dữ liệu, mặc định pics.json cùng thư mục
                        (PIC_FILE vẫn dùng được cho tương thích ngược)
"""

from __future__ import annotations

import html
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_SHOPS = [
    "Bé Hai Trà",
    "Tiệm Trà Nè",
    "Crane",
    "Toco",
]

API = "https://api.telegram.org/bot{token}/{method}"
MAX_PICK = 10
MAX_NAME_LEN = 64
MAX_ITEMS = 50

# key trong file lưu -> (nhãn, emoji, hậu tố lệnh)
KINDS = {
    "shops": ("quán", "🏪", ""),
    "pics": ("người", "👥", "_pic"),
}

HELP = (
    "🥤 <b>Bot random quán nước</b>\n\n"
    "<b>Quán</b>\n"
    "/random — chọn đại 1 quán\n"
    "/random 3 — chọn 3 quán khác nhau\n"
    "/add Crane, Toco — thêm quán (ngăn bằng dấu phẩy)\n"
    "/del Crane — xoá quán\n"
    "/list — xem danh sách quán\n\n"
    "<b>Người đi mua</b>\n"
    "/add_pic Nam, Lan — thêm người\n"
    "/del_pic Nam — xoá người\n"
    "/list_pic — xem danh sách người\n"
    "/who_pic — random 1 người đi mua\n\n"
    "<b>Combo</b>\n"
    "/today — random một phát ra cả quán và người\n\n"
    "Mỗi group có danh sách riêng."
)


def load_dotenv(path: Path) -> None:
    """Nạp file .env đơn giản (KEY=VALUE) vào os.environ, không ghi đè biến sẵn có."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# ---------------------------------------------------------------- Telegram API


def call(token: str, method: str, params: dict, timeout: int = 60) -> dict:
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(API.format(token=token, method=method), data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send(token: str, chat_id: int, text: str, reply_to: int | None = None) -> None:
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to is not None:
        params["reply_to_message_id"] = reply_to
    try:
        call(token, "sendMessage", params, timeout=30)
    except urllib.error.HTTPError as exc:
        print(f"Gửi lỗi {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)


def esc(text: str) -> str:
    """Escape nội dung do người dùng nhập trước khi nhét vào HTML."""
    return html.escape(text, quote=False)


# ------------------------------------------------------------------- Lưu dữ liệu


class Store:
    """Lưu danh sách quán và người theo từng chat vào 1 file JSON.

    Cấu trúc: {"<chat_id>": {"shops": [...], "pics": [...]}}
    File đời cũ dạng {"<chat_id>": [...]} được hiểu là danh sách người.
    Group chưa có danh sách quán riêng thì dùng tạm `defaults` (từ biến SHOPS);
    khi group đó sửa danh sách lần đầu, bản mặc định được chép vào rồi sửa trên đó.
    """

    def __init__(self, path: Path, defaults: dict[str, list[str]] | None = None) -> None:
        self.path = path
        self.defaults = defaults or {}
        self.data: dict[str, dict[str, list[str]]] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"Không đọc được {path}, bắt đầu từ rỗng: {exc}", file=sys.stderr)
                loaded = {}
            if isinstance(loaded, dict):
                for chat, value in loaded.items():
                    if isinstance(value, list):  # định dạng cũ: chỉ có danh sách người
                        self.data[chat] = {"pics": list(value)}
                    elif isinstance(value, dict):
                        self.data[chat] = {
                            k: list(v) for k, v in value.items() if k in KINDS and isinstance(v, list)
                        }

    def _save(self) -> None:
        """Ghi qua file tạm rồi replace — tránh hỏng file nếu bot chết giữa chừng."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            print(f"Không ghi được {self.path}: {exc}", file=sys.stderr)

    def list(self, chat_id: int, kind: str) -> list[str]:
        chat = self.data.get(str(chat_id), {})
        if kind in chat:
            return list(chat[kind])
        return list(self.defaults.get(kind, []))

    def _editable(self, chat_id: int, kind: str) -> list[str]:
        """Lấy list để sửa; lần đầu thì chép bản mặc định vào group này."""
        chat = self.data.setdefault(str(chat_id), {})
        if kind not in chat:
            chat[kind] = list(self.defaults.get(kind, []))
        return chat[kind]

    def add(self, chat_id: int, kind: str, names: list[str]) -> tuple[list[str], list[str], bool]:
        """Trả (đã thêm, đã có sẵn, có bị đụng trần MAX_ITEMS không)."""
        current = self._editable(chat_id, kind)
        existing = {n.casefold() for n in current}
        added, dup = [], []
        full = False
        for name in names:
            if name.casefold() in existing:
                dup.append(name)
            elif len(current) >= MAX_ITEMS:
                full = True
                break
            else:
                current.append(name)
                existing.add(name.casefold())
                added.append(name)
        if added:
            self._save()
        return added, dup, full

    def remove(self, chat_id: int, kind: str, names: list[str]) -> tuple[list[str], list[str]]:
        """Trả (đã xoá, không tìm thấy). So tên không phân biệt hoa thường."""
        current = self._editable(chat_id, kind)
        removed, missing = [], []
        for name in names:
            match = next((c for c in current if c.casefold() == name.casefold()), None)
            if match is None:
                missing.append(name)
            else:
                current.remove(match)
                removed.append(match)
        if removed:
            self._save()
        return removed, missing


def parse_names(args: str) -> list[str]:
    """Tách 'Nam, Lan , Nam' thành ['Nam', 'Lan'] — bỏ rỗng, bỏ trùng, cắt tên quá dài."""
    out: list[str] = []
    seen = set()
    for chunk in args.replace("\n", ",").split(","):
        name = " ".join(chunk.split())[:MAX_NAME_LEN]
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            out.append(name)
    return out


# ------------------------------------------------------------------- Xử lý lệnh


def parse_command(text: str, bot_username: str) -> tuple[str, str]:
    """Tách '/random@bot 3' thành ('random', '3'). Trả ('', '') nếu không phải lệnh."""
    if not text.startswith("/"):
        return "", ""
    head, _, rest = text.partition(" ")
    cmd = head[1:]
    if "@" in cmd:
        cmd, _, target = cmd.partition("@")
        if bot_username and target.lower() != bot_username.lower():
            return "", ""
    return cmd.lower(), rest.strip()


def parse_count(args: str, limit: int) -> tuple[int, str]:
    """Đọc số lượng từ tham số. Trả (n, lỗi) — lỗi rỗng nghĩa là hợp lệ."""
    if not args:
        return 1, ""
    try:
        n = int(args.split()[0])
    except ValueError:
        return 0, "Số lượng không hợp lệ. Ví dụ: <code>3</code>"
    if n < 1:
        return 0, "Ít nhất phải 1 chứ 😅"
    return min(n, MAX_PICK, limit), ""


def numbered(items: list[str]) -> str:
    return "\n".join(f"{i}. {esc(x)}" for i, x in enumerate(items, 1))


def empty_hint(kind: str) -> str:
    label, _, suffix = KINDS[kind]
    return f"Chưa có {label} nào. Thêm bằng <code>/add{suffix} Tên</code>"


def do_add(store: Store, chat_id: int, kind: str, args: str, fallback: str = "") -> str:
    label, _, suffix = KINDS[kind]
    names = parse_names(args) or parse_names(fallback)
    if not names:
        example = "Crane, Toco" if kind == "shops" else "Nam, Lan"
        return f"Thêm {label} nào? Ví dụ: <code>/add{suffix} {example}</code>"
    added, dup, full = store.add(chat_id, kind, names)
    parts = []
    if added:
        parts.append("✅ Đã thêm: " + ", ".join(esc(n) for n in added))
    if dup:
        parts.append("⚠️ Đã có sẵn: " + ", ".join(esc(n) for n in dup))
    if full:
        parts.append(f"🚫 Danh sách đầy rồi (tối đa {MAX_ITEMS} {label}).")
    return "\n".join(parts)


def do_del(store: Store, chat_id: int, kind: str, args: str) -> str:
    label, _, suffix = KINDS[kind]
    names = parse_names(args)
    if not names:
        example = "Crane" if kind == "shops" else "Nam"
        return f"Xoá {label} nào? Ví dụ: <code>/del{suffix} {example}</code>"
    removed, missing = store.remove(chat_id, kind, names)
    parts = []
    if removed:
        parts.append("🗑 Đã xoá: " + ", ".join(esc(n) for n in removed))
    if missing:
        parts.append("❓ Không có trong danh sách: " + ", ".join(esc(n) for n in missing))
    return "\n".join(parts)


def do_list(store: Store, chat_id: int, kind: str) -> str:
    label, emoji, _ = KINDS[kind]
    items = store.list(chat_id, kind)
    if not items:
        return empty_hint(kind)
    return f"{emoji} {len(items)} {label}:\n{numbered(items)}"


def do_pick(store: Store, chat_id: int, kind: str, args: str) -> str:
    label, emoji, _ = KINDS[kind]
    items = store.list(chat_id, kind)
    if not items:
        return empty_hint(kind)
    n, err = parse_count(args, len(items))
    if err:
        return err
    chosen = random.sample(items, n)
    if n == 1:
        if kind == "pics":
            return f"🫵 Hôm nay <b>{esc(chosen[0])}</b> đi mua nước nhé!"
        return f"🥤 Hôm nay uống ở: <b>{esc(chosen[0])}</b>"
    return f"{emoji} {n} {label} được chọn:\n{numbered(chosen)}"


def do_today(store: Store, chat_id: int) -> str:
    """Combo quán + người. Phần nào chưa có danh sách thì bỏ qua, có nhắc ở cuối."""
    lines = ["📅 <b>Chốt đơn hôm nay</b>"]
    missing = []
    for kind, prefix in (("shops", "🥤 Quán"), ("pics", "🫵 Người đi mua")):
        items = store.list(chat_id, kind)
        if items:
            lines.append(f"{prefix}: <b>{esc(random.choice(items))}</b>")
        else:
            missing.append(f"/add{KINDS[kind][2]}")
    if missing:
        lines.append("\n<i>Thiếu dữ liệu, thêm bằng: " + ", ".join(missing) + "</i>")
    return "\n".join(lines)


def sender_name(message: dict) -> str:
    """Tên người gửi, dùng khi /add_pic không kèm tham số."""
    user = message.get("from") or {}
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    return (name or user.get("username") or "").strip()[:MAX_NAME_LEN]


def handle(token: str, store: Store, bot_username: str, message: dict) -> None:
    text = message.get("text") or ""
    chat_id = message["chat"]["id"]
    msg_id = message["message_id"]
    cmd, args = parse_command(text, bot_username)
    if not cmd:
        return

    # /add_shop, /random_shop... vẫn nhận, coi như lệnh quán (tương thích ngược)
    if cmd.endswith("_shop"):
        cmd = cmd[: -len("_shop")]
    if cmd == "random_shop":
        cmd = "random"

    if cmd == "random":
        reply = do_pick(store, chat_id, "shops", args)
    elif cmd == "add":
        reply = do_add(store, chat_id, "shops", args)
    elif cmd == "del":
        reply = do_del(store, chat_id, "shops", args)
    elif cmd == "list":
        reply = do_list(store, chat_id, "shops")

    elif cmd == "add_pic":
        reply = do_add(store, chat_id, "pics", args, fallback=sender_name(message))
    elif cmd == "del_pic":
        reply = do_del(store, chat_id, "pics", args)
    elif cmd == "list_pic":
        reply = do_list(store, chat_id, "pics")
    elif cmd == "who_pic":
        reply = do_pick(store, chat_id, "pics", args)

    elif cmd == "today":
        reply = do_today(store, chat_id)
    elif cmd in ("start", "help"):
        reply = HELP
    else:
        return

    send(token, chat_id, reply, msg_id)


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Thiếu TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 2

    raw = os.environ.get("SHOPS") or os.environ.get("DRINKS")
    shops = [s.strip() for s in raw.split("|") if s.strip()] if raw else DEFAULT_SHOPS

    data_file = Path(
        os.environ.get("DATA_FILE")
        or os.environ.get("PIC_FILE")
        or Path(__file__).with_name("pics.json")
    )
    store = Store(data_file, defaults={"shops": shops})

    try:
        me = call(token, "getMe", {}, timeout=30)
    except urllib.error.HTTPError as exc:
        print(f"Token sai? Telegram trả {exc.code}", file=sys.stderr)
        return 1
    bot_username = me["result"].get("username", "")
    print(f"Bot @{bot_username} đang chạy, {len(shops)} quán mặc định, dữ liệu ở {data_file}.")

    offset = None
    while True:
        params = {"timeout": 50}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = call(token, "getUpdates", params, timeout=70)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"Lỗi mạng, thử lại sau 5s: {exc}", file=sys.stderr)
            time.sleep(5)
            continue

        for update in resp.get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("channel_post")
            if message:
                handle(token, store, bot_username, message)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nDừng bot.")
