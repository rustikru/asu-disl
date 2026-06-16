<?php
/**
 * fetch_excel.php
 * Скачивает Excel-файлы из IMAP-почты и копирует из локальных папок
 * в директорию, где лежит этот скрипт.
 *
 * Настройки берутся из ~/ASU_PODHOD/settings.json
 * Запуск: php fetch_excel.php
 */

define('EXCEL_EXTS', ['xlsx', 'xls', 'xlsm', 'xltx', 'xltm']);
define('OUTPUT_DIR', __DIR__ . '/');

// ── Найти settings.json ───────────────────────────────────────────────────────

function find_settings_file(): ?string {
    $candidates = [
        getenv('APPDATA')   ? getenv('APPDATA')   . '/ASU_PODHOD/settings.json' : null,
        getenv('LOCALAPPDATA') ? getenv('LOCALAPPDATA') . '/ASU_PODHOD/settings.json' : null,
        getenv('HOME')      ? getenv('HOME')       . '/ASU_PODHOD/settings.json' : null,
    ];
    foreach ($candidates as $path) {
        if ($path && file_exists($path)) {
            return $path;
        }
    }
    return null;
}

function load_settings(): array {
    $path = find_settings_file();
    if (!$path) {
        echo "[WARN] settings.json не найден, используются пустые настройки.\n";
        return [];
    }
    echo "[INFO] Читаю настройки: $path\n";
    $data = json_decode(file_get_contents($path), true);
    return is_array($data) ? $data : [];
}

function get_imap_cfg(array $settings, string $tab): array {
    $default = [
        'enabled'                 => false,
        'server'                  => '',
        'port'                    => 993,
        'username'                => '',
        'password'                => '',
        'mailbox'                 => 'INBOX',
        'sender_filter'           => '',
        'subject_filter'          => '',
        'subject_equals'          => '',
        'attachment_name_contains'=> '',
        'attachment_name_equals'  => '',
    ];
    $legacy = $settings['imap'] ?? [];
    if ($tab === 'approach') {
        return array_merge($default, $legacy, $settings['imap_approach'] ?? []);
    }
    return array_merge($default, $settings['imap_departure'] ?? []);
}

// ── Проверка расширения файла ─────────────────────────────────────────────────

function is_excel(string $name): bool {
    $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
    return in_array($ext, EXCEL_EXTS, true);
}

// ── Безопасное имя файла ──────────────────────────────────────────────────────

function safe_filename(string $name): string {
    $name = preg_replace('/[^\w.\-]/u', '_', $name);
    return $name ?: 'attachment.xlsx';
}

// ── Декодирование MIME-заголовка ──────────────────────────────────────────────

function decode_mime(string $value): string {
    $decoded = imap_mime_header_decode($value);
    $result = '';
    foreach ($decoded as $part) {
        $charset = strtolower($part->charset ?? 'utf-8');
        $text    = $part->text ?? '';
        if ($charset !== 'utf-8' && $charset !== 'default') {
            $text = mb_convert_encoding($text, 'UTF-8', $charset);
        }
        $result .= $text;
    }
    return $result;
}

// ── Сохранить файл в OUTPUT_DIR ───────────────────────────────────────────────

function save_file(string $prefix, string $original_name, string $content): void {
    $ts       = date('Ymd_His');
    $safe     = safe_filename($original_name);
    $filename = "{$prefix}_{$ts}_{$safe}";
    $dest     = OUTPUT_DIR . $filename;
    file_put_contents($dest, $content);
    echo "[OK]   Сохранён: $filename\n";
}

// ── Получить файлы из IMAP ────────────────────────────────────────────────────

function fetch_from_imap(array $cfg, string $tab): void {
    if (empty($cfg['enabled'])) {
        echo "[SKIP] IMAP для '$tab' не включён.\n";
        return;
    }
    if (!function_exists('imap_open')) {
        echo "[ERROR] Расширение PHP IMAP не установлено (php-imap).\n";
        return;
    }

    $server   = trim($cfg['server'] ?? '');
    $port     = (int)($cfg['port'] ?? 993);
    $username = trim($cfg['username'] ?? '');
    $password = $cfg['password'] ?? '';
    $mailbox  = trim($cfg['mailbox'] ?? '') ?: 'INBOX';

    if (!$server || !$username || !$password) {
        echo "[SKIP] IMAP для '$tab': не заполнены server/username/password.\n";
        return;
    }

    $sender_filter            = strtolower(trim($cfg['sender_filter'] ?? ''));
    $subject_filter           = strtolower(trim($cfg['subject_filter'] ?? ''));
    $subject_equals           = strtolower(trim($cfg['subject_equals'] ?? ''));
    $attachment_name_contains = strtolower(trim($cfg['attachment_name_contains'] ?? ''));
    $attachment_name_equals   = strtolower(trim($cfg['attachment_name_equals'] ?? ''));

    $mbox_str = "{{$server}:{$port}/imap/ssl}{$mailbox}";
    echo "[INFO] Подключаюсь к IMAP: $mbox_str\n";

    $imap = @imap_open($mbox_str, $username, $password, 0, 1);
    if (!$imap) {
        echo "[ERROR] Не удалось подключиться: " . imap_last_error() . "\n";
        return;
    }

    // Письма за последние сутки
    $since = date('d-M-Y', strtotime('-1 day'));
    $uids  = imap_search($imap, "SINCE \"$since\"");
    if (!$uids) {
        echo "[INFO] Нет писем за последние сутки (tab=$tab).\n";
        imap_close($imap);
        return;
    }

    $found = 0;
    foreach (array_reverse($uids) as $uid) {
        $header = imap_headerinfo($imap, $uid);

        // Фильтр по отправителю
        if ($sender_filter) {
            $from = strtolower($header->fromaddress ?? '');
            if (strpos($from, $sender_filter) === false) continue;
        }

        // Фильтр по теме
        $subject = strtolower(decode_mime($header->subject ?? ''));
        if ($subject_equals && $subject !== $subject_equals) continue;
        if ($subject_filter && strpos($subject, $subject_filter) === false) continue;

        // Разбор вложений
        $structure = imap_fetchstructure($imap, $uid);
        $parts     = $structure->parts ?? [];

        foreach ($parts as $i => $part) {
            // Disposition: attachment
            $disp = '';
            if (!empty($part->disposition)) {
                $disp = strtolower($part->disposition);
            }
            if ($disp !== 'attachment') continue;

            // Имя файла
            $filename = '';
            foreach ($part->dparameters ?? [] as $param) {
                if (strtolower($param->attribute) === 'filename') {
                    $filename = decode_mime($param->value);
                }
            }
            foreach ($part->parameters ?? [] as $param) {
                if (strtolower($param->attribute) === 'name') {
                    $filename = $filename ?: decode_mime($param->value);
                }
            }
            if (!$filename || !is_excel($filename)) continue;

            $lower = strtolower($filename);
            if ($attachment_name_equals && $lower !== $attachment_name_equals) continue;
            if ($attachment_name_contains && strpos($lower, $attachment_name_contains) === false) continue;

            // Загрузка тела части (part index начинается с 1)
            $part_num = $i + 1;
            $body     = imap_fetchbody($imap, $uid, (string)$part_num);

            // Декодирование
            switch ($part->encoding ?? 0) {
                case 3: $body = base64_decode($body);        break; // BASE64
                case 4: $body = quoted_printable_decode($body); break; // QP
            }

            if (!$body) continue;

            save_file($tab, $filename, $body);
            $found++;
            break; // берём первое подходящее вложение из письма
        }
    }

    if ($found === 0) {
        echo "[INFO] Подходящих вложений не найдено (tab=$tab).\n";
    }

    imap_close($imap);
}

// ── Копировать файлы из локальной папки ──────────────────────────────────────

function fetch_from_folder(string $tab): void {
    // Ищем папку tab/ рядом со скриптом и на уровень выше
    $candidates = [
        __DIR__ . "/$tab",
        dirname(__DIR__) . "/$tab",
    ];

    $folder = null;
    foreach ($candidates as $c) {
        if (is_dir($c)) { $folder = $c; break; }
    }

    if (!$folder) {
        echo "[SKIP] Папка '$tab' не найдена рядом со скриптом.\n";
        return;
    }

    echo "[INFO] Читаю папку: $folder\n";

    $latest_file  = null;
    $latest_mtime = 0;

    foreach (EXCEL_EXTS as $ext) {
        foreach (glob("$folder/*.$ext") ?: [] as $f) {
            $mtime = filemtime($f);
            if ($mtime > $latest_mtime) {
                $latest_mtime = $mtime;
                $latest_file  = $f;
            }
        }
    }

    if (!$latest_file) {
        echo "[SKIP] В папке '$folder' нет Excel-файлов.\n";
        return;
    }

    $original_name = basename($latest_file);
    $ts       = date('Ymd_His');
    $safe     = safe_filename($original_name);
    $dest     = OUTPUT_DIR . "{$tab}_{$ts}_{$safe}";
    copy($latest_file, $dest);
    echo "[OK]   Скопирован: " . basename($dest) . " (из $folder)\n";
}

// ── Точка входа ───────────────────────────────────────────────────────────────

echo "=== fetch_excel.php ===\n";
echo "Сохранение в: " . OUTPUT_DIR . "\n\n";

$settings = load_settings();

foreach (['approach', 'departure'] as $tab) {
    echo "--- $tab ---\n";
    $cfg = get_imap_cfg($settings, $tab);

    // Сначала пробуем почту, потом локальную папку
    if (!empty($cfg['enabled'])) {
        fetch_from_imap($cfg, $tab);
    } else {
        fetch_from_folder($tab);
    }
    echo "\n";
}

echo "=== Готово ===\n";
