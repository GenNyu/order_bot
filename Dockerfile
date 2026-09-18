FROM python:3.12-slim

# Log ra stdout ngay, không đệm — để `docker logs` thấy liền
ENV PYTHONUNBUFFERED=1
# Dữ liệu (quán + người) lưu ở /data (mount volume vào đây để không mất khi rebuild)
ENV PIC_FILE=/data/pics.json

WORKDIR /app
COPY drinkbot.py .

# Chạy bằng user thường, không cần root. /data phải thuộc user này thì bot mới ghi được.
RUN useradd --create-home --uid 10001 bot \
 && mkdir -p /data && chown bot:bot /data
USER bot

VOLUME ["/data"]
CMD ["python3", "drinkbot.py"]
