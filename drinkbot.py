#!/usr/bin/env python3
"""Bot Telegram: random quán nước và người đi mua. Chạy thường trực (long polling).

Lệnh hỗ trợ:
    /random           bấm nút chọn mục (healthy/toxic/buồn ngủ) rồi random quán trong mục
    /add <tên>        thêm quán (ngăn bằng dấu phẩy), sau đó bấm nút chọn mục
    /cat <tên>        đổi mục cho quán đã có
    /del <tên>        xoá quán
    /list             xem danh sách quán, gom theo mục
    /vote             bốc vài quán ra cho cả nhóm bầu
    /vote_end         chốt kết quả vote

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

# category cho quán -> (nhãn hiển thị, emoji)
CATEGORIES = {
    "healthy": ("Healthy", "🥗"),
    "toxic": ("Toxic", "🧋"),
    "sleepy": ("Buồn ngủ", "😴"),
}
DEFAULT_CATEGORY = "toxic"

# key lưu lịch sử đã chọn -> số lần gần nhất cần nhớ để tránh lặp lại
HISTORY = {"recent_shops": 3, "recent_pics": 3}

HELP = (
    "🥤 <b>Bot random quán nước</b>\n\n"
    "<b>Quán</b>\n"
    "/random — bấm chọn mục rồi random 1 quán trong đó\n"
    "/add Crane, Toco — thêm quán (ngăn bằng dấu phẩy), sau đó bấm chọn mục\n"
    "/cat Crane — đổi mục cho quán đã có\n"
    "/del Crane — xoá quán\n"
    "/list — xem danh sách quán theo mục\n\n"
    "<b>Vote</b>\n"
    "/vote — bốc 3 quán ra cho cả nhóm bầu\n"
    "/vote_end — chốt kết quả\n\n"
    "<b>Người đi mua</b>\n"
    "/add_pic Nam, Lan — thêm người\n"
    "/del_pic Nam — xoá người\n"
    "/list_pic — xem danh sách người\n"
    "/who_pic — random 1 người đi mua\n\n"
    "<b>Combo</b>\n"
    "/today — random một phát ra cả quán và người\n\n"
    "Mỗi group có danh sách riêng. Bot né quán và người vừa ra gần đây."
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


def send(
    token: str,
    chat_id: int,
    text: str,
    reply_to: int | None = None,
    keyboard: list[list[tuple[str, str]]] | None = None,
) -> None:
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to is not None:
        params["reply_to_message_id"] = reply_to
    if keyboard is not None:
        params["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in keyboard]}
        )
    try:
        call(token, "sendMessage", params, timeout=30)
    except urllib.error.HTTPError as exc:
        print(f"Gửi lỗi {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)


def edit_message(
    token: str,
    chat_id: int,
    message_id: int,
    text: str,
    keyboard: list[list[tuple[str, str]]] | None = None,
) -> None:
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if keyboard is not None:
        params["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in keyboard]}
        )
    try:
        call(token, "editMessageText", params, timeout=30)
    except urllib.error.HTTPError as exc:
        print(f"Sửa tin lỗi {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)


def answer_callback(token: str, callback_id: str, text: str = "") -> None:
    try:
        call(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text}, timeout=15)
    except urllib.error.HTTPError as exc:
        print(f"Trả lời callback lỗi {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)


def category_keyboard(prefix: str) -> list[list[tuple[str, str]]]:
    return [[(f"{emoji} {label}", f"{prefix}:{key}")] for key, (label, emoji) in CATEGORIES.items()]


def esc(text: str) -> str:
    """Escape nội dung do người dùng nhập trước khi nhét vào HTML."""
    return html.escape(text, quote=False)


# ------------------------------------------------------------------- Lưu dữ liệu


def _shop_entry(name: str, category: str = DEFAULT_CATEGORY) -> dict:
    return {"name": name, "category": category if category in CATEGORIES else DEFAULT_CATEGORY}


class Store:
    """Lưu danh sách quán và người theo từng chat vào 1 file JSON.

    Cấu trúc: {"<chat_id>": {"shops": [{"name":.., "category":..}], "pics": [...]}}
    File đời cũ dạng {"<chat_id>": [...]} được hiểu là danh sách người.
    File đời cũ hơn nữa có "shops" là list[str] thuần (chưa có category) —
    được nạp lại kèm category mặc định.
    Group chưa có danh sách quán riêng thì dùng tạm `defaults` (từ biến SHOPS);
    khi group đó sửa danh sách lần đầu, bản mặc định được chép vào rồi sửa trên đó.
    """

    def __init__(self, path: Path, defaults: dict[str, list] | None = None) -> None:
        self.path = path
        self.defaults = defaults or {}
        self.data: dict[str, dict[str, list]] = {}
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
                            k: self._normalize(k, v)
                            for k, v in value.items()
                            if (k in KINDS or k in HISTORY) and isinstance(v, list)
                        }

    @staticmethod
    def _normalize(kind: str, items: list) -> list:
        if kind != "shops":
            return list(items)
        out = []
        for item in items:
            if isinstance(item, str):
                out.append(_shop_entry(item))
            elif isinstance(item, dict) and "name" in item:
                out.append(_shop_entry(item["name"], item.get("category", DEFAULT_CATEGORY)))
        return out

    def _save(self) -> None:
        """Ghi qua file tạm rồi replace — tránh hỏng file nếu bot chết giữa chừng."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            print(f"Không ghi được {self.path}: {exc}", file=sys.stderr)

    def list(self, chat_id: int, kind: str) -> list:
        chat = self.data.get(str(chat_id), {})
        if kind in chat:
            return list(chat[kind])
        return list(self.defaults.get(kind, []))

    def list_shop_names(self, chat_id: int, category: str | None = None) -> list[str]:
        shops = self.list(chat_id, "shops")
        if category is not None:
            shops = [s for s in shops if s["category"] == category]
        return [s["name"] for s in shops]

    def _editable(self, chat_id: int, kind: str) -> list:
        """Lấy list để sửa; lần đầu thì chép bản mặc định vào group này."""
        chat = self.data.setdefault(str(chat_id), {})
        if kind not in chat:
            chat[kind] = [dict(s) for s in self.defaults.get(kind, [])] if kind == "shops" else list(
                self.defaults.get(kind, [])
            )
        return chat[kind]

    def add(self, chat_id: int, kind: str, names: list[str]) -> tuple[list[str], list[str], bool]:
        """Trả (đã thêm, đã có sẵn, có bị đụng trần MAX_ITEMS không)."""
        current = self._editable(chat_id, kind)
        is_shops = kind == "shops"
        existing = {(s["name"] if is_shops else s).casefold() for s in current}
        added, dup = [], []
        full = False
        for name in names:
            if name.casefold() in existing:
                dup.append(name)
            elif len(current) >= MAX_ITEMS:
                full = True
                break
            else:
                current.append(_shop_entry(name) if is_shops else name)
                existing.add(name.casefold())
                added.append(name)
        if added:
            self._save()
        return added, dup, full

    def remove(self, chat_id: int, kind: str, names: list[str]) -> tuple[list[str], list[str]]:
        """Trả (đã xoá, không tìm thấy). So tên không phân biệt hoa thường."""
        current = self._editable(chat_id, kind)
        is_shops = kind == "shops"
        removed, missing = [], []
        for name in names:
            match = next(
                (c for c in current if (c["name"] if is_shops else c).casefold() == name.casefold()), None
            )
            if match is None:
                missing.append(name)
            else:
                current.remove(match)
                removed.append(match["name"] if is_shops else match)
        if removed:
            self._save()
        return removed, missing

    def set_shop_category(self, chat_id: int, name: str, category: str) -> bool:
        """Gán category cho 1 quán đã có. Trả False nếu không tìm thấy."""
        if category not in CATEGORIES:
            return False
        current = self._editable(chat_id, "shops")
        match = next((s for s in current if s["name"].casefold() == name.casefold()), None)
        if match is None:
            return False
        match["category"] = category
        self._save()
        return True

    def recent(self, chat_id: int, key: str) -> list[str]:
        """Danh sách vừa được chọn gần đây, mới nhất đứng đầu."""
        return list(self.data.get(str(chat_id), {}).get(key, []))

    def push_recent(self, chat_id: int, key: str, name: str) -> None:
        """Ghi nhận vừa chọn `name`, chỉ giữ lại HISTORY[key] lượt gần nhất."""
        chat = self.data.setdefault(str(chat_id), {})
        history = [n for n in chat.get(key, []) if n.casefold() != name.casefold()]
        history.insert(0, name)
        chat[key] = history[: HISTORY[key]]
        self._save()


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


class PendingAdds:
    """Nhớ tạm các quán vừa thêm, chờ người dùng bấm nút chọn mục.

    callback_data của Telegram chỉ được 64 byte nên không nhét thẳng tên quán vào
    được; ở đây chỉ gửi kèm một mã ngắn rồi tra ngược lại.
    """

    MAX = 200

    def __init__(self) -> None:
        self.items: dict[str, tuple[int, list[str]]] = {}
        self.counter = 0

    def put(self, chat_id: int, names: list[str]) -> str:
        self.counter += 1
        ticket = str(self.counter)
        self.items[ticket] = (chat_id, names)
        while len(self.items) > self.MAX:
            self.items.pop(next(iter(self.items)))
        return ticket

    def take(self, ticket: str, chat_id: int) -> list[str] | None:
        found = self.items.get(ticket)
        if found is None or found[0] != chat_id:
            return None
        del self.items[ticket]
        return found[1]


PENDING = PendingAdds()


class Polls:
    """Các cuộc vote đang mở. Mỗi user 1 phiếu, bấm lại là đổi phiếu.

    Chỉ giữ trong RAM — restart bot là mất, vote dở thì gõ lại /vote.
    """

    MAX = 50

    def __init__(self) -> None:
        self.items: dict[str, tuple[int, list[str], dict[int, int]]] = {}
        self.counter = 0

    def put(self, chat_id: int, options: list[str]) -> str:
        self.counter += 1
        ticket = str(self.counter)
        self.items[ticket] = (chat_id, options, {})
        while len(self.items) > self.MAX:
            self.items.pop(next(iter(self.items)))
        return ticket

    def vote(self, ticket: str, chat_id: int, user_id: int, choice: int) -> tuple[list[str], dict[int, int]] | None:
        """Ghi phiếu. Trả (lựa chọn, phiếu) hoặc None nếu vote đã hết hạn."""
        found = self.items.get(ticket)
        if found is None or found[0] != chat_id or not 0 <= choice < len(found[1]):
            return None
        _, options, votes = found
        votes[user_id] = choice
        return options, votes

    def close(self, ticket: str, chat_id: int) -> tuple[list[str], dict[int, int]] | None:
        found = self.items.get(ticket)
        if found is None or found[0] != chat_id:
            return None
        del self.items[ticket]
        return found[1], found[2]


POLLS = Polls()
VOTE_OPTIONS = 3


def category_label(key: str) -> str:
    label, emoji = CATEGORIES[key]
    return f"{emoji} {label}"


def pick_fresh(store: Store, chat_id: int, key: str, names: list[str]) -> str:
    """Chọn ngẫu nhiên, ưu tiên cái lâu chưa được chọn.

    Bỏ qua những cái vừa ra gần đây; nếu loại hết thì lấy cái cũ nhất trong lịch sử
    để danh sách ngắn vẫn xoay vòng thay vì kẹt.
    """
    recent = [r.casefold() for r in store.recent(chat_id, key)]
    fresh = [n for n in names if n.casefold() not in recent]
    if fresh:
        chosen = random.choice(fresh)
    else:
        # cả danh sách đều vừa ra gần đây: lấy cái nằm cuối lịch sử (lâu nhất chưa tới lượt)
        chosen = max(names, key=lambda n: recent.index(n.casefold()))
    store.push_recent(chat_id, key, chosen)
    return chosen


def numbered(items: list[str]) -> str:
    return "\n".join(f"{i}. {esc(x)}" for i, x in enumerate(items, 1))


def empty_hint(kind: str) -> str:
    label, _, suffix = KINDS[kind]
    return f"Chưa có {label} nào. Thêm bằng <code>/add{suffix} Tên</code>"


def do_add(store: Store, chat_id: int, kind: str, args: str, fallback: str = "") -> str:
    label, _, suffix = KINDS[kind]
    names = parse_names(args) or parse_names(fallback)
    if not names:
        return f"Thêm {label} nào? Ví dụ: <code>/add{suffix} Nam, Lan</code>"
    added, dup, full = store.add(chat_id, kind, names)
    parts = []
    if added:
        parts.append("✅ Đã thêm: " + ", ".join(esc(n) for n in added))
    if dup:
        parts.append("⚠️ Đã có sẵn: " + ", ".join(esc(n) for n in dup))
    if full:
        parts.append(f"🚫 Danh sách đầy rồi (tối đa {MAX_ITEMS} {label}).")
    return "\n".join(parts)


def do_add_shops(store: Store, chat_id: int, args: str) -> tuple[str, list[list[tuple[str, str]]] | None]:
    """Thêm quán rồi hỏi mục. Trả (lời nhắn, bàn phím chọn mục hoặc None)."""
    names = parse_names(args)
    if not names:
        return "Thêm quán nào? Ví dụ: <code>/add Crane, Toco</code>", None
    added, dup, full = store.add(chat_id, "shops", names)
    parts = []
    if added:
        parts.append("✅ Đã thêm: " + ", ".join(esc(n) for n in added))
    if dup:
        parts.append("⚠️ Đã có sẵn: " + ", ".join(esc(n) for n in dup))
    if full:
        parts.append(f"🚫 Danh sách đầy rồi (tối đa {MAX_ITEMS} quán).")
    if not added:
        return "\n".join(parts), None
    ticket = PENDING.put(chat_id, added)
    parts.append("\nXếp vào mục nào?")
    return "\n".join(parts), category_keyboard(f"setcat:{ticket}")


def do_cat(store: Store, chat_id: int, args: str) -> tuple[str, list[list[tuple[str, str]]] | None]:
    """Đổi mục cho quán đã có. Trả (lời nhắn, bàn phím chọn mục hoặc None)."""
    names = parse_names(args)
    if not names:
        return "Đổi mục cho quán nào? Ví dụ: <code>/cat Crane</code>", None
    known = store.list_shop_names(chat_id)
    found, missing = [], []
    for name in names:
        match = next((k for k in known if k.casefold() == name.casefold()), None)
        (missing if match is None else found).append(match or name)
    if not found:
        return "❓ Không có trong danh sách: " + ", ".join(esc(n) for n in missing), None
    parts = [f"Đổi mục cho: <b>{', '.join(esc(n) for n in found)}</b>"]
    if missing:
        parts.append("❓ Bỏ qua (không có trong danh sách): " + ", ".join(esc(n) for n in missing))
    parts.append("\nXếp vào mục nào?")
    return "\n".join(parts), category_keyboard(f"setcat:{PENDING.put(chat_id, found)}")


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
    if kind != "shops":
        return f"{emoji} {len(items)} {label}:\n{numbered(items)}"
    lines = [f"{emoji} {len(items)} quán:"]
    for key in CATEGORIES:
        names = [s["name"] for s in items if s["category"] == key]
        if names:
            lines.append(f"\n<b>{category_label(key)}</b>\n{numbered(names)}")
    return "\n".join(lines)


def do_pick(store: Store, chat_id: int, kind: str, args: str) -> str:
    label, emoji, _ = KINDS[kind]
    items = store.list(chat_id, kind)
    if not items:
        return empty_hint(kind)
    n, err = parse_count(args, len(items))
    if err:
        return err
    if n == 1:
        chosen = pick_fresh(store, chat_id, "recent_pics", items)
        return f"🫵 Hôm nay <b>{esc(chosen)}</b> đi mua nước nhé!"
    return f"{emoji} {n} {label} được chọn:\n{numbered(random.sample(items, n))}"


def do_random_shop(store: Store, chat_id: int, category: str) -> str:
    """Random 1 quán trong mục đã chọn, né mấy quán vừa đi gần đây."""
    names = store.list_shop_names(chat_id, category)
    if not names:
        return f"Mục {category_label(category)} chưa có quán nào. Thêm bằng <code>/add Tên</code>"
    chosen = pick_fresh(store, chat_id, "recent_shops", names)
    return f"{category_label(category)} — hôm nay uống ở: <b>{esc(chosen)}</b>"


def vote_text(options: list[str], votes: dict[int, int]) -> str:
    tally = [sum(1 for c in votes.values() if c == i) for i in range(len(options))]
    lines = ["🗳 <b>Chọn quán nào?</b> (bấm để bầu, bấm lại để đổi)"]
    for name, count in zip(options, tally):
        bar = "🟩" * count if count else "▫️"
        lines.append(f"{esc(name)} — {bar} {count}")
    lines.append(f"\n<i>{len(votes)} phiếu. Chốt bằng /vote_end</i>")
    return "\n".join(lines)


def vote_keyboard(ticket: str, options: list[str]) -> list[list[tuple[str, str]]]:
    return [[(name, f"vote:{ticket}:{i}")] for i, name in enumerate(options)]


def do_vote(store: Store, chat_id: int) -> tuple[str, list[list[tuple[str, str]]] | None]:
    """Mở vote giữa vài quán random."""
    names = store.list_shop_names(chat_id)
    if not names:
        return empty_hint("shops"), None
    if len(names) < 2:
        return "Cần ít nhất 2 quán mới vote được. Thêm bằng <code>/add Tên</code>", None
    options = random.sample(names, min(VOTE_OPTIONS, len(names)))
    ticket = POLLS.put(chat_id, options)
    return vote_text(options, {}), vote_keyboard(ticket, options)


def do_vote_end(store: Store, chat_id: int, ticket: str | None = None) -> str:
    """Chốt vote đang mở gần nhất trong group này."""
    if ticket is None:
        ticket = next(
            (t for t, (cid, _, _) in reversed(list(POLLS.items.items())) if cid == chat_id), None
        )
    closed = POLLS.close(ticket, chat_id) if ticket else None
    if closed is None:
        return "Không có vote nào đang mở. Mở bằng <code>/vote</code>"
    options, votes = closed
    if not votes:
        return "Không ai bầu cả 😐 Thôi gõ <code>/random</code> cho nhanh."
    tally = [sum(1 for c in votes.values() if c == i) for i in range(len(options))]
    best = max(tally)
    winners = [options[i] for i, count in enumerate(tally) if count == best]
    if len(winners) > 1:
        chosen = random.choice(winners)
        note = f"\n<i>Hoà {best} phiếu giữa {', '.join(esc(w) for w in winners)}, bốc ngẫu nhiên.</i>"
    else:
        chosen = winners[0]
        note = ""
    store.push_recent(chat_id, "recent_shops", chosen)
    return f"🏆 Chốt: <b>{esc(chosen)}</b> ({best} phiếu){note}"


def do_today(store: Store, chat_id: int) -> str:
    """Combo quán + người. Phần nào chưa có danh sách thì bỏ qua, có nhắc ở cuối."""
    lines = ["📅 <b>Chốt đơn hôm nay</b>"]
    missing = []

    shops = store.list(chat_id, "shops")
    if shops:
        name = pick_fresh(store, chat_id, "recent_shops", [s["name"] for s in shops])
        category = next(s["category"] for s in shops if s["name"] == name)
        lines.append(f"🥤 Quán: <b>{esc(name)}</b> ({category_label(category)})")
    else:
        missing.append("/add")

    pics = store.list(chat_id, "pics")
    if pics:
        lines.append(f"🫵 Người đi mua: <b>{esc(pick_fresh(store, chat_id, 'recent_pics', pics))}</b>")
    else:
        missing.append("/add_pic")

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
        send(token, chat_id, "🎲 Muốn chọn quán kiểu nào?", msg_id, category_keyboard("pick"))
        return
    if cmd == "add":
        reply, keyboard = do_add_shops(store, chat_id, args)
        send(token, chat_id, reply, msg_id, keyboard)
        return
    if cmd == "cat":
        reply, keyboard = do_cat(store, chat_id, args)
        send(token, chat_id, reply, msg_id, keyboard)
        return
    if cmd == "vote":
        reply, keyboard = do_vote(store, chat_id)
        send(token, chat_id, reply, msg_id, keyboard)
        return

    if cmd == "del":
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

    elif cmd == "vote_end":
        reply = do_vote_end(store, chat_id)
    elif cmd == "today":
        reply = do_today(store, chat_id)
    elif cmd in ("start", "help"):
        reply = HELP
    else:
        return

    send(token, chat_id, reply, msg_id)


def handle_callback(token: str, store: Store, query: dict) -> None:
    """Xử lý nút bấm: chọn mục để random, hoặc gán mục cho quán vừa thêm."""
    callback_id = query["id"]
    message = query.get("message") or {}
    chat = message.get("chat") or {}
    data = query.get("data") or ""
    if not chat or ":" not in data:
        answer_callback(token, callback_id)
        return

    chat_id = chat["id"]
    message_id = message["message_id"]
    action, _, rest = data.partition(":")

    if action == "pick":
        if rest not in CATEGORIES:
            answer_callback(token, callback_id)
            return
        answer_callback(token, callback_id)
        edit_message(token, chat_id, message_id, do_random_shop(store, chat_id, rest))
        return

    if action == "vote":
        ticket, _, index = rest.partition(":")
        user_id = (query.get("from") or {}).get("id")
        result = POLLS.vote(ticket, chat_id, user_id, int(index)) if index.isdigit() and user_id else None
        if result is None:
            answer_callback(token, callback_id, "Vote này đóng rồi")
            return
        options, votes = result
        answer_callback(token, callback_id, f"Đã bầu {options[int(index)]}")
        edit_message(
            token, chat_id, message_id, vote_text(options, votes), vote_keyboard(ticket, options)
        )
        return

    if action == "setcat":
        ticket, _, category = rest.partition(":")
        names = PENDING.take(ticket, chat_id) if category in CATEGORIES else None
        if names is None:
            answer_callback(token, callback_id, "Hết hạn rồi, thêm lại nhé")
            return
        applied = [n for n in names if store.set_shop_category(chat_id, n, category)]
        answer_callback(token, callback_id, "Đã xếp mục")
        if applied:
            listed = ", ".join(esc(n) for n in applied)
            edit_message(
                token, chat_id, message_id, f"✅ {listed} → <b>{category_label(category)}</b>"
            )
        return

    answer_callback(token, callback_id)


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Thiếu TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 2

    raw = os.environ.get("SHOPS") or os.environ.get("DRINKS")
    names = [s.strip() for s in raw.split("|") if s.strip()] if raw else DEFAULT_SHOPS
    shops = [_shop_entry(n) for n in names]

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
            if "callback_query" in update:
                handle_callback(token, store, update["callback_query"])
                continue
            message = update.get("message") or update.get("channel_post")
            if message:
                handle(token, store, bot_username, message)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nDừng bot.")
