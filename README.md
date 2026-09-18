# Drink Bot

Bot Telegram random quán nước và random người đi mua.
Chỉ dùng thư viện chuẩn của Python — không cần `pip install` gì cả.

| Lệnh | Tác dụng |
|---|---|
| `/random` | bấm nút chọn mục, rồi random 1 quán trong mục đó |
| `/add Crane, Toco` | thêm quán (ngăn bằng dấu phẩy), rồi bấm nút chọn mục |
| `/cat Crane` | đổi mục cho quán đã có |
| `/del Crane` | xoá quán |
| `/list` | xem danh sách quán, gom theo mục |
| `/vote` | bốc 3 quán ra cho cả nhóm bầu |
| `/vote_end` | chốt kết quả vote |
| `/add_pic Nam, Lan` | thêm người vào danh sách đi mua |
| `/add_pic` | thêm chính bạn |
| `/del_pic Nam` | xoá người |
| `/list_pic` | xem danh sách người |
| `/who_pic` | random 1 người đi mua |
| `/today` | random một phát ra cả quán + người |
| `/help` | hướng dẫn |

## Mục quán

Mỗi quán thuộc 1 trong 3 mục:

| Mục | Ý nghĩa |
|---|---|
| 🥗 Healthy | quán đồ uống lành mạnh |
| 🧋 Toxic | trà sữa, topping, đường sữa full |
| 😴 Buồn ngủ | cà phê, thứ gì đó chống buồn ngủ |

Cả `/random`, `/add` và `/cat` đều đi 2 bước: gõ lệnh → bot hiện 3 nút → bấm chọn mục.
`/random` xong là ra luôn 1 quán trong mục đã chọn; `/add` xong là quán vừa thêm được xếp vào mục đó.
Quán thêm từ trước (hoặc từ biến `SHOPS`) mặc định nằm ở mục Toxic, đổi bằng `/cat Tên quán`.

## Tránh trùng lặp

Bot nhớ 3 quán và 3 người gần nhất đã chọn, lần sau né ra — không bị Toco ba ngày liền,
không bị một người đi mua hai hôm liên tiếp. Danh sách ngắn hơn 3 thì xoay vòng đều.
Lịch sử lưu cùng file JSON nên restart bot vẫn nhớ.

## Vote

`/vote` bốc ngẫu nhiên 3 quán kèm nút bấm, mỗi người 1 phiếu, bấm nút khác là đổi phiếu.
`/vote_end` chốt — hoà phiếu thì bốc ngẫu nhiên giữa các quán cao nhất, và quán thắng cũng
được ghi vào lịch sử tránh trùng. Vote chỉ nằm trong RAM, restart bot là mất, gõ `/vote` lại.

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
random - Chọn mục rồi random quán
vote - Bốc 3 quán cho cả nhóm bầu
vote_end - Chốt kết quả vote
list - Xem danh sách quán theo mục
add - Thêm quán rồi chọn mục
cat - Đổi mục cho quán
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
`{"<chat_id>": {"shops": [{"name": "Crane", "category": "toxic"}], "pics": ["Nam"]}}`

`category` là `healthy`, `toxic` hoặc `sleepy`. File đời cũ (shops chỉ là danh sách tên)
vẫn đọc được, các quán trong đó được xếp vào `toxic`.

Mỗi chat còn có `recent_shops` và `recent_pics` — 3 lượt chọn gần nhất, dùng để tránh trùng.

- Chạy trực tiếp: file `pics.json` cùng thư mục (đổi chỗ bằng biến `DATA_FILE`).
- Chạy Docker: `/data/pics.json` trong volume `drinkbot-data`, `PIC_FILE` đã set sẵn trong Dockerfile.
  Rebuild image không mất dữ liệu; muốn xoá sạch thì `docker compose down -v`.

Xem nội dung khi đang chạy Docker:

```bash
docker compose -f /Users/phancaonguyen/Documents/temp/drink-poll-bot/docker-compose.yml exec drinkbot cat /data/pics.json
```
