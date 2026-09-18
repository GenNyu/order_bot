# Drink Bot

Bot Telegram random quán nước và random người đi mua.
Chỉ dùng thư viện chuẩn của Python — không cần `pip install` gì cả.

| Lệnh | Tác dụng |
|---|---|
| `/random` | random 1 quán |
| `/random 3` | random 3 quán khác nhau (tối đa 10) |
| `/add Crane, Toco` | thêm quán (ngăn bằng dấu phẩy) |
| `/del Crane` | xoá quán |
| `/list` | xem danh sách quán |
| `/add_pic Nam, Lan` | thêm người vào danh sách đi mua |
| `/add_pic` | thêm chính bạn |
| `/del_pic Nam` | xoá người |
| `/list_pic` | xem danh sách người |
| `/who_pic` | random 1 người đi mua |
| `/today` | random một phát ra cả quán + người |
| `/help` | hướng dẫn |

Mỗi group có danh sách riêng (theo chat id), tối đa 50 quán và 50 người,
ghi xuống file JSON nên restart bot không mất.

Group chưa tự thêm quán thì dùng danh sách mặc định trong biến `SHOPS`.
Vừa gõ `/add` hoặc `/del` lần đầu là group đó có bản riêng, sửa `SHOPS` không ảnh hưởng nữa.

Các lệnh `/add_shop`, `/del_shop`, `/list_shop`, `/random_shop` vẫn nhận, chạy y hệt bản không hậu tố.

## 1. Tạo bot

1. Chat với [@BotFather](https://t.me/BotFather) → `/newbot` → lấy **token**.
2. Muốn dùng trong group: chỉ cần **Add members** → tìm tên bot → thêm vào. Xong.
   Không cần chỉnh `/setprivacy`: lệnh bắt đầu bằng `/` luôn được Telegram đẩy tới bot,
   kể cả khi privacy mode đang bật (privacy mode chỉ chặn tin nhắn tán gẫu thường).
   Nếu trong group có nhiều bot cùng có lệnh `/random`, gõ `/random@tên_bot` để gọi đúng bot.

## 2. Cấu hình

```bash
cp /Users/phancaonguyen/Documents/temp/drink-poll-bot/.env.example /Users/phancaonguyen/Documents/temp/drink-poll-bot/.env
```

Điền `TELEGRAM_BOT_TOKEN` vào `.env`. Sửa quán mặc định ở `SHOPS` (ngăn bằng `|`).

## 3. Chạy

```bash
python3 /Users/phancaonguyen/Documents/temp/drink-poll-bot/drinkbot.py
```

Chạy nền kèm log:

```bash
nohup python3 /Users/phancaonguyen/Documents/temp/drink-poll-bot/drinkbot.py > /Users/phancaonguyen/Documents/temp/drink-poll-bot/drinkbot.log 2>&1 &
```

Dừng:

```bash
pkill -f drinkbot.py
```

## 4. Menu lệnh cho đẹp (tuỳ chọn)

BotFather → `/setcommands` → dán:

```
random - Random quán nước
list - Xem danh sách quán
add - Thêm quán
del - Xoá quán
who_pic - Random người đi mua nước
list_pic - Xem danh sách người
add_pic - Thêm người vào danh sách
del_pic - Xoá người khỏi danh sách
today - Chốt đơn: quán + người
help - Hướng dẫn
```

## 5. Chạy bằng Docker

Cần `.env` có `TELEGRAM_BOT_TOKEN` (xem bước 2). File `.env` **không** bị copy vào image —
nó được nạp lúc chạy qua `env_file`.

```bash
cd /Users/phancaonguyen/Documents/temp/drink-poll-bot && docker compose up -d --build
```

Xem log:

```bash
docker compose -f /Users/phancaonguyen/Documents/temp/drink-poll-bot/docker-compose.yml logs -f
```

Dừng:

```bash
docker compose -f /Users/phancaonguyen/Documents/temp/drink-poll-bot/docker-compose.yml down
```

Đổi `SHOPS` trong `.env` rồi restart là xong, không cần build lại:

```bash
docker compose -f /Users/phancaonguyen/Documents/temp/drink-poll-bot/docker-compose.yml restart
```

## 6. Dữ liệu lưu ở đâu

Quán và người nằm chung 1 file JSON, tách theo chat id:
`{"<chat_id>": {"shops": [...], "pics": [...]}}`

- Chạy trực tiếp: file `pics.json` cùng thư mục (đổi chỗ bằng biến `DATA_FILE`).
- Chạy Docker: `/data/pics.json` trong volume `drinkbot-data`, `PIC_FILE` đã set sẵn trong Dockerfile.
  Rebuild image không mất dữ liệu; muốn xoá sạch thì `docker compose down -v`.

Xem nội dung khi đang chạy Docker:

```bash
docker compose -f /Users/phancaonguyen/Documents/temp/drink-poll-bot/docker-compose.yml exec drinkbot cat /data/pics.json
```
