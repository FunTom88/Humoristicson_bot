#!/usr/bin/env bash
set -euo pipefail

app=/opt/humoristicson-bot
config=/etc/humoristicson-bot/bot.env
repo=https://github.com/FunTom88/Humoristicson_bot.git
unit=humoristicson-bot.service

if (( EUID != 0 )); then
    echo 'Запустите установщик от root или через sudo bash.' >&2
    exit 1
fi

if [[ ! -f "$config" ]]; then
    if ! { exec 3<>/dev/tty; } 2>/dev/null; then
        echo 'Для первого запуска нужен интерактивный терминал.' >&2
        exit 1
    fi
    read -rsp 'Токен Telegram от BotFather: ' bot_token <&3
    printf '\n' >&2
    read -rp 'Адрес LM Studio [http://127.0.0.1:1234]: ' ai_url <&3
    read -rp 'Идентификатор модели [google/gemma-4-12b-qat]: ' ai_model <&3
    read -rsp 'Токен API модели (Enter, если не требуется): ' ai_key <&3
    printf '\n' >&2
    exec 3>&-
    ai_url=${ai_url:-http://127.0.0.1:1234}
    ai_model=${ai_model:-google/gemma-4-12b-qat}
    if [[ ! "$bot_token" =~ ^[0-9]+:[a-zA-Z0-9_-]+$ ]] ||
       [[ ! "$ai_url" =~ ^https?://[a-zA-Z0-9.:-]+(/v1|/api/v1|/api/v1/chat)?/?$ ]] ||
       [[ ! "$ai_model" =~ ^[a-zA-Z0-9_./:-]+$ ]] ||
       [[ ! "$ai_key" =~ ^[a-zA-Z0-9._-]*$ ]]; then
        echo 'Проверьте формат токена, адреса API и идентификатора модели.' >&2
        exit 1
    fi
fi

apt-get update
apt-get install -y ca-certificates git python3 python3-venv

if [[ ! -e "$app" ]]; then
    git clone --depth 1 --branch main "$repo" "$app"
elif [[ $(git -C "$app" remote get-url origin 2>/dev/null || true) != "$repo" ]]; then
    echo "Каталог $app уже используется другой установкой." >&2
    exit 1
fi

python3 -m venv "$app/.venv"
"$app/.venv/bin/python" -m pip install -r "$app/requirements.txt"

install -d -m 0700 /etc/humoristicson-bot
if [[ ! -f "$config" ]]; then
    (umask 077
     printf 'BOT_TOKEN=%s\nAI_BASE_URL=%s\nAI_MODEL=%s\nAI_API_KEY=%s\n' \
        "$bot_token" "$ai_url" "$ai_model" "$ai_key" > "$config")
fi
unset bot_token ai_key

install -m 0644 "$app/deploy/$unit" "/etc/systemd/system/$unit"
systemctl daemon-reload
systemctl enable --now "$unit"
systemctl status "$unit" --no-pager
